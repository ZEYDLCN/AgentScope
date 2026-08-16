"""AgentGuard Dashboard — Genel Bakış (§18).

KPI kartları, severity dağılımı, soruşturma üretim kaynağı dağılımı.
Yalnızca REST API'yi tüketir; uygulama mantığı paylaşılmaz (ADR-006).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from http_client import api_get

st.set_page_config(page_title="AgentGuard AI", page_icon="🛡️", layout="wide")


@st.cache_data(ttl=30)
def _load_stats() -> dict | None:  # type: ignore[type-arg]
    return api_get("/v1/stats")


def main() -> None:
    st.title("🛡️ AgentGuard AI — Genel Bakış")
    st.caption("AI agent yürütmelerinde anomali tespiti ve soruşturma sistemi")

    stats = _load_stats()
    if stats is None:
        st.warning(
            "API'ye ulaşılamıyor. `AG_API_URL` ortam değişkenini kontrol edin "
            "(varsayılan: http://localhost:8000)."
        )
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Toplam Trace", stats["total_traces"])
    col2.metric("Toplam Tespit", stats["total_detections"])
    col3.metric("Anomali Sayısı", stats["total_anomalies"])
    col4.metric("Anomali Oranı", f"{stats['anomaly_rate']:.1%}")

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Severity Dağılımı")
        by_severity: dict[str, int] = stats.get("anomalies_by_severity", {})
        if by_severity:
            st.bar_chart(by_severity)
        else:
            st.info("Henüz anomali kaydı yok.")

    with col_right:
        st.subheader("Soruşturma Üretim Kaynağı")
        by_source: dict[str, int] = stats.get("investigations_by_generated_by", {})
        if by_source:
            st.bar_chart(by_source)
            fallback = by_source.get("fallback", 0)
            total = sum(by_source.values())
            if total and fallback / total > 0.05:
                st.warning(
                    f"Fallback oranı %{fallback / total:.0%} — LLM/şema doğrulama "
                    f"sorunlarını incelemeyi düşünün (§14.3)."
                )
        else:
            st.info("Henüz soruşturma kaydı yok.")

    st.divider()
    st.page_link("pages/1_Anomalies.py", label="→ Anomali listesine git", icon="🚨")
    st.page_link("pages/2_Investigation.py", label="→ Soruşturma detayına git", icon="🔍")
    st.page_link("pages/3_Knowledge.py", label="→ Retrieval debug'a git", icon="📚")
    st.page_link("pages/4_Models.py", label="→ Model değerlendirmesine git", icon="📊")


main()
