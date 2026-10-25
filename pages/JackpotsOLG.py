import streamlit as st
from jackpots_publisher import start_publisher

st.set_page_config(page_title='OLG Jackpot Monitor', page_icon='🎰', layout='wide')
worker = start_publisher()
st.title('OLG Jackpot Monitor')
st.caption('Valores publicados por este Streamlit para o ESP32-C6. Fonte: OLG (site chinês). Maxmillions fixo em 0 nesta versão.')
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

