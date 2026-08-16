"""Soruşturma sorgusu inşası — §12.1.

Ham trace LLM'e değil, önce şablonlu bir doğal dil sorgusuna dönüştürülür.
`candidate_types`, kural katmanından **deterministik** olarak türetilir —
LLM kullanılmaz; retrieval, açıklama üretiminden önce gelmelidir.
"""

from __future__ import annotations

from collections import Counter

QUERY_TEMPLATE = (
    "Agent {agent_id} made {tool_calls} tool calls "
    "({repeated} repeated, {unique} unique tools) with {errors} errors "
    "and {tokens} tokens in {duration:.0f} seconds. "
    "Dominant tool: {top_tool}. Triggered signals: {rule_names}. "
    "Suspected behavior: {candidate_types}."
)

# Kural adı -> AnomalyType değeri (rules.py ile hizalı, §7.3)
RULE_TO_TYPE: dict[str, str] = {
    "R001_hard_call_limit": "tool_loop",
    "R002_denied_access": "permission_violation",
    "R003_repeat_burst": "tool_loop",
    "R004_token_ceiling": "token_spike",
    "R005_injection_lexical": "prompt_injection",
}


def derive_candidate_types(triggered_rules: list[str]) -> list[str]:
    """Tetiklenen kurallardan deterministik aday anomali tipleri türetir."""
    types = [RULE_TO_TYPE[r] for r in triggered_rules if r in RULE_TO_TYPE]
    # Sırayı koruyarak tekrarları kaldır
    seen: set[str] = set()
    ordered: list[str] = []
    for t in types:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered or ["unknown"]


def dominant_tool(tool_names: list[str]) -> str:
    if not tool_names:
        return "unknown"
    return Counter(tool_names).most_common(1)[0][0]


def build_investigation_query(
    *,
    agent_id: str,
    tool_call_count: int,
    repeated_call_count: int,
    unique_tool_count: int,
    error_count: int,
    total_tokens: int,
    duration_sec: float,
    tool_names: list[str],
    triggered_rules: list[str],
) -> tuple[str, list[str]]:
    """Döner: `(sorgu_metni, candidate_types)`."""
    candidate_types = derive_candidate_types(triggered_rules)
    query = QUERY_TEMPLATE.format(
        agent_id=agent_id,
        tool_calls=tool_call_count,
        repeated=repeated_call_count,
        unique=unique_tool_count,
        errors=error_count,
        tokens=total_tokens,
        duration=duration_sec,
        top_tool=dominant_tool(tool_names),
        rule_names=", ".join(triggered_rules) if triggered_rules else "none",
        candidate_types=", ".join(candidate_types),
    )
    return query, candidate_types
