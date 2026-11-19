import json
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
refs = json.loads((ROOT / "data" / "references.json").read_text(encoding="utf-8"))

st.title("레퍼런스")
st.caption("앱의 가정값과 판정 기준이 어떤 논문에 기대고 있는지 정리했습니다. 발표에는 정식 출판 논문을 우선 인용하세요 (arXiv는 심사 전 버전일 수 있음).")

df = pd.DataFrame(refs)
topics = st.multiselect("주제", sorted(df["topic"].unique()), default=sorted(df["topic"].unique()))
for _, r in df[df["topic"].isin(topics)].iterrows():
    with st.container(border=True):
        st.markdown(f"**{r['topic']}** · {r['type']}")
        st.markdown(r["cite"])
        st.caption(f"앱에서 쓰는 곳: {r['use']}")
        if r["url"]:
            st.markdown(f"[원문 열기]({r['url']})")
