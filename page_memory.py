import numpy as np
import pandas as pd
import streamlit as st

from physics import Device
from mem_model import (cell_device, read_margin_curve, Kinetics, write_time, energy_per_bit,
                         Reliability, SCENARIOS, scenario_check, YEAR, bto_field_at)
from plotting import fig, nominor, DEVICE_COLORS, PALETTE

mat = st.session_state["material"]
st.title("차세대 통신 메모리로서의 가능성")
st.markdown("""
6G·IoT·위성 통신 단말은 **전원이 자주 끊기고, 배터리로 오래 버텨야 하고, 방사선 같은 가혹한 환경**에 놓입니다.
이런 곳에는 껐다 켜도 데이터가 남고(비휘발), 쓰기 에너지가 작고, 쓰기 횟수에 강한 **강유전 메모리(FeRAM)**가 맞습니다.
이 페이지는 우리 커패시터의 물성을 **1T1C FeRAM 셀 크기로 축소**했을 때의 성능을 계산하고, 통신 응용별 요구치와 비교합니다.
""")
st.warning("여기 숫자는 **모델 투영값**입니다. 측정으로 확정된 값이 아니며, Pr·Ec·스위칭 속도·피로 특성을 실측하면 "
           "사이드바와 아래 파라미터를 바꿔 다시 계산하세요.")

c1, c2, c3 = st.columns(3)
coats = c1.selectbox("BTO 코팅 횟수", [2, 4, 6, 8], index=0)
area = c2.select_slider("셀 커패시터 면적 (µm²)", [0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0], 1.0)
vdd = c3.slider("동작 전압 Vdd (V)", 0.5, 5.0, 3.0, 0.1)

devs = {s: Device(s, coats, mat) for s in ("MFM", "MFBM")}
cells = {s: cell_device(d, area) for s, d in devs.items()}

tab1, tab2, tab3, tab4 = st.tabs(["① 읽기 신호", "② 쓰기 속도", "③ 에너지 · 신뢰성", "④ 통신 응용 적합성"])

# ---------------------------------------------------------------- 읽기
with tab1:
    st.markdown("읽기: plate에 Vdd를 걸면 '1'(반대 분극) 셀은 분극이 뒤집히며 큰 전하를, '0' 셀은 작은 전하를 비트라인으로 내보냅니다. "
                "두 경우의 비트라인 전압 차이 **ΔV**가 감지 증폭기 여유(보통 ≥ 100 mV)보다 커야 읽힙니다.")
    cbl = np.logspace(np.log10(5e-15), np.log10(1e-12), 18)
    f, ax = fig(1, 2, w=10, h=3.8)
    rows = []
    for s, dc in cells.items():
        v1, v0, dv = read_margin_curve(dc, vdd, cbl)
        col = DEVICE_COLORS[f"{s}{coats}"]
        ax[0].semilogx(cbl * 1e15, dv * 1e3, "o-", color=col, ms=3, label=f"{s}{coats}")
        ax[1].semilogx(cbl * 1e15, v1 * 1e3, "-", color=col, label=f"{s} '1'")
        ax[1].semilogx(cbl * 1e15, v0 * 1e3, "--", color=col, label=f"{s} '0'")
        i300 = np.argmin(np.abs(cbl - 300e-15))
        rows.append({"구조": f"{s}{coats}", "셀 C_lin (fF)": round(dc.c_lin * 1e15, 1),
                     "BTO 내부전계 @Vdd (kV/cm)": round(bto_field_at(dc, vdd), 0),
                     "ΔV @ C_BL 300 fF (mV)": round(dv[i300] * 1e3, 0),
                     "최대 ΔV (mV)": round(dv.max() * 1e3, 0)})
    ax[0].axhline(100, color=PALETTE["bad"], ls="--", lw=0.8); ax[0].text(6, 110, "감지 여유 100 mV", fontsize=8, color=PALETTE["bad"])
    ax[0].set_xlabel("비트라인 커패시턴스 C_BL (fF)"); ax[0].set_ylabel("ΔV = V('1') − V('0') (mV)"); ax[0].legend()
    ax[1].set_xlabel("C_BL (fF)"); ax[1].set_ylabel("비트라인 전압 (mV)"); ax[1].legend(fontsize=7)
    st.pyplot(f)
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    st.caption("상용 FeRAM은 C_BL 수백 fF에서 ΔV 수백 mV를 목표로 합니다(Kawashima 2007). MFBM은 TiO₂가 전압을 나눠 가져 "
               "같은 Vdd에서 반전이 덜 일어나고 ΔV가 작아집니다. 대신 누설이 줄면 '0' 신호의 퍼짐이 작아지는 장점이 있어요.")

# ---------------------------------------------------------------- 쓰기
with tab2:
    a, b, c, d = st.columns(4)
    t_inf = a.select_slider("t∞ (s)", [1e-10, 5e-10, 1e-9, 5e-9, 1e-8, 5e-8], 5e-9, format_func=lambda x: f"{x:.0e}")
    Ea = b.slider("활성화 전계 Ea (kV/cm)", 50, 1000, 300, 10)
    nexp = c.slider("Avrami 지수 n", 1.0, 3.0, 2.0, 0.1)
    sig = d.slider("NLS 분포 폭 σ", 0.0, 2.0, 0.6, 0.1)
    kin = Kinetics(t_inf, Ea, nexp, sig)
    st.caption("기본값은 졸-겔 다결정 BTO 가정. 에피 BTO는 약 2 ns에 반전된다는 보고가 있습니다(Jiang 2022). "
               "PUND 펄스 폭 실험으로 이 값들을 맞추는 것이 다음 측정 목표입니다.")
    ts = np.logspace(-10, -2, 300)
    f, ax = fig(1, 2, w=10, h=3.8)
    rows = []
    for s in ("MFM", "MFBM"):
        col = DEVICE_COLORS[f"{s}{coats}"]
        for vv, ls in [(vdd, "-"), (vdd * 0.6, "--")]:
            E = bto_field_at(devs[s], vv)
            ax[0].semilogx(ts, kin.switched_fraction(ts, E), ls, color=col, label=f"{s} {vv:.1f} V (E_BTO {E:.0f})")
        tsw, rc_pad, tw_pad, E = write_time(devs[s], vdd, kin)
        tsw_c, rc_c, tw_c, _ = write_time(cells[s], vdd, kin, r_driver=5e3)
        rows.append({"구조": f"{s}{coats}", "E_BTO (kV/cm)": round(E, 0), "스위칭 90% (ns)": round(tsw * 1e9, 1),
                     "현재 750 µm 패드 3RC (ns)": round(rc_pad * 1e9, 0), "패드 쓰기시간 (ns)": round(tw_pad * 1e9, 0),
                     "셀 쓰기시간 (ns)": round(tw_c * 1e9, 1)})
    ax[0].set_xlabel("펄스 폭 (s)"); ax[0].set_ylabel("반전 분율"); ax[0].legend(fontsize=7); ax[0].set_title("NLS 반전 곡선")
    Es = np.linspace(20, 600, 100)
    ax[1].loglog(Es, kin.t0(Es), color=PALETTE["model"])
    ax[1].axhline(70e-9, color="#6b7280", ls=":", lw=0.8); ax[1].text(25, 80e-9, "상용 FRAM 접근 70 ns", fontsize=8)
    nominor(ax[1]); ax[1].set_xlabel("BTO 내부 전계 (kV/cm)"); ax[1].set_ylabel("t₀ (s)"); ax[1].set_title("Merz 법칙 t₀ = t∞·exp(Ea/E)")
    st.pyplot(f)
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    st.caption("750 µm 패드는 nF급이라 50 Ω 장비에서 RC가 수백 ns~µs입니다. 그래서 지금 측정하는 스위칭 시간은 물질 한계가 아니라 "
               "RC 한계일 수 있어요. 셀 크기(fF)로 줄이면 RC는 무시되고 물질 스위칭 속도가 남습니다.")
    st.session_state["mem_tw"] = {r["구조"]: r["셀 쓰기시간 (ns)"] * 1e-9 for r in rows}

# ---------------------------------------------------------------- 에너지/신뢰성
with tab3:
    a, b, c = st.columns(3)
    N0 = a.select_slider("피로 특성 사이클 N₀", [1e6, 1e7, 1e8, 1e9, 1e10, 1e12, 1e14], 1e9, format_func=lambda x: f"{x:.0e}")
    beta = b.slider("피로 지수 β", 0.2, 1.5, 0.5, 0.1)
    mdec = c.slider("보존: 10배 시간당 분극 감소", 0.0, 0.1, 0.02, 0.005)
    rel = Reliability(N0, beta, mdec)
    N = np.logspace(0, 16, 200)
    t = np.logspace(0, np.log10(20 * YEAR), 200)
    f, ax = fig(1, 3, w=12, h=3.6)
    ax[0].semilogx(N, rel.fatigue(N), color=PALETTE["model"])
    ax[0].axhline(0.8, color=PALETTE["bad"], ls="--", lw=0.8)
    ax[0].axvline(1e10, color="#6b7280", ls=":", lw=0.8); ax[0].text(1.3e10, 0.3, "Zhao 2025\n10¹⁰ 무피로", fontsize=7)
    ax[0].axvline(1e14, color="#6b7280", ls=":", lw=0.8); ax[0].text(1.3e14, 0.5, "상용\n10¹⁴", fontsize=7)
    ax[0].set_xlabel("쓰기 사이클"); ax[0].set_ylabel("Pr / Pr₀"); ax[0].set_title("피로")
    ax[1].semilogx(t / YEAR, rel.retention(t), color=PALETTE["model"])
    ax[1].axvline(10, color="#6b7280", ls=":", lw=0.8); ax[1].set_xlabel("시간 (년)"); ax[1].set_ylabel("P / P₀"); ax[1].set_title("보존")
    for s, dc in cells.items():
        vs = np.linspace(0.5, 5, 30)
        ax[2].plot(vs, [energy_per_bit(dc, v, 300e-15) * 1e15 for v in vs], color=DEVICE_COLORS[f"{s}{coats}"], label=f"{s}{coats}")
    ax[2].set_xlabel("Vdd (V)"); ax[2].set_ylabel("비트당 에너지 (fJ)"); ax[2].legend(); ax[2].set_title(f"쓰기 에너지 (셀 {area} µm²)")
    st.pyplot(f)
    st.session_state["mem_rel"] = (rel.cycles_to(0.8), rel.retention(10 * YEAR))
    st.write(f"Pr이 80%로 떨어지는 사이클: **{rel.cycles_to(0.8):.1e}회**, 10년 뒤 분극 유지율: **{rel.retention(10*YEAR)*100:.0f}%**")

# ---------------------------------------------------------------- 응용
with tab4:
    tw = st.session_state.get("mem_tw", {})
    n80, ret = st.session_state.get("mem_rel", (Reliability().cycles_to(0.8), Reliability().retention(10 * YEAR)))
    if not tw:
        kin = Kinetics()
        tw = {f"{s}{coats}": write_time(cells[s], vdd, kin, r_driver=5e3)[2] for s in ("MFM", "MFBM")}
    rows = []
    for sc in SCENARIOS:
        for s, t_w in tw.items():
            need, ok_s, ok_e, ok_r = scenario_check(sc, t_w, n80, ret)
            mark = lambda b: "충족" if b else "미달"
            rows.append({"응용": sc["name"], "구조": s, "요구 쓰기시간": f"{sc['write_ns']:.0e} ns",
                         "우리 셀": f"{t_w*1e9:.0f} ns", "속도": mark(ok_s),
                         "필요 사이클": f"{need:.1e}", "내구성": mark(ok_e), "보존": mark(ok_r),
                         "종합": "적합" if (ok_s and ok_e and ok_r) else "보완 필요", "왜 이 응용인가": sc["why"]})
    df = pd.DataFrame(rows)

    def hl(v):
        return {"충족": "background-color:#c6f6d5;color:#111", "적합": "background-color:#c6f6d5;color:#111",
                "미달": "background-color:#fed7d7;color:#111", "보완 필요": "background-color:#fefcbf;color:#111"}.get(v, "")
    sty = df.style
    sty = (sty.map(hl) if hasattr(sty, "map") else sty.applymap(hl))
    st.dataframe(sty, hide_index=True, use_container_width=True)
    st.markdown("""
**읽는 법**
- 패킷 버퍼(ns 쓰기, 10¹⁶회 이상)는 DRAM/SRAM의 영역이고, FeRAM의 목표가 아닙니다. 비교 기준으로 넣었어요.
- 우리 소자의 자리는 **전원 차단에 강한 로그·설정 저장, 저전력 IoT 노드, 방사선 환경 단말**입니다.
- '미달' 항목이 다음 실험 목표입니다: PUND 펄스 폭 실험으로 **스위칭 시간**을, 반복 펄스로 **피로 사이클**을 실측해서 이 표를 실측값으로 채웁니다.
""")
