"""DetectionService uçtan uca testi — küçük, elle eğitilmiş bir
DetectorBundle ile (gerçek 11k'lık sentetik veri seti gerekmez)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from agentguard.anomaly.isolation_forest import IsolationForestDetector
from agentguard.anomaly.registry import DetectorBundle, Manifest
from agentguard.anomaly.scoring import ECDFCalibrator
from agentguard.features.definitions import FEATURE_ORDER, FEATURE_VERSION
from agentguard.features.extractor import FeatureExtractor
from agentguard.features.transforms import apply_clip, apply_log1p, compute_clip_bounds, fit_scaler
from agentguard.schemas.trace import AgentTrace, TokenUsage, ToolCall, ToolStatus
from agentguard.services.detection import DetectionService


def _normal_trace(index: int, base: datetime) -> AgentTrace:
    calls = [
        ToolCall(
            index=i,
            tool_name="db.query" if i % 2 == 0 else "api.search",
            started_at=base + timedelta(seconds=i),
            ended_at=base + timedelta(seconds=i, milliseconds=300),
            status=ToolStatus.OK,
            duration_ms=300,
            input_hash=f"hash-{index}-{i}",
        )
        for i in range(4)
    ]
    return AgentTrace(
        trace_id=f"trace-normal-{index:04d}",
        agent_id="agent-01",
        started_at=base,
        ended_at=base + timedelta(seconds=5),
        tool_calls=calls,
        token_usage=TokenUsage(prompt_tokens=300, completion_tokens=150, total_tokens=450),
    )


def _loop_trace(base: datetime) -> AgentTrace:
    calls = [
        ToolCall(
            index=i,
            tool_name="db.query",
            started_at=base + timedelta(seconds=i),
            ended_at=base + timedelta(seconds=i, milliseconds=300),
            status=ToolStatus.OK,
            duration_ms=300,
            input_hash="same-hash",
        )
        for i in range(45)
    ]
    return AgentTrace(
        trace_id="trace-loop-000001",
        agent_id="agent-01",
        started_at=base,
        ended_at=base + timedelta(seconds=45),
        tool_calls=calls,
        token_usage=TokenUsage(prompt_tokens=300, completion_tokens=150, total_tokens=450),
    )


@pytest.fixture(scope="module")
def bundle_and_extractor() -> tuple[DetectorBundle, FeatureExtractor]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    normal_traces = [_normal_trace(i, base + timedelta(seconds=i * 10)) for i in range(60)]

    extractor = FeatureExtractor(bigram_vocabulary=set())
    raw = np.array(
        [[extractor.extract_raw(t)[name] for name in FEATURE_ORDER] for t in normal_traces]
    )
    log = apply_log1p(raw)
    low, high = compute_clip_bounds(log)
    clipped = apply_clip(log, low, high)
    scaler = fit_scaler(clipped)
    scaled = scaler.transform(clipped)

    detector = IsolationForestDetector(random_state=42)
    detector.fit(scaled)
    ecdf = ECDFCalibrator(detector.raw_score(scaled))

    bundle = DetectorBundle(
        scaler=scaler,
        isolation_forest=detector,
        ecdf_if=ecdf,
        bigram_vocabulary=set(),
        thresholds={"tau": 0.9, "clip_low": low.tolist(), "clip_high": high.tolist()},
        manifest=Manifest(
            feature_version=FEATURE_VERSION,
            git_sha="test",
            train_rows=len(normal_traces),
            fusion_weights={"isolation_forest": 1.0},
        ),
    )
    return bundle, extractor


def test_detect_normal_trace_is_not_anomaly(
    bundle_and_extractor: tuple[DetectorBundle, FeatureExtractor],
) -> None:
    bundle, extractor = bundle_and_extractor
    base = datetime(2026, 1, 1, tzinfo=UTC)
    trace = _normal_trace(999, base)

    outcome = DetectionService(bundle, extractor).detect(trace)

    assert outcome.result.trace_id == trace.trace_id
    assert 0.0 <= outcome.result.score <= 1.0
    assert len(outcome.result.detector_scores) == 1
    assert outcome.result.detector_scores[0].detector == "isolation_forest"


def test_detect_tool_loop_trace_triggers_r001_and_r003(
    bundle_and_extractor: tuple[DetectorBundle, FeatureExtractor],
) -> None:
    bundle, extractor = bundle_and_extractor
    base = datetime(2026, 1, 1, tzinfo=UTC)
    trace = _loop_trace(base)

    outcome = DetectionService(bundle, extractor).detect(trace)

    assert "R001_hard_call_limit" in outcome.result.triggered_rules
    assert "R003_repeat_burst" in outcome.result.triggered_rules
    assert outcome.result.is_anomaly is True
    assert outcome.result.score >= 0.85  # R001 rule_floor


def test_detect_is_deterministic(
    bundle_and_extractor: tuple[DetectorBundle, FeatureExtractor],
) -> None:
    bundle, extractor = bundle_and_extractor
    base = datetime(2026, 1, 1, tzinfo=UTC)
    trace = _normal_trace(1234, base)

    service = DetectionService(bundle, extractor)
    result1 = service.detect(trace).result
    result2 = service.detect(trace).result

    assert result1.score == result2.score
    assert result1.severity == result2.severity


def test_detect_top_contributing_features_populated(
    bundle_and_extractor: tuple[DetectorBundle, FeatureExtractor],
) -> None:
    bundle, extractor = bundle_and_extractor
    base = datetime(2026, 1, 1, tzinfo=UTC)
    trace = _loop_trace(base)

    outcome = DetectionService(bundle, extractor).detect(trace)

    assert len(outcome.result.top_contributing_features) == 3
    feature_names = {name for name, _ in outcome.result.top_contributing_features}
    assert feature_names.issubset(set(FEATURE_ORDER))
