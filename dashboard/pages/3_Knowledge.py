"""Retrieval debug — sorgu → BM25/vector/RRF/rerank skorları yan yana (§18).

"Retrieval debug sayfası portföyde en çok etki eden ekrandır: hibrit
aramanın ve reranker'ın sıralamayı nasıl değiştirdiğini yan yana gösterir."
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from http_client import api_get

st.set_page_config(page_title="Knowledge Debug — AgentGuard", page_icon="📚", layout="wide")
st.title("📚 Retrieval Debug")

query = st.text_input("Sorgu", value="agent tool loop repeated calls")
top_k = st.slider("top_k", min_value=5, max_value=50, value=20)

if not query:
    st.stop()

result = api_get("/v1/knowledge/search", q=query, top_k=top_k)
if result is None:
    st.warning("RAG index yüklü değil ya da API'ye ulaşılamıyor.")
    st.stop()

col_bm25, col_vector, col_fused = st.columns(3)

with col_bm25:
    st.subheader("BM25")
    st.dataframe(
        [{"chunk_id": r["chunk_id"], "score": round(r["score"], 4)} for r in result["bm25"]],
        use_container_width=True,
        hide_index=True,
    )

with col_vector:
    st.subheader("Vektör (kosinüs)")
    st.dataframe(
        [{"chunk_id": r["chunk_id"], "score": round(r["score"], 4)} for r in result["vector"]],
        use_container_width=True,
        hide_index=True,
    )

with col_fused:
    st.subheader("RRF Füzyon")
    st.dataframe(
        [{"chunk_id": r["chunk_id"], "score": round(r["score"], 4)} for r in result["fused_rrf"]],
        use_container_width=True,
        hide_index=True,
    )

st.divider()
st.subheader("Reranker Sonrası (nihai — LLM'e giden)")

if not result["final"]:
    st.info(
        "Hiçbir chunk alaka eşiğini (rerank_min_score) geçemedi — "
        "'her zaman N doküman doldur' anti-pattern'i kasıtlı olarak uygulanmaz (§13)."
    )
else:
    for r in result["final"]:
        with st.container(border=True):
            score = r["rerank_score"] if r["rerank_score"] is not None else r["rrf_score"]
            st.markdown(f"**#{r['rank']} · {r['chunk_id']}** (skor: {score:.3f})")
            st.caption(f"{r['doc_id']} › {r['section']}")
            st.text(r["text_preview"])
