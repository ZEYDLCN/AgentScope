"""InvestigationService uçtan uca testleri — gerçek Ollama ağ erişimi
gerektirdiğinden `FakeLLMClient` kullanılır (§22.3: "FakeLLMClient: sabit
JSON döndürür → LLM'siz hızlı CI")."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from agentguard.anomaly.rules import evaluate_rules
from agentguard.llm.ollama_client import LLMUnavailableError
from agentguard.schemas.anomaly import AnomalyResult, DetectorScore, Severity
from agentguard.schemas.trace import AgentTrace, TokenUsage, ToolCall, ToolStatus
from agentguard.services.investigation import InvestigationService

VALID_LLM_JSON = json.dumps(
    {
        "anomaly_type": "tool_loop",
        "severity": "high",
        "confidence": 0.85,
        "root_cause": "Repeated database queries with identical input indicate a retry loop.",
        "evidence": [{"statement": "19 tekrarlanan çağrı", "source": "[T2]"}],
        "recommendations": [
            {"action": "Agent'ı sonlandır", "priority": 1, "rationale": "Aktif döngü"}
        ],
    }
)


class FakeLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0

    async def generate(self, *, system_prompt: str, user_prompt: str, json_schema: dict) -> str:  # type: ignore[type-arg]
        self.calls += 1
        if not self._responses:
            raise LLMUnavailableError("fake: yanıt tükendi")
        return self._responses.pop(0)

    async def warmup(self) -> None:
        pass

    async def aclose(self) -> None:
        pass


def _loop_trace() -> AgentTrace:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    calls = [
        ToolCall(
            index=i,
            tool_name="db.query",
            started_at=base,
            ended_at=base,
            status=ToolStatus.OK,
            duration_ms=100,
            input_hash="same-hash",
        )
        for i in range(20)
    ]
    return AgentTrace(
        trace_id="trace-investigate-000001",
        agent_id="agent-01",
        started_at=base,
        ended_at=base,
        tool_calls=calls,
        token_usage=TokenUsage(prompt_tokens=1000, completion_tokens=500, total_tokens=1500),
    )


def _anomaly_result(trace: AgentTrace) -> AnomalyResult:
    return AnomalyResult(
        trace_id=trace.trace_id,
        is_anomaly=True,
        score=0.95,
        severity=Severity.HIGH,
        detector_scores=[
            DetectorScore(
                detector="isolation_forest",
                raw_score=1.2,
                normalized_score=0.95,
                model_version="v1",
            )
        ],
        triggered_rules=["R003_repeat_burst"],
        threshold=0.7,
        detected_at=datetime.now(UTC),
    )


async def test_investigate_success_on_first_attempt() -> None:
    from agentguard.features.extractor import FeatureExtractor

    trace = _loop_trace()
    raw_features = FeatureExtractor(bigram_vocabulary=set()).extract_raw(trace)
    rule_eval = evaluate_rules(raw_features)
    anomaly_result = _anomaly_result(trace)

    llm = FakeLLMClient([VALID_LLM_JSON])
    service = InvestigationService(llm, rag=None, model_name="fake-model")

    outcome = await service.investigate(trace, raw_features, anomaly_result, rule_eval)

    assert outcome.generated_by == "llm"
    assert outcome.schema_valid_first_try is True
    assert outcome.investigation.severity == Severity.HIGH  # dedektörden
    assert llm.calls == 1


async def test_investigate_retries_then_succeeds() -> None:
    from agentguard.features.extractor import FeatureExtractor

    trace = _loop_trace()
    raw_features = FeatureExtractor(bigram_vocabulary=set()).extract_raw(trace)
    rule_eval = evaluate_rules(raw_features)
    anomaly_result = _anomaly_result(trace)

    llm = FakeLLMClient(["bozuk json ```", "yine bozuk", VALID_LLM_JSON])
    service = InvestigationService(llm, rag=None, model_name="fake-model")

    outcome = await service.investigate(trace, raw_features, anomaly_result, rule_eval)

    assert outcome.generated_by == "llm"
    assert outcome.schema_valid_first_try is False
    assert llm.calls == 3


async def test_investigate_falls_back_after_exhausting_retries() -> None:
    from agentguard.features.extractor import FeatureExtractor

    trace = _loop_trace()
    raw_features = FeatureExtractor(bigram_vocabulary=set()).extract_raw(trace)
    rule_eval = evaluate_rules(raw_features)
    anomaly_result = _anomaly_result(trace)

    llm = FakeLLMClient(["hep bozuk", "hep bozuk", "hep bozuk"])
    service = InvestigationService(llm, rag=None, model_name="fake-model")

    outcome = await service.investigate(trace, raw_features, anomaly_result, rule_eval)

    assert outcome.generated_by == "fallback"
    assert outcome.investigation.severity == Severity.HIGH  # dedektörden, fallback'te de korunur


async def test_investigate_falls_back_immediately_on_llm_unavailable() -> None:
    from agentguard.features.extractor import FeatureExtractor

    trace = _loop_trace()
    raw_features = FeatureExtractor(bigram_vocabulary=set()).extract_raw(trace)
    rule_eval = evaluate_rules(raw_features)
    anomaly_result = _anomaly_result(trace)

    llm = FakeLLMClient([])  # ilk çağrıda LLMUnavailableError fırlatır
    service = InvestigationService(llm, rag=None, model_name="fake-model")

    outcome = await service.investigate(trace, raw_features, anomaly_result, rule_eval)

    assert outcome.generated_by == "fallback"
    assert llm.calls == 1
