"""
차세대 통신용 비휘발 메모리(FeRAM) 관점의 소자 투영 모델
-------------------------------------------------------------
우리 750 um 패드 커패시터의 물성(단위면적 기준)을 1T1C FeRAM 셀 크기로 축소해서
  (1) 읽기 신호 여유 (bitline 전압차)
  (2) 쓰기 속도 (NLS/KAI + Merz 법칙, RC 한계)
  (3) 비트당 에너지
  (4) 내구성(피로)과 보존(retention)
을 계산하고, 통신 분야 응용 요구치와 비교한다.

※ 이 모듈의 결과는 '측정값'이 아니라 '모델 투영'이다. 파라미터마다 출처 태그를 단다.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import numpy as np

from physics import Device, EPS0, quasistatic_qv, _solve_e_bto


# ---------------------------------------------------------------------------
# (1) 1T1C 읽기: plate에 Vdd, 떠 있는 bitline(C_BL)과 전하 공유
# ---------------------------------------------------------------------------
def cell_device(dev: Device, cell_area_um2: float) -> Device:
    return replace(dev, area=cell_area_um2 * 1e-12)


def read_bitline(dev_cell: Device, vdd: float, c_bl: float, state: int):
    """state=1: 저장 분극이 읽기 전압과 반대 -> 반전(큰 전하), state=0: 같은 방향 -> 비반전.
    전하 보존: Q_cell(Vdd - V_BL) - Q_cell(0) = C_BL * V_BL 를 이분법으로 푼다."""
    m = dev_cell.mat
    pr = m.Ps * np.tanh(1 / m.sharpness)
    p0 = -pr if state == 1 else pr

    def dq(vcell):
        e, p = _solve_e_bto(vcell, dev_cell, p0, rising=True)
        e0, p00 = _solve_e_bto(0.0, dev_cell, p0, rising=True)
        q = (EPS0 * m.eps_bto_eff * e + p) * dev_cell.area
        q0 = (EPS0 * m.eps_bto_eff * e0 + p00) * dev_cell.area
        return q - q0

    lo, hi = 0.0, vdd
    for _ in range(60):
        vbl = 0.5 * (lo + hi)
        if dq(vdd - vbl) - c_bl * vbl > 0:
            lo = vbl
        else:
            hi = vbl
    return 0.5 * (lo + hi)


def read_margin_curve(dev_cell: Device, vdd: float, c_bl_list):
    v1 = np.array([read_bitline(dev_cell, vdd, c, 1) for c in c_bl_list])
    v0 = np.array([read_bitline(dev_cell, vdd, c, 0) for c in c_bl_list])
    return v1, v0, v1 - v0


# ---------------------------------------------------------------------------
# (2) 스위칭 속도: KAI s(t) = 1 - exp(-(t/t0)^n),  Merz t0(E) = t_inf * exp(Ea/E)
# ---------------------------------------------------------------------------
@dataclass
class Kinetics:
    t_inf: float = 5e-9        # s   (가정: 졸-겔 다결정, 에피 BTO는 ~1e-10 s급)
    Ea_kVcm: float = 300.0     # kV/cm 활성화 전계 (가정, 보통 Ec의 5~10배)
    n: float = 2.0             # Avrami 지수 (박막 2D 성장)
    nls_sigma: float = 0.6     # NLS: ln(t0) 분포 폭 (다결정 무질서도)

    def t0(self, E_kVcm):
        E = np.maximum(np.asarray(E_kVcm, float), 1e-3)
        return self.t_inf * np.exp(self.Ea_kVcm / E)

    def switched_fraction(self, t, E_kVcm, n_grid=41):
        """NLS: t0가 로그정규 분포를 갖는 KAI 영역들의 합."""
        t = np.asarray(t, float)
        z = np.linspace(-3, 3, n_grid)
        w = np.exp(-z ** 2 / 2)
        w /= w.sum()
        t0 = self.t0(E_kVcm) * np.exp(self.nls_sigma * z)
        s = 1 - np.exp(-(t[:, None] / t0[None, :]) ** self.n)
        return (s * w).sum(axis=1)

    def t_switch(self, E_kVcm, target=0.9):
        ts = np.logspace(-12, 0, 600)
        s = self.switched_fraction(ts, E_kVcm)
        idx = np.searchsorted(s, target)
        return ts[min(idx, len(ts) - 1)]


def bto_field_at(dev: Device, v: float) -> float:
    """외부 전압 v 에서 BTO 내부 전계 (kV/cm), 분극 0 근처 선형 분압."""
    share_b = 1 - (dev.tio2_voltage_share if dev.t_tio2 > 0 else 0)
    return v * share_b / dev.t_bto / 1e5


def write_time(dev: Device, v: float, kin: Kinetics, r_driver: float = 50.0):
    """쓰기 시간 = max(스위칭 90%, 3*RC) 로 근사."""
    E = bto_field_at(dev, v)
    tsw = kin.t_switch(E)
    rc = r_driver * dev.c_lin
    return tsw, 3 * rc, max(tsw, 3 * rc), E


# ---------------------------------------------------------------------------
# (3) 에너지, (4) 피로/보존
# ---------------------------------------------------------------------------
def energy_per_bit(dev_cell: Device, v: float, c_bl: float):
    m = dev_cell.mat
    pr = m.Ps * np.tanh(1 / m.sharpness)
    e_switch = 2 * pr * dev_cell.area * v
    e_lin = dev_cell.c_lin * v ** 2
    e_bl = c_bl * (0.3 * v) ** 2
    return e_switch + e_lin + e_bl


@dataclass
class Reliability:
    N0: float = 1e9          # 피로 특성 사이클 (가정: 졸-겔 Pt 전극 BTO)
    beta: float = 0.5
    m_decade: float = 0.02   # 보존: 10배 시간마다 분극 감소 비율 (가정)

    def fatigue(self, N):
        N = np.asarray(N, float)
        return 1 / (1 + (N / self.N0) ** self.beta)

    def cycles_to(self, ratio=0.8):
        return self.N0 * ((1 / ratio) - 1) ** (1 / self.beta)

    def retention(self, t_s, t_ref=1.0):
        t = np.maximum(np.asarray(t_s, float), t_ref)
        return np.clip(1 - self.m_decade * np.log10(t / t_ref), 0, 1)


# ---------------------------------------------------------------------------
# 통신 분야 응용 시나리오 (요구치는 공개 사양/일반 설계값 기준의 대략값)
# ---------------------------------------------------------------------------
YEAR = 3.156e7
SCENARIOS = [
    dict(name="IoT 센서 노드 (NB-IoT/LoRa) 데이터 로깅",
         write_ns=1e5, writes_per_s=1.0, years=10, retention_yr=10,
         why="배터리 구동, 전원 차단 잦음 -> 비휘발 + 저에너지 쓰기가 핵심"),
    dict(name="5G/6G 기지국·RU 설정/이벤트 로그",
         write_ns=1e3, writes_per_s=100.0, years=10, retention_yr=10,
         why="정전 순간까지의 로그를 즉시 기록 (블랙박스형)"),
    dict(name="엣지 AI 단말 가중치·상태 저장",
         write_ns=1e2, writes_per_s=1e3, years=5, retention_yr=5,
         why="읽기 위주, 전원 껐다 켜도 즉시 재개 (instant-on)"),
    dict(name="저궤도(LEO) 위성 통신 단말",
         write_ns=1e3, writes_per_s=10.0, years=7, retention_yr=7,
         why="방사선 환경: 강유전 메모리는 전하 저장형보다 방사선에 강함"),
    dict(name="고속 패킷 버퍼 (참고: DRAM/SRAM 영역)",
         write_ns=1.0, writes_per_s=1e8, years=5, retention_yr=0,
         why="ns 쓰기 + 10^16회 이상 -> FeRAM 목표 영역 아님 (비교 기준)"),
]


def scenario_check(sc, t_write, n_cycles_ok, retention_10y):
    need_cycles = sc["writes_per_s"] * sc["years"] * YEAR
    ok_speed = t_write <= sc["write_ns"] * 1e-9
    ok_endur = n_cycles_ok >= need_cycles
    ok_ret = (sc["retention_yr"] == 0) or (retention_10y >= 0.7)
    return need_cycles, ok_speed, ok_endur, ok_ret
