import numpy as np
import pandas as pd
import streamlit as st
from scipy.signal import medfilt

from dataset import load_all, record_from_bytes, KIND_KO
from b1500 import STATUS_KO, gap_of
from physics import A_PAD
from plotting import fig, nominor, DEVICE_COLORS, PALETTE

st.title("11/19 측정 데이터")
st.caption("B1500A EasyEXPERT CSV를 그대로 읽어서 측정 종류, 시편, 판정을 자동으로 붙입니다. 새 측정 파일을 올려도 같은 기준으로 판정해요.")


@st.cache_data(show_spinner="CSV 파싱 중...")
def base_records():
    return load_all()


recs = list(base_records())
up = st.file_uploader("새 측정 CSV 추가 (여러 개 가능)", type=["csv"], accept_multiple_files=True)
for u in up or []:
    r = record_from_bytes(u.name, u.getvalue())
    if r:
        recs.append(r)

table = pd.DataFrame([{
    "시간": r["time"], "측정": r["kind_ko"], "시편": r["sample"], "판정": STATUS_KO.get(r["status"], r["status"]),
    "근거": r["msg"], "파일": r["file"], "시편 근거": r["sample_note"],
} for r in recs])

st.subheader("한눈에 보기")
c = table["판정"].value_counts()
cols = st.columns(len(c))
for col, (k, v) in zip(cols, c.items()):
    col.metric(k, v)

# 판정 매트릭스 (시편 x 측정)
samples = ["MFM2", "MFM4", "MFM6", "MFM8", "MFBM2", "MFBM4", "MFBM6", "MFBM8"]
kinds = ["I–V (HRSMU)", "C–V (4284A)", "P–E (WGFMU)"]
mat = pd.DataFrame("", index=kinds, columns=samples)
for r in recs:
    s = r["sample"]
    if s in samples and r["kind_ko"] in kinds and r["status"] not in ("empty", "nodata"):
        cur = mat.loc[r["kind_ko"], s]
        lab = STATUS_KO[r["status"]]
        if lab not in cur:
            mat.loc[r["kind_ko"], s] = (cur + " / " if cur else "") + lab
COL = {"정상": "#c6f6d5", "바닥신호": "#fefcbf", "Open": "#bee3f8", "Short": "#fed7d7", "Leaky": "#feebc8"}


def color(v):
    for key, c_ in COL.items():
        if key in v:
            return f"background-color:{c_};color:#111"
    return "color:#999"


st.markdown("**시편 × 측정 판정 매트릭스**")
_sty = mat.replace("", "미측정").style
_sty = _sty.map(color) if hasattr(_sty, "map") else _sty.applymap(color)
st.dataframe(_sty, use_container_width=True)
st.caption("정상(nF, D<0.1 / 루프)은 아직 0건. 바닥신호 = 절연은 확인됐지만 막 신호인지 측정계 바닥인지 미구분.")

st.subheader("파일 목록")
f_kind = st.multiselect("측정 종류", sorted(table["측정"].unique()), default=sorted(table["측정"].unique()))
f_stat = st.multiselect("판정", sorted(table["판정"].unique()), default=sorted(table["판정"].unique()))
view = table[table["측정"].isin(f_kind) & table["판정"].isin(f_stat)]
st.dataframe(view, hide_index=True, use_container_width=True, height=360)

# ------------------------------------------------------------------ 개별 파일
st.subheader("파일 하나 자세히 보기")
names = [r["file"] for r in recs if r["status"] not in ("empty", "nodata")]
pick = st.selectbox("파일", names)
r = next(x for x in recs if x["file"] == pick)
st.write(f"**{r['kind_ko']} · {r['sample']} · {STATUS_KO[r['status']]}** — {r['msg']}")
if r["info"]:
    st.json({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r["info"].items()}, expanded=False)
df = r["blocks"][0].df
f, ax = fig(w=8, h=3.6)
if r["kind"] == "IV":
    ax.plot(df.iloc[:, 0], df.iloc[:, 1] * 1e12, ".-", ms=3); ax.set_xlabel("V (V)"); ax.set_ylabel("I (pA)")
elif r["kind"] == "CV":
    ax.plot(df.iloc[:, 0], df.iloc[:, 1] * 1e9, "o-", ms=3, label="Cp")
    ax.set_xlabel("V (V)"); ax.set_ylabel("Cp (nF)")
    ax2 = ax.twinx(); ax2.plot(df.iloc[:, 0], np.abs(df.iloc[:, 2]), "s", ms=2, color=PALETTE["bad"], label="|D|")
    ax2.set_yscale("log"); ax2.set_ylabel("|D|"); ax2.grid(False)
elif r["kind"] == "PE":
    ax.plot(df["Voltage"], df["Current"] * 1e3, ".", ms=2); ax.set_xlabel("V (V)"); ax.set_ylabel("I (mA)")
elif r["kind"] == "PATTERN":
    d2 = df.drop_duplicates(subset=["Time"])
    ax.plot(d2["Time"] * 1e6, d2["MeasResult1_value"] * 1e3, "o-"); ax.set_xlabel("t (µs)"); ax.set_ylabel("I (mA)")
st.pyplot(f)

# ------------------------------------------------------------------ I-V 분석
st.subheader("I–V 분석: 살릴 수 있는 데이터")
st.markdown("쇼트가 아닌 패드의 I–V는 **'막 누설의 상한'**으로 쓸 수 있습니다. 처리: 5점 메디안 필터, 스윕 초기 15%(이완 전류) 제외, +분기만 사용.")
iv = [x for x in recs if x["kind"] == "IV" and x["status"] in ("floor", "ok") and gap_of(x["sample"])]
seen = set()
f, ax = fig(1, 3, w=12, h=3.8)
rows = []
for x in iv:
    s = x["sample"]
    d = x["blocks"][0].df
    V, I0 = d.iloc[:, 0].values, d.iloc[:, 1].values
    I = medfilt(I0, 5)
    keep = np.arange(len(V)) > len(V) * 0.15
    g = gap_of(s)
    col = DEVICE_COLORS.get(s, "#555")
    lab = s if s not in seen else None
    seen.add(s)
    ax[0].plot(V[keep], I[keep] * 1e12, color=col, lw=1.4, label=lab)
    m = keep & (V > 0.05 * V.max()) & (I > 0)
    ax[1].loglog(V[m] / (g * 100) / 1e3, I[m] / (A_PAD * 1e4), color=col, lw=1.4, label=lab)
    mm = (V > 0.3 * V.max()) & (I > 0)
    slope = np.polyfit(np.log10(V[mm]), np.log10(I[mm]), 1)[0]
    rows.append({"시편": s, "파일": x["file"][:32], "Gap (nm)": round(g * 1e9, 1), "Vmax": float(V.max()),
                 "J@+Vmax (A/cm²)": float(I[-1] / (A_PAD * 1e4)), "I@+3V (pA)": float(np.interp(3, V, I) * 1e12) if V.max() >= 3 else np.nan,
                 "log-log 기울기": round(slope, 2)})
ax[0].set_xlabel("V (V)"); ax[0].set_ylabel("I (pA)"); ax[0].legend(fontsize=7); ax[0].set_title("보정 후 I–V")
ax[1].set_xlabel("E (kV/cm)"); ax[1].set_ylabel("J (A/cm²)"); ax[1].set_title("+분기 J–E (상한)")
res = pd.DataFrame(rows)
gp = res.groupby("시편").agg({"Gap (nm)": "first", "I@+3V (pA)": "mean"}).reset_index().dropna()
ax[2].plot(gp["Gap (nm)"], gp["I@+3V (pA)"], "ko-", label="실측 I(+3 V)")
ref = gp["I@+3V (pA)"].iloc[0] * np.exp(-(gp["Gap (nm)"] - gp["Gap (nm)"].iloc[0]) / 40)
ax[2].plot(gp["Gap (nm)"], ref, "r:", label="막 누설이라면 (예시)")
ax[2].set_yscale("log"); ax[2].set_xlabel("Gap (nm)"); ax[2].set_ylabel("I @ +3 V (pA)"); ax[2].legend(fontsize=7)
ax[2].set_title("두께 무관 = 측정계 바닥")
nominor(ax[1], ax[2])
st.pyplot(f)
st.dataframe(res, hide_index=True, use_container_width=True)
st.markdown("""
**결론 (말할 수 있는 범위)**
- 확실: 시편 5종 모두 250 kV/cm까지 절연 유지, **J ≤ 약 10⁻⁸ A/cm²**, 반복 측정 재현성 확인.
- 조건부: log I–log V 기울기 약 1.0~1.2 → Ohmic 영역, SCLC(기울기 2) 진입 없음.
- 불가: 같은 3 V에서 두께가 3배 달라도 전류가 같아서, MFM과 MFBM의 누설 차이는 이 데이터로 주장할 수 없음.
""")
