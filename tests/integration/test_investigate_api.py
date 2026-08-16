"""API uçtan uca: POST /v1/traces (tespit) → arka plan soruşturma →
GET /v1/investigations, GET /v1/jobs. `app.state.detector`/`llm`/`rag`,
TestClient başladıktan sonra test-double'larla değiştirilir."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from agentguard.anomaly.isolation_forest import IsolationForestDetector
from agentguard.anomaly.registry import DetectorBundle, Manifest
from agentguard.anomaly.scoring import ECDFCalibrator
from agentguard.api.app import create_app
from agentguard.features.definitions import FEATURE_ORDER, FEATURE_VERSION
from agentguard.features.extractor import FeatureExtractor
from agentguard.features.transforms import apply_clip, apply_log1p, compute_clip_bounds, fit_scaler

FIXTURES = Path(__file__).parent.parent / "fixtures" / "traces"
TEST_API_KEY = "test-api-key"

VALID_LLM_JSON = json.dumps(
    {
        "anomaly_type": "tool_loop",
        "severity": "high",
        "confidence": 0.85,
        "root_cause": "Repeated database queries with identical input.",
        "evidence": [{"statement": "tekrar tespit edildi", "source": "[T2]"}],
        "recommendations": [{"action": "İncele", "priority": 1, "rationale": "loop"}],
    }
)


class _FakeLLMClient:
    def __init__(self, response: str = VALID_LLM_JSON) -> None:
        self._response = response

    async def generate(self, *, system_prompt: str, user_prompt: str, json_schema: dict) -> str:  # type: ignore[type-arg]
        return self._response

    async def warmup(self) -> None:
        pass

    async def aclose(self) -> None:
        pass


def _build_bundle() -> DetectorBundle:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    extractor = FeatureExtractor(bigram_vocabulary=set())

    normal_payload = json.loads((FIXTURES / "normal_trace.json").read_text())
    from agentguard.schemas.trace import AgentTrace

    traces = []
    for i in range(60):
        payload = dict(normal_payload)
        payload["trace_id"] = f"trace-bundle-normal-{i:04d}"
        payload["started_at"] = (base + timedelta(seconds=i * 10)).isoformat()
        payload["ended_at"] = (base + timedelta(seconds=i * 10 + 12)).isoformat()
        traces.append(AgentTrace.model_validate(payload))

    raw = np.array([[extractor.extract_raw(t)[name] for name in FEATURE_ORDER] for t in traces])
    log = apply_log1p(raw)
    low, high = compute_clip_bounds(log)
    clipped = apply_clip(log, low, high)
    scaler = fit_scaler(clipped)
    scaled = scaler.transform(clipped)

    detector = IsolationForestDetector(random_state=42)
    detector.fit(scaled)
    ecdf = ECDFCalibrator(detector.raw_score(scaled))

    return DetectorBundle(
        scaler=scaler,
        isolation_forest=detector,
        ecdf_if=ecdf,
        bigram_vocabulary=set(),
        thresholds={"tau": 0.9, "clip_low": low.tolist(), "clip_high": high.tolist()},
        manifest=Manifest(
            feature_version=FEATURE_VERSION,
            git_sha="test",
            train_rows=60,
            fusion_weights={"isolation_forest": 1.0},
        ),
    )


@pytest.fixture
def wired_client() -> TestClient:
    app = create_app()
    with TestClient(app, headers={"X-API-Key": TEST_API_KEY}) as client:
        bundle = _build_bundle()
        app.state.detector = bundle
        app.state.feature_extractor = FeatureExtractor(bigram_vocabulary=bundle.bigram_vocabulary)
        app.state.llm = _FakeLLMClient()
        app.state.rag = None
        yield client


def _tool_loop_payload() -> dict:  # type: ignore[type-arg]
    base = datetime(2026, 1, 1, tzinfo=UTC)
    calls = [
        {
            "index": i,
            "tool_name": "db.query",
            "started_at": (base + timedelta(seconds=i)).isoformat(),
            "ended_at": (base + timedelta(seconds=i, milliseconds=300)).isoformat(),
            "status": "ok",
            "duration_ms": 300,
            "input_hash": "same-hash-0001",
        }
        for i in range(45)
    ]
    return {
        "trace_id": "trace-api-loop-0001",
        "agent_id": "agent-01",
        "started_at": base.isoformat(),
        "ended_at": (base + timedelta(seconds=45)).isoformat(),
        "tool_calls": calls,
        "token_usage": {"prompt_tokens": 300, "completion_tokens": 150, "total_tokens": 450},
    }


def test_post_trace_returns_detection_result(wired_client: TestClient) -> None:
    payload = _tool_loop_payload()
    response = wired_client.post("/v1/traces", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["detection"] is not None
    assert body["detection"]["is_anomaly"] is True
    assert "R001_hard_call_limit" in body["detection"]["triggered_rules"]


def test_investigation_completes_via_background_task(wired_client: TestClient) -> None:
    payload = _tool_loop_payload()
    ingest_response = wired_client.post("/v1/traces", json=payload)
    detector_severity = ingest_response.json()["detection"]["severity"]

    # TestClient BackgroundTasks'ı senkron yürütür (yanıt döndükten hemen sonra);
    # yine de olası bir yarış durumuna karşı kısa bir bekleme payı bırakılır.
    for _ in range(20):
        response = wired_client.get(f"/v1/investigations/{payload['trace_id']}")
        if response.status_code == 200:
            break
        asyncio.run(asyncio.sleep(0.05))

    assert response.status_code == 200
    body = response.json()
    assert body["generated_by"] == "llm"
    # Fake LLM "high" önerse de nihai severity DEDEKTÖRDEN gelir (ADR-001);
    # bu, farklı bir değer olsa bile (ör. "critical") LLM'in önerisini geçersiz kılar.
    assert body["severity"] == detector_severity


def test_trigger_investigation_is_idempotent(wired_client: TestClient) -> None:
    payload = _tool_loop_payload()
    payload["trace_id"] = "trace-api-loop-0002"
    wired_client.post("/v1/traces", json=payload)

    for _ in range(20):
        if wired_client.get(f"/v1/investigations/{payload['trace_id']}").status_code == 200:
            break
        asyncio.run(asyncio.sleep(0.05))

    second_trigger = wired_client.post(f"/v1/anomalies/{payload['trace_id']}/investigate")
    assert second_trigger.status_code == 202
    assert second_trigger.json()["status"] == "already_completed"


def test_force_reinvestigation_overwrites_existing_record(wired_client: TestClient) -> None:
    """`?force=true` var olan bir soruşturmayı yeniden üretip üzerine
    yazabilmeli — `InvestigationRecord.trace_id` UNIQUE kısıtlı olduğundan
    düz bir INSERT (`add()`) burada `IntegrityError` fırlatır ve arka plan
    görevi sessizce başarısız olurdu (gerçek bir prod hatası: bkz.
    `InvestigationRepository.upsert()`)."""
    payload = _tool_loop_payload()
    payload["trace_id"] = "trace-api-loop-0003"
    wired_client.post("/v1/traces", json=payload)

    for _ in range(20):
        if wired_client.get(f"/v1/investigations/{payload['trace_id']}").status_code == 200:
            break
        asyncio.run(asyncio.sleep(0.05))
    first = wired_client.get(f"/v1/investigations/{payload['trace_id']}").json()

    trigger = wired_client.post(f"/v1/anomalies/{payload['trace_id']}/investigate?force=true")
    assert trigger.status_code == 202
    assert trigger.json()["status"] == "queued"

    for _ in range(20):
        response = wired_client.get(f"/v1/investigations/{payload['trace_id']}")
        body = response.json()
        if response.status_code == 200 and body["created_at"] != first["created_at"]:
            break
        asyncio.run(asyncio.sleep(0.05))

    assert response.status_code == 200
    assert body["created_at"] != first["created_at"]
    assert body["generated_by"] == "llm"


def test_get_investigation_404_for_unknown_trace(wired_client: TestClient) -> None:
    response = wired_client.get("/v1/investigations/does-not-exist-00")
    assert response.status_code == 404


def test_get_job_404_for_unknown_job(wired_client: TestClient) -> None:
    response = wired_client.get("/v1/jobs/does-not-exist")
    assert response.status_code == 404
