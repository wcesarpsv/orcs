import streamlit as st
from streamlit_qrcode_scanner import qrcode_scanner

st.title("Scanner Test")

code = qrcode_scanner()

if code:
    st.success(f"Scanned: {code}")
