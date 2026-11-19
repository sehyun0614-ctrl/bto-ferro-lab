import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from scipy.ndimage import median_filter
from scipy.signal import find_peaks

from plotting import fig

ROOT = Path(__file__).resolve().parent
recipe = json.loads((ROOT / "recipe.json").read_text(encoding="utf-8"))

st.title("공정 레시피 · XRD")

st.subheader("공정 단계")
df = pd.DataFrame(recipe["steps"])
df["value"] = df["value"].fillna("(미기입)")
st.dataframe(df.rename(columns={"no": "#", "stage": "단계", "item": "항목", "value": "조건", "status": "상태", "note": "비고"}),
             hide_index=True, use_container_width=True)
missing = df[df["status"] == "미기입"]["item"].tolist()
if missing:
    st.warning(f"아직 기록이 없는 항목 {len(missing)}개: " + ", ".join(sorted(set(missing))) +
               ". `data/recipe.json`에 실험노트 값을 채우면 이 표가 바로 갱신됩니다.")

st.subheader("두께 계산기")
c1, c2, c3 = st.columns(3)
n = c1.number_input("BTO 코팅 횟수", 1, 12, 4)
per = c2.number_input("1회 두께 (nm)", 10.0, 100.0, 43.8, 0.1)
buf = c3.checkbox("TiO₂ 버퍼 포함 (32.69 nm)", True)
gap = n * per + (32.69 if buf else 0)
st.write(f"전극 사이 총 두께 **{gap:.1f} nm** → 250 kV/cm에 필요한 전압 **{gap*1e-7*250e3:.2f} V**")

st.subheader("진행 기록")
st.table(pd.DataFrame(recipe["history"]).rename(columns={"date": "날짜", "what": "내용"}))

# ---------------------------------------------------------------- XRD
st.subheader("XRD: 700 °C vs 750 °C")


def load_xrd(path):
    rows = []
    for line in path.read_text(errors="ignore").splitlines():
        p = line.replace(",", "\t").split("\t")
        try:
            rows.append((float(p[0]), float(p[1])))
        except (ValueError, IndexError):
            pass
    return np.array(rows)


REF = {
    "BTO": [(22.2, "(100)"), (31.6, "(110)"), (38.9, "(111)"), (45.3, "(200)"), (50.9, "(210)"), (56.2, "(211)")],
    "Pt": [(39.8, "(111)"), (46.2, "(200)")],
    "BaCO₃ 후보": [(23.9, ""), (24.3, ""), (34.6, ""), (42.0, "")],
    "TiO₂ 후보": [(25.3, "A101"), (27.4, "R110"), (36.1, "R101"), (54.3, "R211")],
}
REF_COL = {"BTO": "#1d4ed8", "Pt": "#6b7280", "BaCO₃ 후보": "#c2410c", "TiO₂ 후보": "#a16207"}

files = {"700 °C (11/11)": ROOT / "BTO700.TXT", "750 °C (11/13)": ROOT / "BTO750C.TXT"}
show = st.multiselect("기준 피크 표시", list(REF), default=list(REF))
tol = st.slider("피크 매칭 허용오차 (°)", 0.1, 0.6, 0.3, 0.05)

f, ax = fig(w=10, h=4.2)
peak_rows = []
for k, (lab, p) in enumerate(files.items()):
    d = load_xrd(p)
    y = d[:, 1] - median_filter(d[:, 1], 151)
    off = k * (np.percentile(y, 99.5) * 1.3)
    ax.plot(d[:, 0], y + off, lw=0.9, label=lab, color=["#0f766e", "#7c3aed"][k])
    pk, _ = find_peaks(y, prominence=np.std(y) * 4, distance=10)
    for i in pk:
        tt = d[i, 0]
        match = [f"{ph} {hkl}".strip() for ph, lst in REF.items() for pos, hkl in lst if abs(pos - tt) <= tol]
        peak_rows.append({"시편": lab, "2θ (°)": round(tt, 2), "세기(배경 제거)": int(y[i]),
                          "후보": ", ".join(match) if match else "미지정"})
        ax.annotate(f"{tt:.1f}", (tt, y[i] + off), textcoords="offset points", xytext=(0, 4), ha="center", fontsize=7)
for ph in show:
    for pos, hkl in REF[ph]:
        ax.axvline(pos, color=REF_COL[ph], lw=0.7, ls="--", alpha=0.6)
ax.set_xlabel("2θ (°)  Cu Kα"); ax.set_ylabel("세기 (배경 제거, 위아래 이동)")
ax.legend(loc="upper right")
st.pyplot(f)
st.dataframe(pd.DataFrame(peak_rows), hide_index=True, use_container_width=True)
st.caption("기준 피크 위치는 표준 카드의 대표값입니다. BaCO₃·TiO₂는 '후보'로만 표시하고, 최종 판정은 JCPDS/ICDD 카드와 "
           "HighScore 검색으로 확인하세요. 배경은 151점 메디안 필터로 뺐습니다.")
