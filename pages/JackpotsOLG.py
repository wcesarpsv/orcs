import streamlit as st
from jackpots_publisher import start_publisher

st.set_page_config(page_title='OLG Jackpot Monitor', page_icon='🎰', layout='wide')
worker = start_publisher()
st.title('OLG Jackpot Monitor')
st.caption('Valores publicados por este Streamlit para o ESP32-C6. Fonte: Lottery Post. Maxmillions fixo em 0 nesta versão.')
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
    st.link_button('JSON para o C6', 'https://orcomputer.streamlit.app/app/static/jackpots_current.json')
    with st.expander('JSON publicado e diagnóstico'):
        st.json(result)
show_snapshot()


st.divider()
st.subheader('Teste de acesso com navegador')
st.caption('Abre o Lottery Post no Chromium do servidor. Este teste não envia valores para o C6.')
if st.button('Testar com navegador', key='test_lottery_browser'):
    import time
    last_test = st.session_state.get('jackpots_browser_test_at', 0)
    if time.time() - last_test < 60:
        st.info('Aguarde 60 segundos entre testes.')
    else:
        st.session_state['jackpots_browser_test_at'] = time.time()
        from jackpots_browser_probe import probe
        with st.spinner('Abrindo a página no navegador do servidor…'):
            st.session_state['jackpots_browser_test_result'] = probe()
if 'jackpots_browser_test_result' in st.session_state:
    browser_result = st.session_state['jackpots_browser_test_result']
    if browser_result.get('ok'):
        st.success('O navegador conseguiu ler e validar os jackpots.')
    else:
        st.error(browser_result.get('error', 'O teste não conseguiu validar os jackpots.'))
    st.json(browser_result)
