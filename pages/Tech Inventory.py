import re
from datetime import datetime, timezone
import requests
import streamlit as st
from bs4 import BeautifulSoup

URL = 'https://www.olg.ca/en/home.html'
HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; JackpotMonitor/1.0)'}

@st.cache_data(ttl=300, show_spinner=False)
def fetch():
    response = requests.get(URL, headers=HEADERS, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    text = soup.get_text(' ', strip=True)
    patterns = {
        'lotto_max': r'LOTTO MAX\s+\$\s*(\d+(?:\.\d+)?)\s*MILLION',
        'gold_ball': r'GOLD BALL\s*\$\s*([\d,]+)',
        'maxmillions': r'\+\s*(\d+)\s*x\s*MAXMILLIONS',
    }
    values = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.I)
        values[key] = float(match.group(1)) if match and key == 'lotto_max' else (int(match.group(1).replace(',', '')) if match else None)
    return {'values': values, 'checked_at': datetime.now(timezone.utc).isoformat(), 'source': URL, 'raw_excerpt': text[:1500]}

st.set_page_config(page_title='OLG Jackpot Monitor', page_icon='🎰')
st.title('OLG Jackpot Monitor')
st.caption('Protótipo de captura da página pública oficial da OLG — não afiliado à OLG')
if st.button('Atualizar agora'):
    fetch.clear()
try:
    result = fetch()
    values = result['values']
    st.write('Consulta UTC:', result['checked_at'])
    a, b, c = st.columns(3)
    a.metric('Lotto Max (milhões CAD)', values['lotto_max'] if values['lotto_max'] is not None else 'Indisponível')
    b.metric('Gold Ball (CAD)', values['gold_ball'] if values['gold_ball'] is not None else 'Indisponível')
    c.metric('Maxmillions (quantidade)', values['maxmillions'] if values['maxmillions'] is not None else 'Indisponível')
    st.json({'status': 'ok' if all(v is not None for v in values.values()) else 'partial', **result})
    if any(v is None for v in values.values()):
        st.warning('Algum valor não foi identificado. Não transmitir valores incompletos.')
except Exception as exc:
    st.error(f'Falha na consulta: {exc}')
