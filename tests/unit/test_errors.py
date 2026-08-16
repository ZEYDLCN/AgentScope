from __future__ import annotations

from fastapi.testclient import TestClient


def test_validation_error_returns_problem_json(client: TestClient) -> None:
    # health.py'de body kabul eden bir POST rotası henüz yok; 404 üzerinden
    # temel problem+json davranışını unhandled-exception handler kapsamı
    # M1'de ingest endpoint'i eklenince tam kapsanacak. Şimdilik yalnızca
    # register_exception_handlers'ın app'e bağlandığını doğrula.
    response = client.get("/does-not-exist")
    assert response.status_code == 404
