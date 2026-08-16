"""Anomali listesi — filtrelenebilir tablo → satır seçimi (§18)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from http_client import api_get

st.set_page_config(page_title="Anomaliler — AgentGuard", page_icon="🚨", layout="wide")
st.title("🚨 Anomaliler")

SEVERITIES = ["(hepsi)", "low", "medium", "high", "critical"]


@st.cache_data(ttl=30)
def _load_anomalies(severity: str | None) -> dict | None:  # type: ignore[type-arg]
    params: dict[str, object] = {}
    if severity:
        params["severity"] = severity
    return api_get("/v1/anomalies", **params)


selected_severity = st.selectbox("Severity filtresi", SEVERITIES)
severity_param = None if selected_severity == "(hepsi)" else selected_severity

data = _load_anomalies(severity_param)

if data is None:
    st.warning("API'ye ulaşılamıyor.")
elif not data["items"]:
    st.info("Filtreye uyan anomali bulunamadı.")
else:
    st.caption(f"{len(data['items'])} kayıt gösteriliyor")

    for item in data["items"]:
        with st.container(border=True):
            cols = st.columns([2, 1, 1, 1, 3, 1])
            cols[0].markdown(f"**{item['trace_id']}**")
            severity_emoji = {
                "critical": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🟢",
            }.get(item["severity"], "⚪")
            cols[1].markdown(f"{severity_emoji} {item['severity']}")
            cols[2].markdown(f"skor: {item['score']:.3f}")
            cols[3].markdown(item["detected_at"][:19])
            cols[4].markdown(", ".join(item["triggered_rules"]) or "—")
            if cols[5].button("İncele", key=f"btn-{item['trace_id']}"):
                st.session_state["selected_trace_id"] = item["trace_id"]
                st.switch_page("pages/2_Investigation.py")
