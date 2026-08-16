"""Soruşturma detayı — trace zaman çizelgesi + kanıt kartları (§18)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from http_client import api_get

st.set_page_config(page_title="Soruşturma — AgentGuard", page_icon="🔍", layout="wide")
st.title("🔍 Soruşturma Detayı")

default_trace_id = st.session_state.get("selected_trace_id", "")
trace_id = st.text_input("Trace ID", value=default_trace_id)

if not trace_id:
    st.info("Bir trace_id girin ya da Anomaliler sayfasından bir kayıt seçin.")
    st.stop()

trace = api_get(f"/v1/traces/{trace_id}")
if trace is None:
    st.error("Trace bulunamadı.")
    st.stop()

payload = trace["payload"]

st.subheader("Trace Özeti")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Agent", payload["agent_id"])
col2.metric("Araç Çağrısı", len(payload["tool_calls"]))
col3.metric("Toplam Token", payload["token_usage"]["total_tokens"])
col4.metric("Durum", payload["final_status"])

st.subheader("Araç Çağrısı Zaman Çizelgesi")
timeline_rows = [
    {
        "index": c["index"],
        "tool_name": c["tool_name"],
        "status": c["status"],
        "duration_ms": c["duration_ms"],
        "input_hash": c["input_hash"][:12],
    }
    for c in payload["tool_calls"]
]
st.dataframe(timeline_rows, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Soruşturma Raporu")

investigation_response = api_get(f"/v1/investigations/{trace_id}")
if investigation_response is None:
    st.warning(
        "Bu trace için henüz bir soruşturma raporu yok (tespit anomali değil ya da iş kuyrukta)."
    )
else:
    inv = investigation_response
    if inv.get("status") in {"pending", "running"}:
        st.info(f"Soruşturma devam ediyor (durum: {inv['status']}). Sayfayı yeniden yükleyin.")
    else:
        severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
            inv["severity"], "⚪"
        )
        badge = "🤖 LLM" if inv["generated_by"] == "llm" else "⚠️ Fallback"
        st.markdown(
            f"**Tip:** `{inv['anomaly_type']}` &nbsp;&nbsp; "
            f"**Severity:** {severity_emoji} {inv['severity']} &nbsp;&nbsp; "
            f"**Güven:** {inv['confidence']:.2f} &nbsp;&nbsp; **Kaynak:** {badge}"
        )
        st.markdown(f"**Kök neden:** {inv['root_cause']}")

        st.markdown("##### Kanıtlar")
        for ev in inv["evidence"]:
            st.markdown(f"- {ev['statement']} `[{ev['source']}]`")

        st.markdown("##### Öneriler")
        for rec in sorted(inv["recommendations"], key=lambda r: r["priority"]):
            st.markdown(f"- **P{rec['priority']}** {rec['action']} — _{rec['rationale']}_")

        if inv["retrieved_docs"]:
            st.markdown("##### Kaynak Dokümanlar")
            st.code("\n".join(inv["retrieved_docs"]))
