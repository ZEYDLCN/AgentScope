from __future__ import annotations

from agentguard.rag.query_builder import (
    build_investigation_query,
    derive_candidate_types,
    dominant_tool,
)


def test_derive_candidate_types_maps_rules_deterministically() -> None:
    types = derive_candidate_types(["R003_repeat_burst", "R002_denied_access"])
    assert types == ["tool_loop", "permission_violation"]


def test_derive_candidate_types_dedupes_preserving_order() -> None:
    types = derive_candidate_types(["R001_hard_call_limit", "R003_repeat_burst"])
    assert types == ["tool_loop"]


def test_derive_candidate_types_empty_rules_returns_unknown() -> None:
    assert derive_candidate_types([]) == ["unknown"]


def test_dominant_tool_returns_most_common() -> None:
    assert dominant_tool(["db.query", "db.query", "api.search"]) == "db.query"


def test_dominant_tool_empty_list_returns_unknown() -> None:
    assert dominant_tool([]) == "unknown"


def test_build_investigation_query_contains_key_facts() -> None:
    query, candidate_types = build_investigation_query(
        agent_id="agent-01",
        tool_call_count=47,
        repeated_call_count=19,
        unique_tool_count=1,
        error_count=14,
        total_tokens=18400,
        duration_sec=82.0,
        tool_names=["db.query"] * 47,
        triggered_rules=["R001_hard_call_limit", "R003_repeat_burst"],
    )
    assert "agent-01" in query
    assert "47 tool calls" in query
    assert "19 repeated" in query
    assert "db.query" in query
    assert candidate_types == ["tool_loop"]


def test_build_investigation_query_no_rules_says_none() -> None:
    query, candidate_types = build_investigation_query(
        agent_id="agent-02",
        tool_call_count=4,
        repeated_call_count=0,
        unique_tool_count=3,
        error_count=0,
        total_tokens=500,
        duration_sec=5.0,
        tool_names=["db.query", "api.search", "file.read"],
        triggered_rules=[],
    )
    assert "Triggered signals: none" in query
    assert candidate_types == ["unknown"]
