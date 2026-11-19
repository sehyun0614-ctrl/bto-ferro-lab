import numpy as np
import pandas as pd
import streamlit as st

from physics import Device, ALL_DEVICES, triangle, quasistatic_qv, loop_metrics
from plotting import fig, DEVICE_COLORS

mat = st.session_state["material"]
st.title("소자 설계값")
st.caption("사이드바 물성값으로 계산한 '모델' 값입니다. 측정에서 C가 나오면 εr을 역산해 사이드바에 넣으세요.")

st.dataframe(pd.DataFrame([Device(s, n, mat).summary() for s, n in ALL_DEVICES]), hide_index=True,
             use_container_width=True)

st.subheader("MFBM에서 TiO₂가 가져가는 전압")
f, ax = fig(w=8, h=3.4)
n = np.array([2, 4, 6, 8])
share = [Device("MFBM", k, mat).tio2_voltage_share * 100 for k in n]
ax.bar(n.astype(str), share, color="#f59e0b")
for x, s in zip(n.astype(str), share):
    ax.text(x, s + 1, f"{s:.0f}%", ha="center")
ax.set_xlabel("BTO 코팅 횟수"); ax.set_ylabel("TiO₂ 전압 분담 (%)"); ax.set_ylim(0, 100)
st.pyplot(f)
st.markdown("TiO₂(εr≈40)는 BTO(εr≈300)보다 유전율이 훨씬 낮아서, 얇아도 **전압을 많이 가져갑니다**. "
            "그래서 MFBM은 같은 전압에서 BTO에 걸리는 전계가 작고, 겉보기 Vc가 커지고, 루프가 기울어집니다.")

st.subheader("예상 P–E 루프: MFM vs MFBM (같은 코팅 횟수)")
c1, c2, c3 = st.columns(3)
coats = c1.selectbox("코팅 횟수", [2, 4, 6, 8], index=1)
emax = c2.slider("최대 평균전계 (kV/cm)", 50, 400, 250, 10)
freq = c3.select_slider("주파수", [100, 1000, 10000], value=1000)
f, ax = fig(1, 2, w=10, h=4)
rows = []
for s in ["MFM", "MFBM"]:
    d = Device(s, coats, mat)
    vp = emax * 1e5 * d.gap
    t, v = triangle(vp, freq, 300, 2)
    Q, EB, P = quasistatic_qv(v, d)
    sl = slice(300, 600)
    E = v[sl] / (d.gap * 100) / 1e3
    Pm = Q[sl] / (d.area * 1e4) * 1e6
    Pm = Pm - 0.5 * (Pm.max() + Pm.min())
    pr, ec = loop_metrics(E, Pm)
    col = DEVICE_COLORS[f"{s}{coats}"]
    ax[0].plot(E, Pm, color=col, lw=2, label=f"{s}{coats}")
    ax[1].plot(E, EB[sl] / 1e5, color=col, lw=2, label=f"{s}{coats}")
    rows.append({"시편": f"{s}{coats}", "Vp (V)": round(vp, 2), "겉보기 Pr (µC/cm²)": round(pr, 2),
                 "겉보기 Ec (kV/cm)": round(ec, 1), "BTO 최대 내부전계 (kV/cm)": round(np.abs(EB).max() / 1e5, 0)})
ax[0].set_xlabel("평균 전계 E (kV/cm)"); ax[0].set_ylabel("P (µC/cm²)"); ax[0].legend(); ax[0].set_title("측정 화면에 보이는 루프")
ax[1].plot([-emax, emax], [-emax, emax], "k:", lw=0.8, label="E_BTO = E_평균")
ax[1].set_xlabel("평균 전계 (kV/cm)"); ax[1].set_ylabel("BTO 내부 전계 (kV/cm)"); ax[1].legend(); ax[1].set_title("BTO가 실제로 받는 전계")
st.pyplot(f)
st.dataframe(pd.DataFrame(rows), hide_index=True)
st.caption("모델: BTO 분극은 Ps·tanh((E∓Ec)/δ) 분기와 이력 규칙, TiO₂는 선형 유전체, 두 층은 전속밀도 연속(D 연속)으로 직렬 연결. "
           "MFBM의 Pr이 작게 보이는 건 탈분극장(분극 전하를 TiO₂가 완전히 가리지 못함) 때문입니다 (Segatto 2022).")
