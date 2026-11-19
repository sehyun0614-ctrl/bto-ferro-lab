import numpy as np
import pandas as pd
import streamlit as st

from physics import Device
from instruments import (CONTACTS, EMPIRICAL, sim_iv, diagnose_iv, sim_cv, diagnose_cv,
                              sim_pe, diagnose_pe, STATUS_STYLE)
from dataset import load_all
from plotting import fig, nominor, PALETTE

mat = st.session_state["material"]
st.title("측정 진단 시뮬레이터")
st.caption("시편, 프로브 접촉 상태, 장비 세팅을 고르면 B1500A/4284A 화면에 나올 결과를 계산하고 자동으로 판정합니다. "
           "접촉 상태와 장비 한계는 11/17·11/19 측정에서 실제로 겪은 값을 모델로 옮긴 것입니다.")


@st.cache_data(show_spinner=False)
def measured():
    out = {}
    for r in load_all():
        if r["status"] in ("empty", "nodata"):
            continue
        out.setdefault((r["kind"], r["sample"]), []).append(r)
    return out


MEAS = measured()

c1, c2, c3 = st.columns([1, 1, 2])
struct = c1.selectbox("구조", ["MFM", "MFBM"], index=1)
coats = c2.selectbox("BTO 코팅 횟수", [2, 4, 6, 8], index=0)
scenario = c3.radio("시나리오", ["11/19 재현", "권장 프로토콜 (목표)", "직접 설정"], horizontal=True)
dev = Device(struct, coats, mat)
name = dev.name
k = f"{scenario}_{name}"   # 시나리오/시편이 바뀌면 위젯 기본값이 새로 적용되게

st.markdown(f"**{name}** · gap {dev.gap*1e9:.1f} nm · 예상 C {dev.c_lin*1e9:.2f} nF · 예상 Vc {dev.vc_apparent:.2f} V · "
            f"Vmax(250 kV/cm) {dev.vmax} V")

ckeys = list(CONTACTS)
if scenario == "11/19 재현":
    d_iv = dict(contact="정상 접촉", vmax=dev.vmax, comp="100 mA")
    d_cv = dict(contact="장비/지그 경로 단락" if name in ("MFBM2", "MFBM6", "MFBM8") else "미접촉 (open)",
                f="1 kHz", vb=2.0)
    d_pe = dict(contact="장비/지그 경로 단락", vp=0.5 if name == "MFBM2" else 1.0, f="1 kHz", ir="1 mA")
elif scenario == "권장 프로토콜 (목표)":
    i_peak = dev.c_lin * 4 * min(dev.vmax, 5) * 1e3 + 2 * dev.mat.Ps * dev.area / (0.1e-3)
    d_iv = dict(contact="정상 접촉", vmax=dev.vmax, comp="100 µA")
    d_cv = dict(contact="정상 접촉", f="10 kHz", vb=2.0)
    d_pe = dict(contact="정상 접촉", vp=min(dev.vmax, 5.0), f="1 kHz", ir="10 mA" if i_peak > 0.9e-3 else "1 mA")
else:
    d_iv = dict(contact="정상 접촉", vmax=dev.vmax, comp="100 mA")
    d_cv = dict(contact="정상 접촉", f="10 kHz", vb=2.0)
    d_pe = dict(contact="정상 접촉", vp=min(dev.vmax, 5.0), f="1 kHz", ir="1 mA")

leaky_R = 1e5
FREQS = {"1 kHz": 1e3, "10 kHz": 1e4, "100 kHz": 1e5, "1 MHz": 1e6}
COMP = {"100 µA": 1e-4, "1 mA": 1e-3, "100 mA": 0.1}

tab_iv, tab_cv, tab_pe, tab_chk = st.tabs(["① I–V (HRSMU)", "② C–V (4284A)", "③ P–E (WGFMU)", "④ 측정 순서 점검"])


def badge(code, text):
    lab, col = STATUS_STYLE.get(code, (code, "#555"))
    st.markdown(f"<div style='border-left:5px solid {col};padding:6px 10px;background:rgba(127,127,127,.08)'>"
                f"<b style='color:{col}'>{lab}</b> · {text}</div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ I-V
with tab_iv:
    a, b, c = st.columns(3)
    iv_contact = a.selectbox("접촉 상태", ckeys, index=ckeys.index(d_iv["contact"]), key="ivc" + k)
    iv_vmax = b.number_input("±Vmax (V)", 0.5, 20.0, float(d_iv["vmax"]), 0.1, key="ivv" + k)
    iv_comp = c.selectbox("Compliance", list(COMP), index=list(COMP).index(d_iv["comp"]), key="ivcp" + k)
    if CONTACTS[iv_contact] == "leaky":
        leaky_R = st.select_slider("누설 패드 저항", [1e3, 1e4, 1e5, 1e6, 1e7], 1e5, format_func=lambda x: f"{x:.0e} Ω", key="lr1" + k)
    v, i, clip = sim_iv(dev, iv_vmax, compliance=COMP[iv_comp], contact=CONTACTS[iv_contact], leaky_R=leaky_R)
    iv_code, iv_msg = diagnose_iv(v, i, clip, dev)
    overlay = st.checkbox("11/19 실측 겹쳐 보기", True, key="ivo" + k)
    f, ax = fig(1, 2, w=10, h=3.8)
    ax[0].plot(v, i * 1e12, color=PALETTE["model"], lw=1.8, label="시뮬레이션")
    J = np.abs(i) / (dev.area * 1e4)
    ax[1].semilogy(v / (dev.gap * 100) / 1e3, J, color=PALETTE["model"], lw=1.8, label="시뮬레이션")
    recs = MEAS.get(("IV", name), [])
    if overlay and recs:
        df = recs[0]["blocks"][0].df
        ax[0].plot(df.iloc[:, 0], df.iloc[:, 1] * 1e12, ".", ms=3, color=PALETTE["measured"], label=f"실측 {recs[0]['file'][:22]}")
        ax[1].semilogy(df.iloc[:, 0] / (dev.gap * 100) / 1e3, np.abs(df.iloc[:, 1]) / (dev.area * 1e4), ".", ms=3,
                       color=PALETTE["measured"], label="실측")
    elif overlay:
        st.caption(f"{name}의 11/19 I–V 실측 파일은 없습니다.")
    ax[0].set_xlabel("V (V)"); ax[0].set_ylabel("I (pA)"); ax[0].legend()
    ax[1].set_xlabel("E 평균 (kV/cm)"); ax[1].set_ylabel("|J| (A/cm²)"); ax[1].legend(); nominor(ax[1])
    st.pyplot(f)
    badge(iv_code, iv_msg)
    with st.expander("이 결과가 이렇게 나오는 이유"):
        st.markdown(f"""
- 측정계 바닥: {EMPIRICAL['floor_R'][1]}
- 시작 이완 전류: {EMPIRICAL['relax_pA'][1]}
- **'미접촉'으로 바꿔도 곡선이 거의 같습니다.** 측정계 바닥이 막 누설보다 크면 I–V만으로는 접촉 여부를 알 수 없어요. 그래서 C–V로 먼저 확인해야 합니다.
""")

# ------------------------------------------------------------------ C-V
with tab_cv:
    a, b, c = st.columns(3)
    cv_contact = a.selectbox("접촉 상태", ckeys, index=ckeys.index(d_cv["contact"]), key="cvc" + k)
    cv_f = b.selectbox("주파수", list(FREQS), index=list(FREQS).index(d_cv["f"]), key="cvf" + k)
    cv_vb = c.number_input("±DC bias (V)", 0.1, 10.0, float(d_cv["vb"]), 0.1, key="cvb" + k)
    if CONTACTS[cv_contact] == "leaky":
        leaky_R = st.select_slider("누설 패드 저항", [1e3, 1e4, 1e5, 1e6, 1e7], 1e5, format_func=lambda x: f"{x:.0e} Ω", key="lr2" + k)
    v, Cp, D, over = sim_cv(dev, cv_vb, FREQS[cv_f], contact=CONTACTS[cv_contact], leaky_R=leaky_R)
    cv_code, cv_msg = diagnose_cv(v, Cp, D, over, dev)
    overlay = st.checkbox("11/19 실측 겹쳐 보기", True, key="cvo" + k)
    f, ax = fig(1, 2, w=10, h=3.8)
    n = len(v) // 2
    ax[0].plot(v[:n], Cp[:n] * 1e9, color=PALETTE["model"], lw=1.8, label="시뮬 (−→+)")
    ax[0].plot(v[n:], Cp[n:] * 1e9, color=PALETTE["model"], lw=1.8, ls="--", label="시뮬 (+→−)")
    ax[1].plot(v, np.abs(D), color=PALETTE["model"], lw=1.5, label="시뮬")
    recs = MEAS.get(("CV", name), [])
    if overlay and recs:
        df = recs[0]["blocks"][0].df
        ax[0].plot(df.iloc[:, 0], df.iloc[:, 1] * 1e9, ".", ms=4, color=PALETTE["measured"], label=f"실측 {recs[0]['file'][:20]}")
        ax[1].plot(df.iloc[:, 0], np.abs(df.iloc[:, 2]), ".", ms=4, color=PALETTE["measured"], label="실측")
    elif overlay:
        st.caption(f"{name}의 11/19 C–V 실측 파일은 없습니다.")
    ax[0].axhline(dev.c_lin * 1e9, color="#9ca3af", lw=0.8, ls=":")
    ax[0].set_xlabel("DC bias (V)"); ax[0].set_ylabel("Cp (nF)"); ax[0].legend()
    ax[1].set_yscale("log"); ax[1].set_xlabel("DC bias (V)"); ax[1].set_ylabel("|D|"); ax[1].axhline(0.1, color=PALETTE["warn"], lw=0.8)
    ax[1].legend()
    st.pyplot(f)
    badge(cv_code, cv_msg)
    with st.expander("판정 기준"):
        st.markdown(f"""
| 판정 | 기준 | 11/19 근거 |
|---|---|---|
| 정상 | C ≈ 예상값(nF), D < 0.1 | 아직 없음 |
| Open | C < 50 pF | {EMPIRICAL['stray_C'][1]} |
| Short | \\|D\\| > 10 또는 C 부호 뒤바뀜 | {EMPIRICAL['path_R_lcr'][1]} |
| Overflow | \\|bias\\| > 2.3 V | {EMPIRICAL['lcr_bias_limit'][1]} |
""")

# ------------------------------------------------------------------ P-E
with tab_pe:
    a, b, c, d = st.columns(4)
    pe_contact = a.selectbox("접촉 상태", ckeys, index=ckeys.index(d_pe["contact"]), key="pec" + k)
    pe_vp = b.number_input("Vp (V)", 0.1, 10.0, float(d_pe["vp"]), 0.1, key="pev" + k)
    pe_f = c.selectbox("주파수", ["1 kHz", "10 kHz"], index=["1 kHz", "10 kHz"].index(d_pe["f"]), key="pef" + k)
    pe_ir = d.selectbox("IrangeIm", ["1 mA", "10 mA"], index=["1 mA", "10 mA"].index(d_pe["ir"]), key="per" + k)
    if pe_vp > 5:
        st.warning("WGFMU(B1530A) 출력은 ±5 V까지입니다. 5 V로 제한해서 계산합니다.")
        pe_vp = 5.0
    if CONTACTS[pe_contact] == "leaky":
        leaky_R = st.select_slider("누설 패드 저항", [1e3, 1e4, 1e5, 1e6, 1e7], 1e5, format_func=lambda x: f"{x:.0e} Ω", key="lr3" + k)
    tt, vv, ii, E, P, clp = sim_pe(dev, pe_vp, FREQS[pe_f], pe_ir, contact=CONTACTS[pe_contact], leaky_R=leaky_R)
    pe_code, pe_msg = diagnose_pe(pe_vp, ii, E, P, clp, dev, pe_ir, FREQS[pe_f])
    overlay = st.checkbox("11/19 실측 겹쳐 보기", True, key="peo" + k)
    f, ax = fig(1, 2, w=10, h=3.8)
    ax[0].plot(E, P, color=PALETTE["model"], lw=2, label="시뮬레이션")
    ax[1].plot((tt - tt[0]) * 1e3, ii * 1e3, color=PALETTE["model"], lw=1.5, label="I 시뮬")
    recs = MEAS.get(("PE", name), [])
    if overlay and recs:
        df = recs[0]["blocks"][0].df
        Vm, Qm, Im = df["Voltage"].values, df["Charge"].values, df["Current"].values
        Pm = (Qm - 0.5 * (np.nanmax(Qm) + np.nanmin(Qm))) / (dev.area * 1e4) * 1e6
        ax[0].plot(Vm / (dev.gap * 100) / 1e3, Pm, ".", ms=2, color=PALETTE["measured"], label=f"실측 {recs[0]['file'][:22]}")
        tm = np.arange(len(Im)) / 400.0          # 1 kHz, 400점/주기 -> ms
        ax[1].plot(tm[:400], Im[:400] * 1e3, ".", ms=2, color=PALETTE["measured"], label="I 실측")
    elif overlay:
        st.caption(f"{name}의 11/19 P–E 실측 파일은 없습니다 (MFBM2/4/8만 있음).")
    ax[0].set_xlabel("E 평균 (kV/cm)"); ax[0].set_ylabel("P (µC/cm²)"); ax[0].legend()
    ax[1].set_xlabel("t (ms)"); ax[1].set_ylabel("I (mA)"); ax[1].legend()
    lim = EMPIRICAL["clip_1mA" if pe_ir == "1 mA" else "clip_10mA"][0] * 1e3
    ax[1].axhline(lim, color=PALETTE["bad"], lw=0.8, ls="--"); ax[1].axhline(-lim, color=PALETTE["bad"], lw=0.8, ls="--")
    st.pyplot(f)
    badge(pe_code, pe_msg)
    st.caption("빨간 점선 = 전류 레인지 포화값. 실측 P는 전하를 그대로 면적으로 나눈 값이라, 쇼트 데이터에서는 물리적 분극이 아닙니다.")

# ------------------------------------------------------------------ 점검
with tab_chk:
    st.markdown("현재 세 탭의 설정으로 **'nF가 확인된 패드에서만 P–E를 찍는다'** 규칙을 점검합니다.")
    rows = [
        ("0", "프로브를 띄운 상태로 기준선 측정", "수동 확인", "4284A pF, WGFMU µA 이하가 나와야 배선이 정상"),
        ("1", "4284A로 C 확인 (같은 패드)", "통과" if cv_code == "ok" else "실패",
         cv_msg if cv_code != "ok" else "nF와 D<0.1 확인. 프로브를 그대로 두고 다음 단계로"),
        ("2", "C–V bias가 4284A 한계 안", "통과" if cv_vb <= EMPIRICAL["lcr_bias_limit"][0] else "실패",
         f"±{cv_vb} V (한계 ±{EMPIRICAL['lcr_bias_limit'][0]} V)"),
        ("3", "HRSMU I–V에서 컴플라이언스 미도달", "통과" if iv_code != "short" else "실패", iv_msg),
        ("4", "P–E Vp ≥ 1.2 × Vc", "통과" if pe_vp >= 1.2 * dev.vc_apparent else "실패",
         f"Vp {pe_vp:.1f} V, 1.2×Vc = {1.2*dev.vc_apparent:.2f} V"),
        ("5", "P–E 전류가 레인지 안", "통과" if not clp.any() else "실패",
         "포화 없음" if not clp.any() else "Irange를 올리거나, 쇼트면 패드 교체"),
        ("6", "P–E 루프 판정", "통과" if pe_code == "ok" else "실패", pe_msg),
    ]
    df = pd.DataFrame(rows, columns=["단계", "항목", "결과", "설명"])
    st.dataframe(df, hide_index=True, use_container_width=True)
    n_pass = (df["결과"] == "통과").sum()
    if n_pass == 6:
        st.success("모든 자동 점검 통과: 이 조건이면 강유전 루프를 얻을 수 있습니다.")
    else:
        st.error(f"자동 점검 6개 중 {n_pass}개 통과. '실패' 단계부터 고치세요.")
