"""Hız sınırlama (`slowapi`) ve CORS testleri (§16.2, §21.3)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent.parent / "fixtures" / "traces"


def load_payload() -> dict:  # type: ignore[type-arg]
    return json.loads((FIXTURES / "normal_trace.json").read_text())


def test_investigate_endpoint_returns_429_after_limit_exceeded(client: TestClient) -> None:
    # trace yok -> her istek 404 döner, ama rate limit sayaç yine de artar
    # (slowapi limiti route body'si çalışmadan ÖNCE kontrol eder).
    responses = [client.post("/v1/anomalies/trace-does-not-exist/investigate") for _ in range(11)]
    statuses = [r.status_code for r in responses]
    assert statuses[:10] == [404] * 10
    assert statuses[10] == 429
    last = responses[10]
    assert last.headers["content-type"] == "application/problem+json"
    assert last.json()["status"] == 429


def test_ingest_endpoint_returns_429_after_limit_exceeded(client: TestClient) -> None:
    payload = load_payload()
    statuses = []
    for _ in range(61):
        response = client.post("/v1/traces", json=payload)
        statuses.append(response.status_code)
    # ilk istek 201, geri kalanı idempotent 200 (aynı trace_id) — 61. istekte 429
    assert statuses[0] == 201
    assert statuses[60] == 429


def test_cors_allows_configured_dashboard_origin(client: TestClient) -> None:
    response = client.options(
        "/v1/stats",
        headers={
            "Origin": "http://localhost:8501",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8501"


def test_cors_rejects_unlisted_origin(client: TestClient) -> None:
    response = client.options(
        "/v1/stats",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-API-Key",
        },
    )
    # starlette CORSMiddleware, izinsiz origin'de preflight'ı 400 ile reddeder
    # ve allow-origin başlığını eklemez.
    assert "access-control-allow-origin" not in response.headers
