"""data/1119 의 B1500A CSV를 읽어 레코드 목록으로 만든다."""
from __future__ import annotations

import json
import re
from pathlib import Path

from b1500 import parse_file, kind_of, guess_sample, judge

ROOT = Path(__file__).resolve().parent
DATA = ROOT
KIND_KO = {"IV": "I–V (HRSMU)", "CV": "C–V (4284A)", "PE": "P–E (WGFMU)", "PATTERN": "Pattern Editor"}


def _sample_map():
    p = DATA / "sample_map.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def time_of(name: str) -> str:
    m = re.search(r"(\d+)_(\d+)_(\d+)_(AM|PM)", name)
    if not m:
        return ""
    h, mi, s, ap = int(m.group(1)), m.group(2), m.group(3), m.group(4)
    h = h + 12 if ap == "PM" and h != 12 else h
    return f"{h:02d}:{mi}:{s}"


def record_from_bytes(name: str, raw: bytes, smap: dict | None = None):
    smap = smap if smap is not None else _sample_map()
    blocks = parse_file(raw)
    if not blocks:
        return None
    k = kind_of(blocks)
    remarks = blocks[0].meta.get("Remarks", "")
    sample = guess_sample(name, remarks)
    note = "Remarks/파일명" if sample != "미기재" else ""
    if sample == "미기재":
        for key, v in smap.items():
            if not key.startswith("_") and name.startswith(key):
                sample, note = v["sample"], v["note"]
                break
    st_, msg, info = judge(k, blocks, name)
    return {
        "file": name, "time": time_of(name), "kind": k, "kind_ko": KIND_KO.get(k, k),
        "sample": sample, "sample_note": note, "status": st_, "msg": msg, "info": info,
        "blocks": blocks, "remarks": remarks,
    }


def load_all():
    smap = _sample_map()
    recs = []
    for p in sorted(DATA.glob("*.csv")):
        r = record_from_bytes(p.name, p.read_bytes(), smap)
        if r:
            recs.append(r)
    recs.sort(key=lambda r: r["time"])
    return recs
