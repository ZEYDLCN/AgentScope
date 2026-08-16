"""Yalnızca frontend'i görsel/işlevsel olarak test etmek için kullanılan,
gerçek AgentGuard backend'ini TAKLİT EDEN minimal bir sunucu.

Bu dosya deploy edilmez / repoya ait "gerçek" backend değildir — sadece bu
oturumda ağ erişimi olmadan (HF Hub / Ollama yok) frontend'in gerçekçi
verilerle nasıl göründüğünü doğrulamak için kullanılır.
"""

from __future__ import annotations

import http.server
import json
from datetime import UTC, datetime, timedelta

TRACE_ID = "trace-demo-0001"


def _investigation() -> dict:
    return {
        "trace_id": TRACE_ID,
        "anomaly_type": "tool_loop",
        "severity": "high",
        "confidence": 0.87,
        "root_cause": (
            "Agent, db.query aracını art arda 23 kez aynı input_hash ile çağırdı; "
            "bu, cursor/sayfalama mantığındaki bir hatanın veya hatalı retry "
            "davranışının işaretidir."
        ),
        "evidence": [
            {
                "statement": "repeated_call_count = 23, max_consecutive_repeats = 19",
                "source": "[T2]",
            },
            {
                "statement": "Tool loop kalıbı: aynı tool_name + input_hash art arda tekrarı",
                "source": "[D1]",
            },
        ],
        "recommendations": [
            {
                "action": "Agent'ı duraklat ve son N çağrının input_hash dağılımını incele",
                "priority": 1,
                "rationale": "Aktif döngüyü durdurmak için ilk adım",
            },
            {
                "action": "idempotency + exponential backoff ekle",
                "priority": 2,
                "rationale": "Kök nedeni kalıcı olarak çözer",
            },
        ],
        "retrieved_docs": ["tool_loop#c1", "rb_terminate_agent#c2"],
        "model_name": "qwen2.5:7b-instruct-q4_K_M",
        "prompt_version": "inv-v1",
        "generated_by": "llm",
        "latency_ms": 842,
        "created_at": datetime.now(UTC).isoformat(),
    }


ROUTES = {
    "/health/ready": lambda qs: (
        200,
        {
            "status": "ok",
            "checks": {
                "detector_loaded": True,
                "rag_loaded": True,
                "llm_reachable": True,
                "db_reachable": True,
            },
        },
    ),
    "/v1/stats": lambda qs: (
        200,
        {
            "total_traces": 1284,
            "total_detections": 1284,
            "total_anomalies": 96,
            "anomaly_rate": 96 / 1284,
            "anomalies_by_severity": {"critical": 6, "high": 21, "medium": 34, "low": 35},
            "investigations_by_generated_by": {"llm": 82, "fallback": 14},
        },
    ),
    "/v1/anomalies": lambda qs: (
        200,
        {
            "items": [
                {
                    "trace_id": f"trace-{i:06d}",
                    "is_anomaly": True,
                    "score": round(0.6 + i * 0.01, 3),
                    "severity": ["critical", "high", "medium", "low"][i % 4],
                    "threshold": 0.7,
                    "triggered_rules": ["R003_repeat_burst"] if i % 2 == 0 else [],
                    "detected_at": (datetime.now(UTC) - timedelta(minutes=i * 7)).isoformat(),
                }
                for i in range(1, 13)
            ],
            "next_cursor": None,
        },
    ),
    f"/v1/traces/{TRACE_ID}": lambda qs: (
        200,
        {
            "trace_id": TRACE_ID,
            "agent_id": "demo-agent",
            "received_at": datetime.now(UTC).isoformat(),
            "payload": {
                "trace_id": TRACE_ID,
                "agent_id": "demo-agent",
                "agent_version": "1.4.0",
                "session_id": "sess-1",
                "started_at": datetime.now(UTC).isoformat(),
                "ended_at": datetime.now(UTC).isoformat(),
                "user_prompt_preview": "Kullanıcının son 30 günlük siparişlerini özetle",
                "tool_calls": [
                    {
                        "index": i,
                        "tool_name": "db.query",
                        "started_at": datetime.now(UTC).isoformat(),
                        "ended_at": datetime.now(UTC).isoformat(),
                        "status": "ok" if i % 5 else "error",
                        "duration_ms": 120 + i,
                        "input_hash": "a1b2c3d4e5f6a7b8",
                        "input_preview": None,
                        "output_size_bytes": 512,
                        "error_type": None,
                    }
                    for i in range(20)
                ],
                "token_usage": {
                    "prompt_tokens": 3200,
                    "completion_tokens": 900,
                    "total_tokens": 4100,
                },
                "final_status": "completed",
                "metadata": {},
            },
        },
    ),
    f"/v1/investigations/{TRACE_ID}": lambda qs: (200, _investigation()),
    "/v1/knowledge/search": lambda qs: (
        200,
        {
            "query": qs.get("q", [""])[0],
            "bm25": [
                {"chunk_id": f"tool_loop#c{i}", "score": round(3.2 - i * 0.3, 2)}
                for i in range(1, 6)
            ],
            "vector": [
                {"chunk_id": f"database_policy#c{i}", "score": round(0.9 - i * 0.08, 2)}
                for i in range(1, 6)
            ],
            "fused_rrf": [
                {"chunk_id": f"tool_loop#c{i}", "score": round(0.03 - i * 0.001, 4)}
                for i in range(1, 6)
            ],
            "final": [
                {
                    "chunk_id": "tool_loop#c1",
                    "doc_id": "tool_loop",
                    "section": "Tespit Sinyalleri",
                    "rank": 1,
                    "rrf_score": 0.031,
                    "rerank_score": 0.82,
                    "text_preview": "max_consecutive_repeats >= 5 → R003_repeat_burst kuralı tetiklenir. Tekrar tanımı aynı tool_name VE aynı input_hash gerektirir…",
                },
                {
                    "chunk_id": "rb_terminate_agent#c2",
                    "doc_id": "rb_terminate_agent",
                    "section": "Ne Zaman Uygulanır",
                    "rank": 2,
                    "rrf_score": 0.028,
                    "rerank_score": 0.61,
                    "text_preview": "Agent aynı aracı art arda 5'ten fazla çağırdığında ve backoff uygulanmadığında derhal duraklatılmalıdır…",
                },
            ],
        },
    ),
}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(self.path)
        handler = ROUTES.get(parsed.path)
        if handler is None:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"title": "not found", "status": 404}).encode())
            return
        status, body = handler(parse_qs(parsed.query))
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, format: str, *args: object) -> None:
        pass


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("0.0.0.0", 8000), Handler)
    print("fake-backend listening on :8000")
    server.serve_forever()
