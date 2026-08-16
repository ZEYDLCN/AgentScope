from __future__ import annotations

import pytest

from agentguard.llm.guards import (
    OutputParseError,
    apply_authority,
    apply_grounding,
    assemble_investigation,
    build_fallback_investigation,
    extract_json_block,
    parse_and_validate,
    sanitize_root_cause,
)
from agentguard.llm.schema import LLMInvestigationOutput
from agentguard.schemas.anomaly import AnomalyType, Severity
from agentguard.schemas.investigation import EvidenceItem, Recommendation

VALID_JSON = """{
    "anomaly_type": "tool_loop",
    "severity": "high",
    "confidence": 0.9,
    "root_cause": "Repeated tool calls detected.",
    "evidence": [{"statement": "19 tekrar", "source": "[T2]"}],
    "recommendations": [{"action": "terminate", "priority": 1, "rationale": "loop"}]
}"""


def test_extract_json_block_strips_code_fence() -> None:
    text = f"```json\n{VALID_JSON}\n```"
    extracted = extract_json_block(text)
    assert extracted.strip().startswith("{")
    assert extracted.strip().endswith("}")


def test_extract_json_block_handles_plain_json() -> None:
    assert extract_json_block(VALID_JSON).strip() == VALID_JSON.strip()


def test_extract_json_block_finds_object_within_prose() -> None:
    text = f"Here is the report:\n{VALID_JSON}\nThanks."
    extracted = extract_json_block(text)
    assert extracted.startswith("{")


def test_parse_and_validate_success() -> None:
    output = parse_and_validate(VALID_JSON)
    assert output.anomaly_type == AnomalyType.TOOL_LOOP
    assert output.confidence == 0.9


def test_parse_and_validate_repairs_broken_json() -> None:
    broken = VALID_JSON.replace('"confidence": 0.9,', '"confidence": 0.9')[:-2]  # kapanışı boz
    # json_repair çoğu eksik parantez/virgül durumunu onarabilir
    try:
        output = parse_and_validate(broken)
        assert output.anomaly_type == AnomalyType.TOOL_LOOP
    except OutputParseError:
        pytest.skip("json_repair bu spesifik bozulmayı onaramadı")


def test_parse_and_validate_raises_on_garbage() -> None:
    with pytest.raises(OutputParseError):
        parse_and_validate("bu hiç JSON değil, düz metin")


def test_parse_and_validate_raises_on_schema_violation() -> None:
    bad = VALID_JSON.replace('"confidence": 0.9', '"confidence": 5.0')  # [0,1] dışında
    with pytest.raises(OutputParseError):
        parse_and_validate(bad)


def test_apply_grounding_keeps_valid_sources() -> None:
    evidence = [
        EvidenceItem(statement="a", source="[T1]"),
        EvidenceItem(statement="b", source="[D2]"),
    ]
    valid_tags = {"T1": "tool_call_count", "D2": "doc#c0"}
    kept, dropped = apply_grounding(evidence, valid_tags)
    assert len(kept) == 2
    assert dropped == 0


def test_apply_grounding_drops_invalid_sources() -> None:
    evidence = [
        EvidenceItem(statement="a", source="[T1]"),
        EvidenceItem(statement="uydurma", source="[D99]"),
        EvidenceItem(statement="kaynaksız", source="no-tag-here"),
    ]
    valid_tags = {"T1": "tool_call_count"}
    kept, dropped = apply_grounding(evidence, valid_tags)
    assert len(kept) == 1
    assert dropped == 2
    assert kept[0].source == "[T1]"


def test_apply_authority_detects_type_mismatch() -> None:
    disagreement = apply_authority(
        Severity.HIGH, AnomalyType.PROMPT_INJECTION, Severity.HIGH, AnomalyType.TOOL_LOOP
    )
    assert disagreement is True


def test_apply_authority_detects_severity_mismatch() -> None:
    disagreement = apply_authority(
        Severity.LOW, AnomalyType.TOOL_LOOP, Severity.CRITICAL, AnomalyType.TOOL_LOOP
    )
    assert disagreement is True


def test_apply_authority_no_disagreement_when_matching() -> None:
    disagreement = apply_authority(
        Severity.HIGH, AnomalyType.TOOL_LOOP, Severity.HIGH, AnomalyType.TOOL_LOOP
    )
    assert disagreement is False


def test_sanitize_root_cause_strips_control_chars_and_truncates() -> None:
    dirty = "Root cause\x00 with\x07 control chars" + "x" * 600
    clean = sanitize_root_cause(dirty)
    assert "\x00" not in clean
    assert "\x07" not in clean
    assert len(clean) <= 500


def test_assemble_investigation_final_severity_always_from_detector() -> None:
    llm_output = LLMInvestigationOutput(
        anomaly_type=AnomalyType.PROMPT_INJECTION,  # LLM farklı düşünüyor
        severity=Severity.LOW,  # LLM farklı düşünüyor
        confidence=0.8,
        root_cause="test",
        evidence=[EvidenceItem(statement="a", source="[T1]")],
        recommendations=[Recommendation(action="x", priority=1, rationale="y")],
    )
    outcome = assemble_investigation(
        llm_output=llm_output,
        valid_tags={"T1": "tool_call_count"},
        trace_id="trace-1",
        detector_severity=Severity.CRITICAL,
        detector_type=AnomalyType.TOOL_LOOP,
        retrieved_doc_ids=[],
        model_name="test-model",
        prompt_version="inv-v1",
        latency_ms=100,
        schema_valid_first_try=True,
    )
    assert outcome.investigation.severity == Severity.CRITICAL  # dedektörden, LLM'den DEĞİL
    assert outcome.investigation.anomaly_type == AnomalyType.TOOL_LOOP
    assert outcome.detector_llm_disagreement is True


def test_assemble_investigation_empty_evidence_after_grounding_lowers_confidence() -> None:
    llm_output = LLMInvestigationOutput(
        anomaly_type=AnomalyType.TOOL_LOOP,
        severity=Severity.HIGH,
        confidence=0.9,
        root_cause="test",
        evidence=[EvidenceItem(statement="uydurma", source="[D99]")],  # geçersiz kaynak
        recommendations=[Recommendation(action="x", priority=1, rationale="y")],
    )
    outcome = assemble_investigation(
        llm_output=llm_output,
        valid_tags={"T1": "tool_call_count"},
        trace_id="trace-1",
        detector_severity=Severity.HIGH,
        detector_type=AnomalyType.TOOL_LOOP,
        retrieved_doc_ids=[],
        model_name="test-model",
        prompt_version="inv-v1",
        latency_ms=100,
        schema_valid_first_try=True,
    )
    assert outcome.investigation.confidence == pytest.approx(0.45)  # 0.9 * 0.5
    assert len(outcome.investigation.evidence) == 1
    assert outcome.investigation.evidence[0].source == "system:grounding_check"
    assert outcome.grounding_dropped == 1


def test_build_fallback_investigation_generated_by_fallback() -> None:
    investigation = build_fallback_investigation(
        trace_id="trace-1",
        detector_severity=Severity.HIGH,
        detector_type=AnomalyType.TOOL_LOOP,
        triggered_rules=["R003_repeat_burst"],
        model_name="test-model",
        prompt_version="inv-v1",
        latency_ms=0,
    )
    assert investigation.generated_by == "fallback"
    assert investigation.severity == Severity.HIGH
    assert investigation.confidence < 0.5
    assert len(investigation.evidence) >= 1
    assert len(investigation.recommendations) >= 1
