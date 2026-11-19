"""
측정 장비 시뮬레이터 + 자동 판정
- HRSMU DC I-V (B1500A)
- 4284A LCR C-V (Cp-D)
- WGFMU FERAM Hysteresis (삼각파, 전류 적분)

'연결 상태(contact)'는 11/17, 11/19 측정에서 실제로 겪은 상황을 모델로 옮긴 것이다.
경험값(empirical)은 EMPIRICAL 딕셔너리에 모아 두고 출처를 적었다.
"""
from __future__ import annotations

import numpy as np
from physics import Device, quasistatic_qv, triangle, loop_metrics, small_signal_c

CONTACTS = {
    "정상 접촉": "normal",
    "미접촉 (open)": "open",
    "막 관통 (Pt-Pt, 수 Ohm)": "punch",
    "누설 패드 (kOhm~MOhm)": "leaky",
    "장비/지그 경로 단락": "path_short",
}

EMPIRICAL = {
    "floor_R": (5e10, "11/19 HRSMU: 시편 5종이 같은 3 V에서 47~67 pA -> 측정계 바닥 약 50 GOhm"),
    "relax_pA": (45e-12, "11/19 HRSMU: 스윕 시작 직후 약 50 pA 과도(이완) 전류"),
    "stray_C": (1.5e-12, "11/19 4284A open 패드: 0.5~2.2 pF"),
    "punch_R": (3.0, "11/19 Pattern Editor: 6.6 mV에서 1.2~2.5 mA -> 2~5 Ohm"),
    "path_R_lcr": (10.0, "11/19 4284A short 파일: Rp = 1/(w Cp D) 약 9~10 Ohm (시편 무관)"),
    "path_R_wgfmu": (2.5, "11/19 Pattern Editor: 20 mV에서 9.3 mA -> 약 2 Ohm"),
    "clip_1mA": (1.156e-3, "11/19 FERAM/Pattern: 1 mA 레인지 포화값"),
    "clip_10mA": (11.4e-3, "11/19 Pattern Editor: 10 mA 레인지 포화값"),
    "lcr_bias_limit": (2.3, "11/19 4284A: +/-2.3 V 넘는 바이어스는 9.9E+37 overflow"),
    "v_sag_clip": (0.85, "11/19 FERAM: 전류 포화 시 Vp 1 V -> 실제 0.83~0.88 V"),
}


def _shunt_R(contact: str, leaky_R: float, instrument: str):
    if contact == "punch":
        return EMPIRICAL["punch_R"][0]
    if contact == "leaky":
        return leaky_R
    if contact == "path_short":
        return EMPIRICAL["path_R_lcr"][0] if instrument == "lcr" else EMPIRICAL["path_R_wgfmu"][0]
    return np.inf


# ---------------------------------------------------------------------------
# 1) HRSMU I-V
# ---------------------------------------------------------------------------
def sim_iv(dev: Device, vmax: float, npts: int = 198, compliance: float = 0.1,
           contact: str = "normal", leaky_R: float = 1e5, double: bool = False, seed: int = 1):
    rng = np.random.default_rng(seed)
    v = np.linspace(-vmax, vmax, npts)
    if double:
        v = np.concatenate([v, v[::-1][1:]])
    i = v / EMPIRICAL["floor_R"][0]                              # 측정계 바닥 (항상 존재)
    if contact != "open":
        i = i + v / dev.r_film                                  # 막 누설
    R = _shunt_R(contact, leaky_R, "smu")
    if np.isfinite(R):
        i = i + v / R
    k = np.arange(len(v))
    i = i + np.sign(v[0]) * EMPIRICAL["relax_pA"][0] * np.exp(-k / 4.0)   # 시작 이완 전류
    i = i + rng.normal(0, 2e-12, len(v))
    clipped = np.abs(i) >= compliance
    i = np.clip(i, -compliance, compliance)
    return v, i, clipped


def diagnose_iv(v, i, clipped, dev: Device):
    if clipped.any():
        return "short", "컴플라이언스 도달: 쇼트 또는 심한 누설. 즉시 중단하고 패드를 바꾸세요."
    sel = np.abs(v) > 0.3 * np.abs(v).max()
    g = np.median(np.abs(i[sel] / v[sel]))
    R = 1 / g if g > 0 else np.inf
    floor = EMPIRICAL["floor_R"][0]
    if R > floor / 3:
        return ("floor", f"유효 저항 {R:.1e} Ohm: 측정계 바닥(약 {floor:.0e} Ohm)과 같은 수준. "
                "막이 잘 절연된 것인지 프로브가 안 닿은 것인지 I-V만으로는 구분할 수 없어요. "
                "같은 패드에서 4284A로 nF가 나오는지 확인하세요.")
    if R > 1e8:
        return "ok", f"유효 저항 {R:.1e} Ohm: 측정 가능한 막 누설입니다."
    return "leaky", f"유효 저항 {R:.1e} Ohm: 누설이 큰 패드입니다. P-E 루프가 바나나 모양이 될 수 있어요."


# ---------------------------------------------------------------------------
# 2) 4284A C-V (Cp-D)
# ---------------------------------------------------------------------------
def sim_cv(dev: Device, vbias: float, freq: float = 10e3, npts: int = 51,
           contact: str = "normal", leaky_R: float = 1e5, seed: int = 2):
    rng = np.random.default_rng(seed)
    up = np.linspace(-vbias, vbias, npts)
    v = np.concatenate([up, up[::-1]])
    rising = np.concatenate([np.ones(npts, bool), np.zeros(npts, bool)])
    w = 2 * np.pi * freq
    if contact == "open":
        C = np.full_like(v, EMPIRICAL["stray_C"][0])
        G = w * C * 0.3
    else:
        C = small_signal_c(v, dev, rising)
        G = w * C * 0.02 + 1 / dev.r_film
        R = _shunt_R(contact, leaky_R, "lcr")
        if np.isfinite(R):
            G = G + 1 / R
    Y = G + 1j * w * C
    # 측정 잡음: 위상 잡음 + 작은 절대 잡음 (open/short 일 때 지배적)
    # 위상 잡음 2.5e-4 rad: 10 Ohm 쇼트 + 1 kHz 에서 Cp 잡음 약 +/-4 nF -> 11/19 short 파일처럼 C 부호가 랜덤
    sig = 2.5e-4
    ph = rng.normal(0, 1, len(v)) * sig
    Ym = np.abs(Y) * (1 + rng.normal(0, 5e-4, len(v))) * np.exp(1j * (np.angle(Y) + ph))
    Ym = Ym + w * 0.05e-12 * (rng.normal(size=len(v)) + 1j * rng.normal(size=len(v)))
    Cp = Ym.imag / w
    D = Ym.real / Ym.imag
    over = np.abs(v) > EMPIRICAL["lcr_bias_limit"][0]
    Cp[over] = np.nan
    D[over] = np.nan
    return v, Cp, D, over


def diagnose_cv(v, Cp, D, over, dev: Device):
    msg_over = ""
    if over.any():
        msg_over = f" (+/-{EMPIRICAL['lcr_bias_limit'][0]} V 밖 {over.sum()}점은 overflow라 버려짐)"
    ok = ~np.isnan(Cp)
    if not ok.any():
        return "overflow", "모든 점이 바이어스 한계 밖입니다. Vbias를 +/-2 V 이내로 줄이세요."
    c, d = np.median(Cp[ok]), np.median(np.abs(D[ok]))
    sign_flip = (Cp[ok] < 0).any() and (Cp[ok] > 0).any()
    if c < 50e-12 and d < 20:
        return "open", f"C 약 {c*1e12:.1f} pF: 프로브가 막에 닿지 않았어요." + msg_over
    if d > 10 or sign_flip:
        w_est = Cp[ok]
        return ("short", f"|D| 중앙값 {d:.0f}, C 부호 뒤바뀜={sign_flip}: 저항 경로가 커패시터를 덮었어요. "
                "Rp = 1/(w*Cp*D)가 수십 Ohm 이하이면 쇼트입니다." + msg_over)
    if d > 0.1:
        return "leaky", f"C {c*1e9:.2f} nF, D {d:.2f}: 누설이 큰 패드. 주파수를 100 kHz~1 MHz로 올려 보세요." + msg_over
    expected = dev.c_lin
    ratio = c / expected
    return ("ok", f"C {c*1e9:.2f} nF (예상 {expected*1e9:.2f} nF의 {ratio*100:.0f}%), D {d:.3f}: 정상 패드. "
            "이 패드에서 P-E를 측정하세요." + msg_over)


# ---------------------------------------------------------------------------
# 3) WGFMU FERAM Hysteresis
# ---------------------------------------------------------------------------
IRANGES = {"1 mA": "clip_1mA", "10 mA": "clip_10mA"}


def sim_pe(dev: Device, vp: float, freq: float = 1e3, irange: str = "1 mA",
           contact: str = "normal", leaky_R: float = 1e5, npts: int = 400, seed: int = 3):
    rng = np.random.default_rng(seed)
    t, v = triangle(vp, freq, npts, cycles=2)
    if contact == "open":
        Q = EMPIRICAL["stray_C"][0] * v
    else:
        Q, _, _ = quasistatic_qv(v, dev)
    i = np.gradient(Q, t)
    if contact != "open":
        i = i + v / dev.r_film
    R = _shunt_R(contact, leaky_R, "wgfmu")
    if np.isfinite(R):
        i = i + v / R
    lim = EMPIRICAL[IRANGES[irange]][0]
    clipped = np.abs(i) >= lim
    i_meas = np.clip(i, -lim, lim) + rng.normal(0, lim * 2e-4, len(i))
    v_meas = np.where(clipped, v * EMPIRICAL["v_sag_clip"][0], v)
    # 두 번째 주기만 사용 (첫 주기 = preset)
    s = slice(npts, 2 * npts)
    tt, vv, ii = t[s], v_meas[s], i_meas[s]
    dt = np.gradient(tt)
    q = np.cumsum(ii * dt)
    q = q - 0.5 * (q.max() + q.min())
    P_uC = q / (dev.area * 1e4) * 1e6          # C/cm2 -> uC/cm2
    E_kV = vv / (dev.gap * 100) / 1e3           # V/cm -> kV/cm (stack 평균)
    return tt, vv, ii, E_kV, P_uC, clipped[s]


def diagnose_pe(vp, ii, E_kV, P_uC, clipped, dev: Device, irange: str, freq: float = 1e3):
    frac = clipped.mean()
    i_expect = dev.c_lin * 4 * vp * freq
    if np.abs(ii).max() < 0.05 * i_expect:
        return ("open", f"최대 전류 {np.abs(ii).max()*1e6:.3f} uA: 예상 충전전류 {i_expect*1e6:.0f} uA의 5% 미만. "
                "프로브가 막에 닿지 않았어요.")
    if frac > 0.2:
        lim = EMPIRICAL[IRANGES[irange]][0] * 1e3
        return ("short", f"전류가 {frac*100:.0f}% 구간에서 {lim:.3g} mA로 잘림: 쇼트/누설 경로. "
                "이 데이터의 'Pr'은 포화전류 x 시간이라 물리량이 아니에요.")
    if frac > 0:
        return ("clip", f"{frac*100:.0f}% 구간에서 전류가 잘림: Irange를 한 단계 올리거나 주파수를 낮추세요.")
    Pr, Ec = loop_metrics(E_kV, P_uC)
    if vp < 1.2 * dev.vc_apparent:
        return ("subvc", f"Vp {vp:.1f} V < 1.2 x Vc({dev.vc_apparent:.2f} V): 분극이 다 뒤집히지 않아요. "
                f"측정 Pr {Pr:.2f} uC/cm2는 과소평가입니다.")
    if Pr < 0.2:
        return "linear", f"Pr {Pr:.2f} uC/cm2: 거의 직선. 강유전상이 부족하거나(2차상, 열처리) 반전이 안 일어났어요."
    return "ok", f"루프 확인: Pr {Pr:.2f} uC/cm2, Ec {Ec:.0f} kV/cm (stack 평균 전계 기준)."


STATUS_STYLE = {
    "ok": ("정상", "#1b7f4b"),
    "floor": ("바닥신호", "#b7791f"),
    "open": ("Open", "#2b6cb0"),
    "short": ("Short", "#c53030"),
    "leaky": ("Leaky", "#dd6b20"),
    "clip": ("레인지 포화", "#dd6b20"),
    "subvc": ("Vp 부족", "#b7791f"),
    "linear": ("직선", "#b7791f"),
    "overflow": ("Overflow", "#718096"),
}
