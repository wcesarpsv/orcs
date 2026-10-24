import streamlit as st
from jackpots_publisher import start_publisher

st.set_page_config(page_title='OLG Jackpot Monitor', page_icon='🎰', layout='wide')
worker = start_publisher()
st.title('OLG Jackpot Monitor')
st.caption('Valores publicados por este Streamlit para o ESP32-C6. Fonte oficial: OLG.')
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
    st.link_button('JSON para o C6', 'https://orcomputer.streamlit.app/app/static/jackpots_current.json')
    with st.expander('JSON publicado e diagnóstico'):
        st.json(result)

    with st.expander('Diagnóstico do acesso do C6', expanded=True):
        from pathlib import Path
        import streamlit
        static_enabled = st.get_option('server.enableStaticServing')
        st.write('Serviço de arquivos estáticos ativo:', static_enabled)
        st.write('Arquivo JSON existe no servidor:', worker.path.is_file())
        st.write('Pasta do JSON:', str(worker.path.parent))
        st.write('Streamlit:', streamlit.__version__)
        st.download_button('Baixar JSON atual', __import__('json').dumps(result, ensure_ascii=False, indent=2),
                           'jackpots_current.json', 'application/json', key='current_snapshot_download')
        if not static_enabled:
            st.error('O servidor está com enableStaticServing desativado, apesar do arquivo no repositório.')
show_snapshot()
