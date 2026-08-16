from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent.parent / "fixtures" / "traces"


def load_payload() -> dict:  # type: ignore[type-arg]
    return json.loads((FIXTURES / "normal_trace.json").read_text())


def test_post_trace_requires_api_key(client: TestClient) -> None:
    payload = load_payload()
    response = client.post("/v1/traces", json=payload, headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


def test_post_trace_creates_then_is_idempotent(client: TestClient) -> None:
    payload = load_payload()

    first = client.post("/v1/traces", json=payload)
    assert first.status_code == 201
    # detector artefaktı bu testte yüklü değil (bkz. conftest.py) -> detection=None
    assert first.json() == {
        "trace_id": payload["trace_id"],
        "status": "received",
        "detection": None,
    }

    second = client.post("/v1/traces", json=payload)
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"


def test_post_trace_conflict_on_changed_payload(client: TestClient) -> None:
    payload = load_payload()
    client.post("/v1/traces", json=payload)

    mutated = dict(payload)
    mutated["agent_version"] = "9.9.9"
    response = client.post("/v1/traces", json=mutated)
    assert response.status_code == 409


def test_post_trace_rejects_too_many_tool_calls(client: TestClient) -> None:
    payload = load_payload()
    template = payload["tool_calls"][0]
    payload["tool_calls"] = [dict(template, index=i) for i in range(501)]
    payload["trace_id"] = "trace-too-many-calls"

    response = client.post("/v1/traces", json=payload)
    assert response.status_code == 422  # Pydantic max_length=500 önce devreye girer


def test_get_trace_roundtrip(client: TestClient) -> None:
    payload = load_payload()
    client.post("/v1/traces", json=payload)

    response = client.get(f"/v1/traces/{payload['trace_id']}")
    assert response.status_code == 200
    assert response.json()["trace_id"] == payload["trace_id"]


def test_get_trace_not_found(client: TestClient) -> None:
    response = client.get("/v1/traces/does-not-exist-00")
    assert response.status_code == 404


def test_batch_ingest_mixed_results(client: TestClient) -> None:
    payload = load_payload()
    duplicate_first = client.post("/v1/traces", json=payload)
    assert duplicate_first.status_code == 201

    second_payload = dict(payload)
    second_payload["trace_id"] = "trace-normal-0002"

    response = client.post("/v1/traces:batch", json={"traces": [payload, second_payload]})
    assert response.status_code == 207
    results = {r["trace_id"]: r["status"] for r in response.json()}
    assert results[payload["trace_id"]] == "duplicate"
    assert results[second_payload["trace_id"]] == "received"
