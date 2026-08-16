"""`/v1/anomalies`, `/v1/stats`, `/v1/knowledge/search`, `/v1/knowledge/reindex`,
`/metrics` uçtan uca testleri (§16, §18, §20)."""

from __future__ import annotations

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
from agentguard.rag.pipeline import RAGPipeline
from agentguard.schemas.knowledge import Chunk
from agentguard.schemas.trace import AgentTrace

FIXTURES = Path(__file__).parent.parent / "fixtures" / "traces"
TEST_API_KEY = "test-api-key"


class FakeEmbedder:
    dimension = 8

    def embed(self, texts: list[str]) -> np.ndarray:
        rng = np.random.default_rng(0)
        return rng.normal(size=(len(texts), self.dimension)).astype(np.float32)


class FakeReranker:
    def rerank(self, query: str, chunks: list[Chunk]) -> list[tuple[Chunk, float]]:
        return [(c, 0.9) for c in chunks]


class _NoOpLLMClient:
    """`schedule_investigation` arka plan görevini sessizce fallback'e düşürür."""

    async def generate(self, *, system_prompt: str, user_prompt: str, json_schema: dict) -> str:  # type: ignore[type-arg]
        raise RuntimeError("test ortamında LLM yok")

    async def warmup(self) -> None:
        pass

    async def aclose(self) -> None:
        pass


def _build_bundle() -> DetectorBundle:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    extractor = FeatureExtractor(bigram_vocabulary=set())
    normal_payload = json.loads((FIXTURES / "normal_trace.json").read_text())

    traces = []
    for i in range(60):
        payload = dict(normal_payload)
        payload["trace_id"] = f"trace-obs-normal-{i:04d}"
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


def _build_rag(tmp_path: Path) -> RAGPipeline:
    kb = tmp_path / "kb"
    (kb / "failure_modes").mkdir(parents=True)
    (kb / "failure_modes" / "tool_loop.md").write_text(
        "---\ndoc_id: tool_loop\ntitle: Tool Loop\ncategory: reference\n"
        "anomaly_types: [tool_loop]\nseverity_scope: [high]\nversion: 1.0\n"
        "updated: 2026-07-01\n---\n\n## Sinyaller\n\nTekrarlanan çağrılar.\n"
    )
    return RAGPipeline.build(kb, FakeEmbedder(), reranker=FakeReranker())


def _tool_loop_payload(trace_id: str = "trace-obs-loop-0001") -> dict:  # type: ignore[type-arg]
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
        "trace_id": trace_id,
        "agent_id": "agent-01",
        "started_at": base.isoformat(),
        "ended_at": (base + timedelta(seconds=45)).isoformat(),
        "tool_calls": calls,
        "token_usage": {"prompt_tokens": 300, "completion_tokens": 150, "total_tokens": 450},
    }


@pytest.fixture
def wired_client(tmp_path: Path) -> TestClient:
    app = create_app()
    with TestClient(app, headers={"X-API-Key": TEST_API_KEY}) as client:
        app.state.detector = _build_bundle()
        app.state.feature_extractor = FeatureExtractor(bigram_vocabulary=set())
        app.state.rag = _build_rag(tmp_path)
        app.state.llm = _NoOpLLMClient()
        yield client


def test_metrics_endpoint_returns_prometheus_text(wired_client: TestClient) -> None:
    response = wired_client.get("/metrics")
    assert response.status_code == 200
    assert b"ag_traces_ingested_total" in response.content or response.content == b""
    assert "text/plain" in response.headers["content-type"]


def test_metrics_is_exempt_from_api_key() -> None:
    app = create_app()
    with TestClient(app) as client:  # X-API-Key header YOK
        response = client.get("/metrics")
        assert response.status_code == 200


def test_stats_reflects_ingested_traces(wired_client: TestClient) -> None:
    wired_client.post("/v1/traces", json=_tool_loop_payload())

    response = wired_client.get("/v1/stats")
    assert response.status_code == 200
    body = response.json()
    assert body["total_traces"] >= 1
    assert body["total_anomalies"] >= 1
    assert body["anomaly_rate"] > 0


def test_list_anomalies_returns_detected_trace(wired_client: TestClient) -> None:
    wired_client.post("/v1/traces", json=_tool_loop_payload("trace-obs-loop-0002"))

    response = wired_client.get("/v1/anomalies")
    assert response.status_code == 200
    body = response.json()
    trace_ids = {item["trace_id"] for item in body["items"]}
    assert "trace-obs-loop-0002" in trace_ids


def test_list_anomalies_filters_by_severity(wired_client: TestClient) -> None:
    wired_client.post("/v1/traces", json=_tool_loop_payload("trace-obs-loop-0003"))

    response = wired_client.get("/v1/anomalies", params={"severity": "does-not-exist"})
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_knowledge_search_returns_all_stages(wired_client: TestClient) -> None:
    response = wired_client.get("/v1/knowledge/search", params={"q": "tool loop repeated calls"})
    assert response.status_code == 200
    body = response.json()
    assert "bm25" in body
    assert "vector" in body
    assert "fused_rrf" in body
    assert "final" in body


def test_knowledge_search_503_when_rag_not_loaded() -> None:
    app = create_app()
    with TestClient(app, headers={"X-API-Key": TEST_API_KEY}) as client:
        response = client.get("/v1/knowledge/search", params={"q": "test"})
        assert response.status_code == 503


def test_knowledge_reindex_returns_202(
    wired_client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Arka plan reindex görevi `get_settings()`'i (lru_cache singleton) çağırır;
    # bu, ortak sabit "nonexistent" test yoluna GERÇEK bir index yazıp sonraki
    # testleri kirletmesin (ve gerçek HF ağına gitmeye zorlamasın) diye
    # tmp_path'e yönlendirilir. `wired_client` fixture'ı lifespan sırasında
    # zaten bir Settings önbelleğe aldığı için cache elle temizlenir.
    from agentguard.config import get_settings

    monkeypatch.setenv("AG_KNOWLEDGE_PATH", str(FIXTURES.parent.parent.parent / "knowledge"))
    monkeypatch.setenv("AG_INDEX_PATH", str(tmp_path / "reindex-out"))
    get_settings.cache_clear()

    response = wired_client.post("/v1/knowledge/reindex")
    assert response.status_code == 202
    assert response.json()["status"] == "queued"

    reindexed_path = tmp_path / "reindex-out"
    assert (reindexed_path / "index_manifest.json").exists()
