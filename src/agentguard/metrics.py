"""Prometheus metrik koleksiyonları (§20.2)."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

traces_ingested_total = Counter("ag_traces_ingested_total", "Alınan trace sayısı", ["agent_id"])
anomalies_detected_total = Counter(
    "ag_anomalies_detected_total", "Tespit edilen anomali sayısı", ["severity", "type"]
)
detection_duration_seconds = Histogram("ag_detection_duration_seconds", "Tespit süresi (saniye)")
retrieval_duration_seconds = Histogram(
    "ag_retrieval_duration_seconds", "Retrieval aşama süresi (saniye)", ["stage"]
)
llm_request_duration_seconds = Histogram(
    "ag_llm_request_duration_seconds", "LLM isteği süresi (saniye)"
)
llm_failures_total = Counter("ag_llm_failures_total", "LLM istek hataları", ["reason"])
investigation_fallback_total = Counter(
    "ag_investigation_fallback_total", "Fallback soruşturma raporu sayısı"
)
schema_valid_first_try_ratio = Gauge(
    "ag_schema_valid_first_try_ratio", "İlk denemede şema geçerlilik oranı"
)
llm_detector_disagreement_total = Counter(
    "ag_llm_detector_disagreement_total",
    "LLM tipi/severity'si ile dedektör kararının çeliştiği sayı",
)
model_version_info = Gauge("ag_model_version_info", "Yüklü model sürümü (info gauge)", ["version"])
