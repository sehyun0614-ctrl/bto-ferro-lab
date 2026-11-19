import streamlit as st
import pandas as pd
from matplotlib.patches import Rectangle

from core.physics import Device, ALL_DEVICES
from core.plotting import fig, PALETTE

mat = st.session_state["material"]

st.title("BTO Ferro Lab")
st.markdown(
    "졸-겔 **BaTiO₃(BTO)** 강유전 커패시터에서 **TiO₂ 버퍼층**이 강유전 특성과 누설에 주는 영향을 보고, "
    "이 소자를 **차세대 통신용 비휘발 메모리(FeRAM)**로 쓸 수 있는지 따져 보는 연구 도구입니다."
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("시편", "8종", "MFM / MFBM × 2·4·6·8회")
c2.metric("BTO 1회 두께", "43.8 nm", "단면 SEM 실측")
c3.metric("11/19 측정 파일", "39개", "자동 판정")
c4.metric("상부 패드", "Ø 750 µm", "4.42×10⁻³ cm²")

st.subheader("두 가지 구조")
f, ax = fig(1, 2, w=9, h=3.0)
for a, (name, layers) in zip(ax, [
    ("MFM  (Pt / BTO / Pt)", [("Pt 하부전극", 0.25, "#9ca3af"), ("BaTiO₃", 1.0, "#60a5fa"), ("Pt 패드", 0.25, "#9ca3af")]),
    ("MFBM  (Pt / TiO₂ / BTO / Pt)", [("Pt 하부전극", 0.25, "#9ca3af"), ("TiO₂ 버퍼 32.7 nm", 0.4, "#fbbf24"),
                                    ("BaTiO₃", 1.0, "#60a5fa"), ("Pt 패드", 0.25, "#9ca3af")]),
]):
    y = 0
    for lab, h, col in layers:
        w0, w1 = (0, 1) if "패드" not in lab else (0.3, 0.7)
        a.add_patch(Rectangle((w0, y), w1 - w0, h, color=col, ec="white"))
        a.text(0.5, y + h / 2, lab, ha="center", va="center", fontsize=9)
        y += h
    a.set_xlim(0, 1); a.set_ylim(0, 2.1); a.axis("off"); a.set_title(name)
st.pyplot(f)

st.subheader("이 앱으로 할 수 있는 것")
st.markdown("""
| 페이지 | 하는 일 |
|---|---|
| 공정 레시피 · XRD | 팀 공정 조건 정리, 700 °C / 750 °C XRD 비교와 2차상 피크 표시 |
| 소자 설계값 | 8개 시편의 두께, 측정 전압, 예상 C·Vc를 물성값에서 바로 계산 |
| 측정 진단 시뮬레이터 | 시편·접촉 상태·장비 세팅을 고르면 I–V, C–V, P–E 예상 결과와 자동 판정. 11/19 실측을 겹쳐 비교 |
| 11/19 측정 데이터 | B1500A CSV를 파싱해서 정상/open/short/바닥신호로 자동 분류, 새 CSV 업로드 가능 |
| 차세대 통신 메모리 | 우리 소자를 1T1C FeRAM 셀로 축소했을 때 읽기 여유, 쓰기 속도, 에너지, 내구성을 통신 응용 요구치와 비교 |
| 레퍼런스 / AI 기록 | 근거 논문과, AI를 어떻게 썼고 무엇을 직접 검증했는지 |
""")

st.info("**값의 출처 표시 규칙**: 실측 = 우리가 측정한 값, 가정 = 문헌 범위에서 고른 값, 모델 = 계산으로 투영한 값. "
        "왼쪽 사이드바의 물성 가정값을 바꾸면 모든 페이지가 같이 바뀝니다.")

st.subheader("현재 물성값으로 본 8개 시편")
st.dataframe(pd.DataFrame([Device(s, n, mat).summary() for s, n in ALL_DEVICES]), hide_index=True,
             use_container_width=True)
