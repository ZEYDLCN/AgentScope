"""Deterministik guardrail kuralları — §7.3.

Bazı olaylar ML'e bırakılmayacak kadar nettir. Nihai skor:
`final_score = max(ml_score, rule_floor)`. Tetiklenen kurallar
`AnomalyResult.triggered_rules` içinde şeffaf şekilde raporlanır.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agentguard.schemas.anomaly import AnomalyType, Severity

HARD_CALL_LIMIT = 40
REPEAT_BURST_THRESHOLD = 5
TOKEN_CEILING = 15000
INJECTION_LEXICAL_THRESHOLD = 0.6


@dataclass
class RuleEvaluation:
    triggered_rules: list[str] = field(default_factory=list)
    rule_floor: float = 0.0
    suggested_type: AnomalyType | None = None
    min_severity: Severity | None = None


_SEVERITY_ORDER = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]


def _max_severity(a: Severity | None, b: Severity) -> Severity:
    if a is None:
        return b
    return a if _SEVERITY_ORDER.index(a) >= _SEVERITY_ORDER.index(b) else b


def evaluate_rules(raw_features: dict[str, float]) -> RuleEvaluation:
    result = RuleEvaluation()

    if raw_features["tool_call_count"] > HARD_CALL_LIMIT:
        result.triggered_rules.append("R001_hard_call_limit")
        result.rule_floor = max(result.rule_floor, 0.85)

    if raw_features["denied_count"] > 0:
        result.triggered_rules.append("R002_denied_access")
        result.min_severity = _max_severity(result.min_severity, Severity.HIGH)
        result.suggested_type = result.suggested_type or AnomalyType.PERMISSION_VIOLATION

    if raw_features["max_consecutive_repeats"] >= REPEAT_BURST_THRESHOLD:
        result.triggered_rules.append("R003_repeat_burst")
        result.suggested_type = result.suggested_type or AnomalyType.TOOL_LOOP

    if raw_features["total_tokens"] > TOKEN_CEILING:
        result.triggered_rules.append("R004_token_ceiling")
        result.suggested_type = result.suggested_type or AnomalyType.TOKEN_SPIKE

    if raw_features["injection_lexical_score"] > INJECTION_LEXICAL_THRESHOLD:
        result.triggered_rules.append("R005_injection_lexical")
        result.suggested_type = result.suggested_type or AnomalyType.PROMPT_INJECTION
        result.min_severity = _max_severity(result.min_severity, Severity.HIGH)

    return result
