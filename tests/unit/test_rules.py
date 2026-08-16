from __future__ import annotations

from agentguard.anomaly.rules import evaluate_rules
from agentguard.schemas.anomaly import AnomalyType, Severity

BASE_FEATURES: dict[str, float] = {
    "tool_call_count": 4,
    "denied_count": 0,
    "max_consecutive_repeats": 0,
    "total_tokens": 500,
    "injection_lexical_score": 0.0,
}


def _features(**overrides: float) -> dict[str, float]:
    return {**BASE_FEATURES, **overrides}


def test_no_rules_triggered_for_normal_features() -> None:
    result = evaluate_rules(_features())
    assert result.triggered_rules == []
    assert result.rule_floor == 0.0
    assert result.suggested_type is None


def test_r001_hard_call_limit() -> None:
    result = evaluate_rules(_features(tool_call_count=41))
    assert "R001_hard_call_limit" in result.triggered_rules
    assert result.rule_floor == 0.85


def test_r002_denied_access() -> None:
    result = evaluate_rules(_features(denied_count=1))
    assert "R002_denied_access" in result.triggered_rules
    assert result.suggested_type == AnomalyType.PERMISSION_VIOLATION
    assert result.min_severity == Severity.HIGH


def test_r003_repeat_burst() -> None:
    result = evaluate_rules(_features(max_consecutive_repeats=5))
    assert "R003_repeat_burst" in result.triggered_rules
    assert result.suggested_type == AnomalyType.TOOL_LOOP


def test_r004_token_ceiling() -> None:
    result = evaluate_rules(_features(total_tokens=15001))
    assert "R004_token_ceiling" in result.triggered_rules
    assert result.suggested_type == AnomalyType.TOKEN_SPIKE


def test_r005_injection_lexical() -> None:
    result = evaluate_rules(_features(injection_lexical_score=0.9))
    assert "R005_injection_lexical" in result.triggered_rules
    assert result.suggested_type == AnomalyType.PROMPT_INJECTION
    assert result.min_severity == Severity.HIGH


def test_multiple_rules_combine_and_first_type_wins() -> None:
    result = evaluate_rules(
        _features(tool_call_count=50, max_consecutive_repeats=6, denied_count=2)
    )
    assert set(result.triggered_rules) == {
        "R001_hard_call_limit",
        "R002_denied_access",
        "R003_repeat_burst",
    }
    # R002 kod sırasında R003'ten önce değerlendirilir -> suggested_type ilk atanan kalır
    assert result.suggested_type == AnomalyType.PERMISSION_VIOLATION
    assert result.rule_floor == 0.85
