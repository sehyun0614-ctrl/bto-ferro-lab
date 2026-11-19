"""
BTO Ferro Lab - 졸-겔 BaTiO3 강유전 커패시터 연구 도구
국민대학교 UROP | 심인보 교수님 연구실 | 박세현, 김지우, 병욱

실행:  streamlit run app.py
"""
import streamlit as st

from core.physics import Material

st.set_page_config(page_title="BTO Ferro Lab", page_icon="⚡", layout="wide")


def sidebar_material() -> Material:
    """모든 페이지가 공유하는 물성값. 실측으로 바뀌면 여기서 바로 반영된다."""
    with st.sidebar:
        st.markdown("### 물성 가정값")
        st.caption("모든 페이지의 계산에 공통으로 쓰입니다. 실측값이 나오면 바꿔 보세요.")
        eps = st.slider("BTO 유전율 εr", 100, 800, 300, 10, key="eps_bto")
        eps_t = st.slider("TiO₂ 유전율 εr", 20, 100, 40, 5, key="eps_tio2")
        ps = st.slider("포화분극 Ps (µC/cm²)", 0.5, 26.0, 6.0, 0.5, key="ps",
                       help="벌크 단결정 BTO 약 26, 졸-겔 무배향 박막은 1~8 수준")
        ec = st.slider("항전계 Ec (kV/cm)", 10, 120, 40, 5, key="ec")
        f2 = st.slider("2차상(BaCO₃ 등) 분율", 0.0, 0.3, 0.0, 0.01, key="f2",
                       help="XRD에서 본 2차상. 유효 유전율과 Ps를 낮춥니다.")
        rho = st.select_slider("막 비저항 (Ω·m)", options=[1e8, 1e9, 1e10, 1e11, 1e12, 1e13],
                               value=1e12, key="rho", format_func=lambda x: f"{x:.0e}")
        st.divider()
        st.caption("국민대 UROP · Pt/BTO/Pt vs Pt/TiO₂/BTO/Pt")
    return Material(eps_bto=eps, eps_tio2=eps_t, Ps_uC=ps, Ec_kVcm=ec, second_phase=f2, rho_film=rho)


st.session_state["material"] = sidebar_material()

pages = {
    "연구": [
        st.Page("views/home.py", title="개요", icon="🏠", default=True),
        st.Page("views/recipe.py", title="공정 레시피 · XRD", icon="🧪"),
        st.Page("views/design.py", title="소자 설계값", icon="📐"),
    ],
    "측정": [
        st.Page("views/simulator.py", title="측정 진단 시뮬레이터", icon="🔬"),
        st.Page("views/data1119.py", title="11/19 측정 데이터", icon="📊"),
    ],
    "응용": [
        st.Page("views/memory.py", title="차세대 통신 메모리", icon="📡"),
    ],
    "자료": [
        st.Page("views/references.py", title="레퍼런스", icon="📚"),
        st.Page("views/ai_log.py", title="AI 활용 · 검증 기록", icon="🤖"),
    ],
}
st.navigation(pages).run()
