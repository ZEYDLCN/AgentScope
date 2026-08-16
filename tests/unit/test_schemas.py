from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from agentguard.schemas.anomaly import AnomalyResult, Severity
from agentguard.schemas.investigation import EvidenceItem, Investigation, Recommendation
from agentguard.schemas.trace import AgentTrace, ToolCall, ToolStatus

FIXTURES = Path(__file__).parent.parent / "fixtures" / "traces"


def load_fixture(name: str) -> AgentTrace:
    data = json.loads((FIXTURES / name).read_text())
    return AgentTrace.model_validate(data)


def test_normal_trace_fixture_parses() -> None:
    trace = load_fixture("normal_trace.json")
    assert trace.trace_id == "trace-normal-0001"
    assert len(trace.tool_calls) == 2
    assert trace.token_usage.total_tokens == 450


def test_tool_call_rejects_negative_time_span() -> None:
    with pytest.raises(ValidationError):
        ToolCall(
            index=0,
            tool_name="db.query",
            started_at=datetime(2026, 1, 1, 10, 0, 5),
            ended_at=datetime(2026, 1, 1, 10, 0, 0),
            status=ToolStatus.OK,
            duration_ms=10,
            input_hash="abc123",
        )


def test_trace_rejects_negative_time_span() -> None:
    with pytest.raises(ValidationError):
        AgentTrace(
            trace_id="trace-bad-000001",
            agent_id="agent",
            started_at=datetime(2026, 1, 1, 10, 0, 5),
            ended_at=datetime(2026, 1, 1, 10, 0, 0),
            token_usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )


def test_trace_id_pattern_enforced() -> None:
    with pytest.raises(ValidationError):
        AgentTrace(
            trace_id="short",
            agent_id="agent",
            started_at=datetime(2026, 1, 1, 10, 0, 0),
            ended_at=datetime(2026, 1, 1, 10, 0, 1),
            token_usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )


def test_investigation_requires_at_least_one_evidence_and_recommendation() -> None:
    with pytest.raises(ValidationError):
        Investigation(
            trace_id="trace-normal-0001",
            anomaly_type="tool_loop",
            severity=Severity.HIGH,
            confidence=0.8,
            root_cause="tekrarlanan araç çağrıları",
            evidence=[],
            recommendations=[Recommendation(action="terminate", priority=1, rationale="loop")],
            model_name="qwen2.5:7b",
            prompt_version="inv-v1",
            latency_ms=1200,
            generated_at=datetime(2026, 8, 15, 9, 0, 30),
        )


def test_investigation_valid_payload() -> None:
    inv = Investigation(
        trace_id="trace-normal-0001",
        anomaly_type="tool_loop",
        severity=Severity.HIGH,
        confidence=0.8,
        root_cause="tekrarlanan araç çağrıları",
        evidence=[EvidenceItem(statement="19 tekrar", source="trace:repeated_call_count")],
        recommendations=[Recommendation(action="terminate", priority=1, rationale="loop")],
        model_name="qwen2.5:7b",
        prompt_version="inv-v1",
        latency_ms=1200,
        generated_at=datetime(2026, 8, 15, 9, 0, 30),
    )
    assert inv.generated_by == "llm"


def test_anomaly_result_score_bounds() -> None:
    with pytest.raises(ValidationError):
        AnomalyResult(
            trace_id="trace-normal-0001",
            is_anomaly=True,
            score=1.5,
            severity=Severity.HIGH,
            threshold=0.5,
            detected_at=datetime(2026, 8, 15, 9, 0, 30),
        )
