"""matplotlib 공통 스타일 + 한글 폰트 설정 (Streamlit Cloud: packages.txt 의 fonts-nanum)"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.ticker import NullFormatter

PALETTE = {
    "MFM": "#1f5f8b",
    "MFBM": "#c2410c",
    "measured": "#111827",
    "model": "#0f766e",
    "grid": "#d6dde4",
    "ok": "#1b7f4b",
    "warn": "#b7791f",
    "bad": "#c53030",
    "open": "#2b6cb0",
}
DEVICE_COLORS = {
    "MFM2": "#93c5fd", "MFM4": "#3b82f6", "MFM6": "#1d4ed8", "MFM8": "#1e3a8a",
    "MFBM2": "#fdba74", "MFBM4": "#f97316", "MFBM6": "#c2410c", "MFBM8": "#7c2d12",
}

_FONT_DONE = False


def setup_fonts():
    global _FONT_DONE
    if _FONT_DONE:
        return
    wanted = ["NanumGothic", "Noto Sans CJK KR", "Noto Sans KR", "Malgun Gothic", "AppleGothic"]
    for path in fm.findSystemFonts():
        low = path.lower()
        if "nanum" in low or "notosanscjk" in low or "malgun" in low:
            try:
                fm.fontManager.addfont(path)
            except Exception:
                pass
    names = {f.name for f in fm.fontManager.ttflist}
    family = [n for n in wanted if n in names]
    plt.rcParams["font.family"] = family[:1] + ["DejaVu Sans"] if family else ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams.update({
        "axes.grid": True, "grid.color": PALETTE["grid"], "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.titlesize": 11, "axes.labelsize": 10, "legend.fontsize": 8.5,
        "figure.dpi": 110,
    })
    _FONT_DONE = True


def fig(nrows=1, ncols=1, w=6.4, h=4.0):
    setup_fonts()
    f, ax = plt.subplots(nrows, ncols, figsize=(w, h), constrained_layout=True)
    return f, ax


def nominor(*axes):
    """로그축 보조 눈금 라벨이 겹치지 않게 숨긴다."""
    for a in axes:
        a.xaxis.set_minor_formatter(NullFormatter())
        a.yaxis.set_minor_formatter(NullFormatter())
