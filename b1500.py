"""
Keysight EasyEXPERT(B1500A) CSV 파서 + 자동 판정
- I/V Sweep (HRSMU), CVSweep4284, FERAM Hysteresis, WGFMU Pattern Editor 를 지원
- 한 파일에 여러 블록(SetupTitle ...)이 들어 있으므로 블록 단위로 나눈다.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

from .physics import A_PAD, T_COAT_BTO, T_TIO2

OVERFLOW = 1e30


@dataclass
class Block:
    title: str = ""
    params: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)

    @property
    def df(self) -> pd.DataFrame:
        if not self.columns:
            return pd.DataFrame()
        n = len(self.columns)
        good = [r for r in self.rows if len(r) == n]
        arr = []
        for r in good:
            vals = []
            for x in r:
                x = x.strip()
                try:
                    v = float(x)
                    vals.append(np.nan if abs(v) > OVERFLOW else v)
                except ValueError:
                    vals.append(np.nan)
            arr.append(vals)
        return pd.DataFrame(arr, columns=self.columns)


def parse_text(text: str) -> list[Block]:
    blocks: list[Block] = []
    cur = None
    pending_names = None
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split(",")]
        tag = parts[0]
        if tag == "SetupTitle":
            cur = Block(title=",".join(parts[1:]))
            blocks.append(cur)
            pending_names = None
            continue
        if cur is None:
            continue
        if tag == "TestParameter":
            if len(parts) > 2 and parts[1] == "Name":
                pending_names = parts[2:]
            elif len(parts) > 2 and parts[1] == "Value" and pending_names:
                for k, v in zip(pending_names, parts[2:]):
                    cur.params.setdefault(k, v)
                pending_names = None
            elif len(parts) >= 3:
                cur.params.setdefault(parts[1], ", ".join(parts[2:]))
        elif tag == "MetaData" and len(parts) >= 2:
            key = parts[1].replace("TestRecord.", "")
            cur.meta[key] = ",".join(parts[2:]).strip()
        elif tag == "DataName":
            cur.columns = parts[1:]
            cur.rows = []
        elif tag == "DataValue":
            cur.rows.append(parts[1:])
    return blocks


def parse_file(raw: bytes | str) -> list[Block]:
    text = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else raw
    return parse_text(text)


def kind_of(blocks: list[Block]) -> str:
    t = blocks[0].title if blocks else ""
    if t.startswith("I/V Sweep"):
        return "IV"
    if t.startswith("CVSweep4284"):
        return "CV"
    if t.startswith("FERAM"):
        return "PE"
    if "Pattern Editor" in t:
        return "PATTERN"
    return "?"


SAMPLE_RE = re.compile(r"(?<![0-9])([12])[-_ ]([2468])(?![0-9])")


def guess_sample(filename: str, remarks: str) -> str:
    """Remarks 또는 파일명에서 '1-4' / '2_6' 형식을 찾아 MFM/MFBM 으로 바꾼다.
    1 = MFM, 2 = MFBM, 뒤 숫자 = 코팅 횟수 (팀 규칙). Remarks 를 우선한다."""
    for src in (remarks or "", filename):
        m = SAMPLE_RE.search(src)
        if m:
            return ("MFM" if m.group(1) == "1" else "MFBM") + m.group(2)
    return "미기재"


def gap_of(sample: str):
    m = re.match(r"(MFM|MFBM)(\d)", sample or "")
    if not m:
        return None
    return int(m.group(2)) * T_COAT_BTO + (T_TIO2 if m.group(1) == "MFBM" else 0)


# ---------------------------------------------------------------------------
# 판정
# ---------------------------------------------------------------------------
def judge(kind: str, blocks: list[Block], filename: str = ""):
    m_vp = re.search(r"Pattern_Editor_(\d\.\d)_", filename)
    vp = float(m_vp.group(1)) if m_vp else 1.0
    b = blocks[0]
    df = b.df
    if df.empty or len(df) < 3:
        return "empty", "데이터 행 없음 (헤더만 저장됨)", {}
    if kind == "IV":
        v, i = df.iloc[:, 0].values, df.iloc[:, 1].values
        comp = float(b.params.get("Measurement.Primary.Compliance", "0.1") or 0.1)
        if np.nanmax(np.abs(i)) >= 0.95 * comp:
            return "short", "컴플라이언스 도달", {}
        sel = np.abs(v) > 0.3 * np.nanmax(np.abs(v))
        R = 1 / np.nanmedian(np.abs(i[sel] / v[sel]))
        info = {"Vmax (V)": float(np.nanmax(v)), "I(+Vmax) (pA)": float(i[np.nanargmax(v)] * 1e12),
                "I(-Vmax) (pA)": float(i[np.nanargmin(v)] * 1e12), "R_eff (GOhm)": R / 1e9}
        if R > 1.5e10:
            return "floor", f"R_eff {R/1e9:.0f} GOhm: 측정계 바닥 수준 (절연 또는 미접촉)", info
        if R > 1e8:
            return "ok", f"R_eff {R/1e9:.2f} GOhm: 막 누설 측정", info
        return "leaky", f"R_eff {R:.2e} Ohm", info
    if kind == "CV":
        f = float(b.params.get("Frequency", "1000") or 1000)
        c = df.iloc[:, 1].values
        d = df.iloc[:, 2].values
        ok = ~np.isnan(c)
        nover = int((~ok).sum())
        if not ok.any():
            return "overflow", "전 구간 overflow", {}
        cm, dm = np.nanmedian(c), np.nanmedian(np.abs(d))
        rp = 1 / (2 * np.pi * f * abs(cm) * dm) if cm != 0 and dm > 0 else np.inf
        info = {"f (Hz)": f, "C 중앙값 (nF)": cm * 1e9, "|D| 중앙값": dm, "Rp 추정 (Ohm)": rp,
                "overflow 점": nover, "함수": b.params.get("Function", "")}
        flip = (c[ok] < 0).any() and (c[ok] > 0).any()
        if abs(cm) < 50e-12 and dm < 20:
            return "open", f"C {cm*1e12:.2f} pF: 미접촉", info
        if dm > 10 or flip or abs(cm) > 1e-6:
            return "short", f"|D| {dm:.3g}, Rp 약 {rp:.3g} Ohm: 쇼트(저항 경로)", info
        if dm > 0.1:
            return "leaky", f"C {cm*1e9:.2f} nF, D {dm:.2f}: 누설 큼", info
        return "ok", f"C {cm*1e9:.2f} nF, D {dm:.3f}: 정상", info
    if kind == "PE":
        cols = [c.strip() for c in b.columns]
        I = df[cols[cols.index("Current")]].values if "Current" in cols else None
        V = df[cols[cols.index("Voltage")]].values
        rng = b.params.get("IrangeIm", "")
        info = {"Vp 설정 (V)": float(b.params.get("Vp", "nan") or "nan"),
                "실제 |V|max (V)": float(np.nanmax(np.abs(V))), "Irange": rng}
        if I is not None:
            imax = np.nanmax(np.abs(I))
            info["|I|max (mA)"] = imax * 1e3
            near = np.mean(np.abs(I) > 0.97 * imax)
            info["포화 구간 (%)"] = near * 100
            if near > 0.2 and imax > 0.9e-3:
                return "short", f"전류가 {imax*1e3:.3g} mA에서 {near*100:.0f}% 구간 잘림: 쇼트형", info
        return "ok", "전류 포화 없음: 루프 해석 가능", info
    if kind == "PATTERN":
        mode = b.params.get("ExecutionMode", "")
        if "Validation" in mode:
            return "nodata", "Pattern Validation 모드: 파형만 저장(측정값 없음)", {"모드": mode}
        cols = [c.strip() for c in b.columns]
        if "MeasResult1_value" not in cols:
            return "nodata", "측정값 열 없음", {}
        t = df["Time"].values
        i = df["MeasResult1_value"].values
        if np.nanmax(np.abs(i)) == 0:
            return "nodata", "측정값이 모두 0", {}
        # 삼각파 0->1 V / 250 us 가정 (11/19 패턴): V(t) = t / 250us
        rng_txt = b.params.get("InitMeasRange1", "")
        clip = 1.156e-3 if rng_txt.startswith("1mA") else 11.4e-3
        df2 = df.drop_duplicates(subset=["Time"]).sort_values("Time")
        df2 = df2[df2["Time"] < 250e-6]          # 첫 상승 구간만 (V가 t에 비례하는 구간)
        t = df2["Time"].values
        i = df2["MeasResult1_value"].values
        v = vp * t / 250e-6
        ok = (np.abs(i) < 0.97 * clip) & (np.abs(i) > 1e-5) & (v > 0)
        glitch = np.abs(i) > 0.1   # 1.0_14 첫 점 -2.6 A 같은 글리치 제외
        ok &= ~glitch
        clipped = (np.abs(i) >= 0.97 * clip) & ~glitch & (v > 0)
        r_up = float(np.min(v[clipped] / clip)) if clipped.any() else np.inf   # 포화 점 -> R 상한
        r_ex = float(np.median(v[ok] / np.abs(i[ok]))) if ok.any() else np.inf
        r = min(r_ex, r_up)
        r_txt = f"R 약 {r:.1f} Ohm" if r_ex <= r_up else f"R <= {r:.1f} Ohm (포화 점 기준 상한)"
        info = {"Irange": rng_txt, "측정 점수": int(len(t)), "R 추정 (Ohm)": r,
                "최대 |I| (mA)": float(np.nanmax(np.abs(i[~glitch]))) * 1e3 if (~glitch).any() else np.nan,
                "글리치 점": int(glitch.sum())}
        if np.nanmax(np.abs(i[~glitch])) > 1e-4:
            return "short", f"수 mV에서 mA 전류: {r_txt} (금속 단락)", info
        return "ok", "단락 아님", info
    return "?", "알 수 없는 형식", {}


STATUS_KO = {"ok": "정상", "floor": "바닥신호", "open": "Open", "short": "Short", "leaky": "Leaky",
             "empty": "빈 파일", "nodata": "측정값 없음", "overflow": "Overflow", "?": "?"}
