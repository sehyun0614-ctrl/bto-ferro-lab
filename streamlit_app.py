"""BTO FAB Simulator - Streamlit 배포용 래퍼.
같은 폴더의 index.html(시뮬레이터 본체)을 그대로 화면에 띄운다.
실행: streamlit run streamlit_app.py
"""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="BTO FAB Simulator", page_icon="🔬", layout="wide",
                   initial_sidebar_state="collapsed")
st.markdown("""<style>
  .block-container {padding: 0 !important; max-width: 100% !important;}
  header[data-testid="stHeader"] {display: none;}
  footer {display: none;}
</style>""", unsafe_allow_html=True)

html = (Path(__file__).parent / "index.html").read_text(encoding="utf-8")
components.html(html, height=920, scrolling=True)
