import re
from datetime import datetime, timezone
import requests
import streamlit as st
from bs4 import BeautifulSoup

SOURCE = 'https://chinese.olg.ca/sc/index.php/lotto_max.php'
HEADERS = {'User-Agent': 'Mozilla/5.0 (JackpotMonitor/3.0)', 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'}

def parse_jackpots(html):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'nav', 'footer']): tag.decompose()
    text = soup.get_text(' ', strip=True)
    # The Chinese OLG page includes repeated jackpot panels. Focus on the
    # first next-draw jackpot block rather than historical winning numbers.
    blocks = re.split(r'下期头奖将于\s*', text)
    max_candidates = []
    gold_candidates = []
    for block in blocks[1:]:
        prefix = block[:350]
        date = re.search(r'(20\d{2})年(\d{1,2})月(\d{1,2})日', prefix)
        draw_date = f'{int(date[1]):04d}-{int(date[2]):02d}-{int(date[3]):02d}' if date else None
        # Gold Ball section includes a separate classic $5m and Gold Ball amount.
        if 'goldball' in prefix.lower() or '或1百万元大奖' in prefix:
            money = re.findall(r'\$\s*([\d,]+)', prefix)
            if len(money) >= 2:
                gold_candidates.append((draw_date, int(money[1].replace(',', '')) // 1_000_000, prefix))
        # Maxmillions block: estimated jackpot and explicit MAXMILLIONS count.
        if '估计彩金' in prefix or 'MAXMILLIONS' in prefix.upper():
            dollars = re.search(r'\$\s*([\d,]+)\s*估计彩金', prefix)
            chinese = re.search(r'(\d+(?:\.\d+)?)\s*千万元\s*估计彩金', prefix)
            if dollars:
                max_value = int(dollars[1].replace(',', '')) // 1_000_000
            elif chinese:
                max_value = int(float(chinese[1]) * 10)
            else:
                max_value = None
            mm = re.search(r'另加\s*(\d+)\s*项\s*1百万元的\s*MAXMILLIONS', prefix, re.I)
            # No explicit Maxmillions line means zero only if the next-draw
            # jackpot section is otherwise positively identified.
            if max_value is not None:
                max_candidates.append((draw_date, max_value, int(mm[1]) if mm else 0, prefix))
    # Reject conflicting snapshots rather than silently choosing one.
    def unique_latest(items):
        valid = [x for x in items if x[0]]
        if not valid: return None
        latest = max(x[0] for x in valid)
        matching = [x for x in valid if x[0] == latest]
        return matching[0] if len({str(x[1:-1]) for x in matching}) == 1 else None
    m = unique_latest(max_candidates)
    g = unique_latest(gold_candidates)
    values = {'lotto_max': m[1] if m else None, 'gold_ball': g[1] if g else None, 'maxmillions': m[2] if m else None}
    return {'values': values, 'draw_dates': {'lotto_max': m[0] if m else None, 'gold_ball': g[0] if g else None}, 'evidence': {'lotto_max': m[3] if m else None, 'gold_ball': g[2] if g else None}, 'excerpt': text[:1200]}

@st.cache_data(ttl=300, show_spinner=False)
def fetch():
    response = requests.get(SOURCE, headers=HEADERS, timeout=25)
    response.raise_for_status()
    parsed = parse_jackpots(response.text)
    parsed.update({'source': SOURCE, 'checked_at': datetime.now(timezone.utc).isoformat()})
    values = parsed['values']
    dates = parsed['draw_dates']
    today = datetime.now(timezone.utc).date().isoformat()
    complete = all(v is not None for v in values.values())
    # Draw dates should not be in the past (UTC is conservative near midnight).
    fresh = all(d is not None and d >= today for d in dates.values())
    parsed['status'] = 'ok' if complete and fresh else 'unverified'
    parsed['transmit_allowed'] = parsed['status'] == 'ok'
    return parsed

st.set_page_config(page_title='OLG Jackpot Monitor', page_icon='🎰', layout='wide')
st.title('OLG Jackpot Monitor')
st.caption('Fonte: versão chinesa oficial da OLG. Valores em milhões CAD; Maxmillions é quantidade.')
if st.button('Atualizar agora'):
    fetch.clear()
try:
    result = fetch()
    v = result['values']
    cols = st.columns(3)
    for col, key, label in zip(cols, ['lotto_max', 'gold_ball', 'maxmillions'], ['Lotto Max (M CAD)', 'Gold Ball (M CAD)', 'Maxmillions (qtd.)']):
        col.metric(label, v[key] if v[key] is not None else 'Indisponível')
    st.write('Status:', result['status'], '| Consulta UTC:', result['checked_at'])
    if not result['transmit_allowed']:
        st.error('Valores incompletos, ambíguos ou com data antiga. Transmissão bloqueada.')
    st.subheader('JSON para integração futura')
    st.json({k: result[k] for k in ('status', 'transmit_allowed', 'values', 'draw_dates', 'checked_at', 'source')})
    with st.expander('Diagnóstico da captura'):
        st.json(result)
        st.download_button('Baixar diagnóstico JSON', __import__('json').dumps(result, ensure_ascii=False, indent=2), 'olg_diagnostic.json', 'application/json')
except Exception as exc:
    st.error(f'Falha na consulta: {exc}')
    st.warning('Nenhum dado foi autorizado para transmissão.')
