import streamlit as st
from jackpots_publisher import start_publisher

st.set_page_config(page_title='OLG Jackpot Monitor', page_icon='🎰', layout='wide')
worker = start_publisher()
st.title('OLG Jackpot Monitor')
st.caption('Valores publicados por este Streamlit para o ESP32-C6. Fonte: Loto-Québec (em validação). Transmissão somente com os três valores e datas confirmados.')
if st.button('Atualizar agora'):
    worker.request_refresh()
    st.info('Atualização solicitada. A página será atualizada em alguns segundos.')

@st.fragment(run_every='5s')
def show_snapshot():
    result = worker.snapshot()
    values = result['values']
    for col, key, label in zip(st.columns(3),
        ('lotto_max', 'gold_ball', 'maxmillions'),
        ('Lotto Max (M CAD)', 'Gold Ball (M CAD)', 'Maxmillions (qtd.)')):
        col.metric(label, values.get(key) if values.get(key) is not None else 'Indisponível')
    st.write('Status:', result['status'], '| Consulta UTC:', result['checked_at'])
    if not result['transmit_allowed']:
        st.warning('Dados indisponíveis, incompletos ou vencidos. Envio dos valores publicado como bloqueado.')
    for error in result.get('errors', []):
        st.error(error)
    st.link_button('JSON para o C6', 'https://orcomputer.streamlit.app/~/+/app/static/jackpots_current.json')
    with st.expander('JSON publicado e diagnóstico'):
        st.json(result)
show_snapshot()


# On-demand read-only HTML inspection. Never publishes or changes C6 data.
with st.expander('Diagnóstico do HTML bruto (requests)', expanded=False):
    st.caption('Busca independente para investigar o parser. Não modifica o JSON do C6.')
    if st.button('Inspecionar HTML recebido', key='inspect_loto_html'):
        import requests
        import re
        from bs4 import BeautifulSoup
        from lotoquebec_parser import SOURCE, parse_jackpots
        try:
            response = requests.get(SOURCE, headers={
                'User-Agent': 'Mozilla/5.0',
                'Accept-Language': 'en-CA,en;q=0.9',
            }, timeout=(8, 20))
            response.raise_for_status()
            response.encoding = 'utf-8'
            raw = response.text
            st.download_button(
                'Baixar HTML recebido (.html)',
                data=response.content,
                file_name='lotoquebec_requests.html',
                mime='text/html',
                key='download_loto_html',
            )
            soup = BeautifulSoup(raw, 'html.parser')
            for node in soup(['script', 'style', 'nav', 'footer', 'header']):
                node.decompose()
            visible = re.sub(r'\\s+', ' ', ' '.join(soup.stripped_strings))
            st.write('HTTP:', response.status_code, '| Bytes:', len(response.content),
                     '| Caracteres visíveis:', len(visible))
            st.write('Parser atual:')
            st.json(parse_jackpots(raw))
            st.text_area('Texto visível (até 6000 caracteres)', visible[:6000], height=220)
            st.markdown('**Trechos do texto visível usados pelo parser**')
            for term in ('Maxmillions', 'The Gold Ball', 'Lotto Max', 'Lotto 6/49'):
                hits = list(re.finditer(re.escape(term), visible, re.I))
                st.write(term + ': ' + str(len(hits)) + ' ocorrência(s)')
                for hit in hits[:4]:
                    st.code(visible[max(0, hit.start()-260):min(len(visible), hit.end()+320)], language='text')
            from lotoquebec_parser import DATE_RE, AMOUNT_RE, COUNT_RE
            st.write('Datas reconhecidas:', [m.group(0) for m in DATE_RE.finditer(visible)][:12])
            st.write('Valores em milhões reconhecidos:', AMOUNT_RE.findall(visible)[:12])
            st.write('Maxmillions reconhecidos:', COUNT_RE.findall(visible)[:12])
            for term in ('Lotto Max', 'Maxmillions', 'Gold Ball', 'Lotto 6/49'):
                st.markdown('**Trechos para: ' + term + '**')
                matches = list(re.finditer(re.escape(term), raw, re.I))
                st.caption(str(len(matches)) + ' ocorrência(s) no HTML bruto; até 3 exemplos.')
                for match in matches[:3]:
                    fragment = raw[max(0, match.start()-350):match.end()+550]
                    st.code(fragment, language='html')
        except Exception as exc:
            st.error('Falha ao inspecionar HTML: ' + type(exc).__name__ + ': ' + str(exc)[:300])
