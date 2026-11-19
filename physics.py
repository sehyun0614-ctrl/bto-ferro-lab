"""
BaTiO3 강유전 커패시터 물리 모델
- MFM  : Pt / BTO / Pt
- MFBM : Pt / TiO2(buffer) / BTO / Pt   (직렬 유전층)

단위 규칙: 내부 계산은 SI(m, V, C, F). 화면 표시만 nm, kV/cm, uC/cm2, nF로 바꾼다.
모든 '가정값'은 Material 기본값에 모아 두었고, 실측으로 바뀌면 여기만 고치면 된다.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import numpy as np

EPS0 = 8.854e-12          # F/m
PAD_DIAMETER = 750e-6     # m  (상부 Pt 패드 지름)
A_PAD = np.pi * (PAD_DIAMETER / 2) ** 2   # 4.418e-7 m2 = 4.42e-3 cm2
T_COAT_BTO = 43.8e-9      # m, 1회 코팅 두께 (11/11 단면 SEM, 3회 131.37 nm)
T_TIO2 = 32.69e-9         # m, TiO2 1회 코팅 두께
E_TARGET = 250e3 * 100    # 250 kV/cm -> V/m (측정 목표 최대 전계)


@dataclass
class Material:
    """물성값. source 딕셔너리에 '실측' / '가정' / '문헌' 출처를 같이 적는다."""
    eps_bto: float = 300.0          # BTO 유전율
    eps_tio2: float = 40.0          # TiO2 유전율 (anatase, 450 C)
    Ps_uC: float = 6.0              # 포화 분극 uC/cm2 (졸-겔 무배향 BTO 수준)
    Ec_kVcm: float = 40.0           # BTO 항전계 kV/cm
    sharpness: float = 0.5          # 스위칭 폭 delta = sharpness * Ec
    second_phase: float = 0.0       # BaCO3 등 2차상 부피분율 (0~0.3)
    eps_second: float = 8.0         # 2차상 유전율 (BaCO3 ~ 8)
    rho_film: float = 1e12          # 막 비저항 Ohm*m (누설 모델)
    source: dict = field(default_factory=lambda: {
        "eps_bto": "가정 (졸-겔 BTO 문헌 범위 200~500)",
        "eps_tio2": "가정 (anatase 문헌값)",
        "Ps_uC": "가정 (Hosokura 2015: CSD BTO 0.9~3 uC/cm2 Pr)",
        "Ec_kVcm": "가정 (졸-겔 BTO 30~60 kV/cm)",
        "second_phase": "XRD 2차상 피크 근거, 분율은 가정",
        "rho_film": "11/19 HRSMU I-V에서 하한만 확인 (측정계 바닥 50 GOhm)",
    })

    # 2차상 반영 유효값 -------------------------------------------------
    @property
    def eps_bto_eff(self) -> float:
        f = self.second_phase
        # 무작위 분산 2차상: Maxwell-Garnett 근사
        em, ei = self.eps_bto, self.eps_second
        return em * (ei + 2 * em + 2 * f * (ei - em)) / (ei + 2 * em - f * (ei - em))

    @property
    def Ps(self) -> float:            # C/m2
        return self.Ps_uC * 1e-2 * (1 - self.second_phase)

    @property
    def Ec(self) -> float:            # V/m
        return self.Ec_kVcm * 1e5


@dataclass
class Device:
    structure: str = "MFM"          # "MFM" or "MFBM"
    coats: int = 4
    mat: Material = field(default_factory=Material)
    area: float = A_PAD

    @property
    def name(self) -> str:
        return f"{self.structure}{self.coats}"

    @property
    def t_bto(self) -> float:
        return self.coats * T_COAT_BTO

    @property
    def t_tio2(self) -> float:
        return T_TIO2 if self.structure == "MFBM" else 0.0

    @property
    def gap(self) -> float:
        return self.t_bto + self.t_tio2

    @property
    def vmax(self) -> float:
        """250 kV/cm 평균전계에 해당하는 전압 (0.1 V 단위 반올림)."""
        return round(E_TARGET * self.gap, 1)

    # 선형 정전용량 -------------------------------------------------------
    @property
    def c_bto(self) -> float:
        return EPS0 * self.mat.eps_bto_eff * self.area / self.t_bto

    @property
    def c_tio2(self) -> float:
        return EPS0 * self.mat.eps_tio2 * self.area / self.t_tio2 if self.t_tio2 > 0 else np.inf

    @property
    def c_lin(self) -> float:
        if self.t_tio2 == 0:
            return self.c_bto
        return 1 / (1 / self.c_bto + 1 / self.c_tio2)

    @property
    def vc_apparent(self) -> float:
        """BTO 내부 전계가 Ec가 되는 외부 전압 (분극 0 기준, TiO2 직렬 분압 포함)."""
        m = self.mat
        return m.Ec * (self.t_bto + self.t_tio2 * m.eps_bto_eff / m.eps_tio2)

    @property
    def tio2_voltage_share(self) -> float:
        """선형 영역에서 TiO2가 나눠 갖는 전압 비율."""
        if self.t_tio2 == 0:
            return 0.0
        return self.c_bto / (self.c_bto + self.c_tio2)

    @property
    def r_film(self) -> float:
        return self.mat.rho_film * self.gap / self.area

    def summary(self) -> dict:
        return {
            "시편": self.name,
            "BTO (nm)": round(self.t_bto * 1e9, 1),
            "TiO2 (nm)": round(self.t_tio2 * 1e9, 2),
            "Gap (nm)": round(self.gap * 1e9, 1),
            "Vmax @250 kV/cm (V)": self.vmax,
            "예상 C (nF)": round(self.c_lin * 1e9, 2),
            "예상 Vc (V)": round(self.vc_apparent, 2),
            "TiO2 전압분담 (%)": round(self.tio2_voltage_share * 100, 0),
        }


ALL_DEVICES = [(s, n) for s in ("MFM", "MFBM") for n in (2, 4, 6, 8)]


# ---------------------------------------------------------------------------
# 강유전 P-E: 히스테리시스 분기(branch) + 이력(history) 규칙
#   상승 분기 P_up(E)   = Ps*tanh((E - Ec)/d)
#   하강 분기 P_down(E) = Ps*tanh((E + Ec)/d)
#   전계가 오를 때 P = max(P_이전, P_up(E))  -> Ec 아래에서는 반전 없음
#   전계가 내릴 때 P = min(P_이전, P_down(E))
# 그래서 Vp < Vc 이면 루프가 열리지 않고 선형 유전체처럼 보인다(실제 물리와 일치).
# ---------------------------------------------------------------------------
def _p_branch(E, mat: Material, rising: bool):
    d = mat.sharpness * mat.Ec
    shift = mat.Ec if rising else -mat.Ec
    return mat.Ps * np.tanh((E - shift) / d)


def _solve_e_bto(V, dev: Device, p_prev: float, rising: bool):
    """직렬 스택에서 BTO 내부 전계 E_B 를 이분법으로 푼다.
    V = E_B*t_B + D*t_T/(eps0*eps_T),  D = eps0*eps_B*E_B + P(E_B)"""
    m = dev.mat
    tB, tT = dev.t_bto, dev.t_tio2

    def P_of(E):
        pb = _p_branch(E, m, rising)
        return max(p_prev, pb) if rising else min(p_prev, pb)

    if tT == 0:
        E = V / tB
        return E, P_of(E)

    def f(E):
        D = EPS0 * m.eps_bto_eff * E + P_of(E)
        return E * tB + D * tT / (EPS0 * m.eps_tio2) - V

    span = abs(V) / tB + 5 * m.Ec + 1e6
    lo, hi = -span, span
    for _ in range(70):
        mid = 0.5 * (lo + hi)
        if f(mid) > 0:
            hi = mid
        else:
            lo = mid
    E = 0.5 * (lo + hi)
    return E, P_of(E)


def quasistatic_qv(V: np.ndarray, dev: Device, p0: float | None = None):
    """전압 파형 V(t)에 대한 전극 전하 Q(t), BTO 내부 전계, 분극.
    p0: 시작 분극 (기본: -Pr 상태에서 출발)"""
    m = dev.mat
    p = -m.Ps * np.tanh(m.Ec / (m.sharpness * m.Ec)) if p0 is None else p0
    Q = np.empty_like(V, dtype=float)
    EB = np.empty_like(V, dtype=float)
    P = np.empty_like(V, dtype=float)
    prev_v = V[0]
    rising = True
    for i, v in enumerate(V):
        if v > prev_v:
            rising = True
        elif v < prev_v:
            rising = False
        e, p = _solve_e_bto(v, dev, p, rising)
        EB[i], P[i] = e, p
        Q[i] = (EPS0 * m.eps_bto_eff * e + p) * dev.area
        prev_v = v
    return Q, EB, P


def triangle(vp: float, freq: float, n_per_cycle: int = 400, cycles: int = 2, start_phase="0"):
    """0 -> +Vp -> 0 -> -Vp -> 0 삼각파 (FERAM Hysteresis 기본 파형)"""
    t = np.arange(n_per_cycle * cycles) / (n_per_cycle * freq)
    ph = (t * freq) % 1.0
    v = np.where(ph < 0.25, 4 * ph, np.where(ph < 0.75, 2 - 4 * ph, 4 * ph - 4)) * vp
    return t, v


def loop_metrics(E_kVcm: np.ndarray, P_uC: np.ndarray):
    """한 주기 P-E 루프에서 Pr(평균), Ec(평균)를 뽑는다."""
    def crossings(x, y):
        out = []
        for i in range(len(y) - 1):
            if y[i] == 0:
                out.append(x[i])
            elif y[i] * y[i + 1] < 0:
                out.append(x[i] - y[i] * (x[i + 1] - x[i]) / (y[i + 1] - y[i]))
        return out
    pr = crossings(P_uC, E_kVcm)          # E=0 에서의 P
    ec = crossings(E_kVcm, P_uC)          # P=0 에서의 E
    Pr = (max(pr) - min(pr)) / 2 if len(pr) >= 2 else 0.0
    Ec = (max(ec) - min(ec)) / 2 if len(ec) >= 2 else 0.0
    return Pr, Ec


def small_signal_c(V: np.ndarray, dev: Device, rising: np.ndarray):
    """C-V(소신호) 현상론 모델: 가역 유전율이 +/-Ec 근처에서 커지는 나비 모양.
    eps_rev(E) = eps_B * (1 + a / (1 + ((E -/+ Ec)/w)^2)),  a 는 강유전 분율에 비례."""
    m = dev.mat
    a = 0.25 * (m.Ps_uC / 6.0) * (1 - m.second_phase)
    w = 0.6 * m.Ec
    out = np.empty_like(V, dtype=float)
    for i, (v, r) in enumerate(zip(V, rising)):
        # BTO 내부 전계: 선형 분압 근사
        share_b = 1 - dev.tio2_voltage_share
        E = v * share_b / dev.t_bto
        ec = m.Ec if r else -m.Ec
        eps_r = m.eps_bto_eff * (1 + a / (1 + ((E - ec) / w) ** 2))
        cb = EPS0 * eps_r * dev.area / dev.t_bto
        out[i] = cb if dev.t_tio2 == 0 else 1 / (1 / cb + 1 / dev.c_tio2)
    return out
