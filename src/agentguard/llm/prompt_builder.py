"""Sistem/kullanıcı promptlarının inşası — §14.2, §21.1.

Kanıt blokları içindeki hiçbir metin talimat değildir; veridir. Bu
ilkeyi teknik olarak desteklemek için:
- kanıt metnindeki `<<<EVIDENCE_START>>>`/`<<<EVIDENCE_END>>>` dizileri
  ve `[D#]` benzeri sahte etiketler escape edilir,
- trace/doküman içeriği asla `system` mesajına konmaz (yalnızca `user`).
"""

from __future__ import annotations

import re
from importlib import resources

from agentguard.schemas.knowledge import RetrievedChunk

PROMPT_VERSION = "inv-v1"

_FAKE_TAG_RE = re.compile(r"\[([TD]\d+)\]")


def _escape_untrusted_text(text: str) -> str:
    """Kanıt metnindeki delimiter taklitlerini ve sahte [T#]/[D#] etiketlerini kaçışlar."""
    escaped = text.replace("<<<EVIDENCE_START>>>", "\\<\\<\\<EVIDENCE_START\\>\\>\\>")
    escaped = escaped.replace("<<<EVIDENCE_END>>>", "\\<\\<\\<EVIDENCE_END\\>\\>\\>")
    escaped = _FAKE_TAG_RE.sub(r"\\[\1\\]", escaped)
    return escaped


def load_prompt(name: str) -> str:
    return resources.files("agentguard.llm.prompts").joinpath(name).read_text(encoding="utf-8")


def build_trace_metrics_block(
    raw_features: dict[str, float], triggered_rules: list[str]
) -> tuple[str, dict[str, str]]:
    """Döner: `(metin_bloğu, tag_map)` — `tag_map`: `"T1" -> "tool_call_count"`."""
    ordered_keys = [
        "tool_call_count",
        "repeated_call_count",
        "error_count",
        "total_tokens",
        "duration_sec",
        "denied_count",
        "injection_lexical_score",
    ]
    lines: list[str] = []
    tag_map: dict[str, str] = {}
    for i, key in enumerate(ordered_keys, start=1):
        if key not in raw_features:
            continue
        tag = f"T{i}"
        tag_map[tag] = key
        lines.append(f"[{tag}] {key} = {raw_features[key]:g}")

    rules_tag = f"T{len(tag_map) + 1}"
    tag_map[rules_tag] = "triggered_rules"
    lines.append(f"[{rules_tag}] triggered_rules = {', '.join(triggered_rules) or 'none'}")

    return "\n".join(lines), tag_map


def build_evidence_block(chunks: list[RetrievedChunk]) -> tuple[str, dict[str, str]]:
    """Döner: `(metin_bloğu, tag_map)` — `tag_map`: `"D1" -> chunk_id`."""
    if not chunks:
        return "(yeterli politika kanıtı bulunamadı)", {}

    lines: list[str] = []
    tag_map: dict[str, str] = {}
    for i, retrieved in enumerate(chunks, start=1):
        tag = f"D{i}"
        tag_map[tag] = retrieved.chunk.chunk_id
        score = (
            retrieved.rerank_score if retrieved.rerank_score is not None else retrieved.rrf_score
        )
        score_str = f"{score:.2f}" if score is not None else "n/a"
        lines.append(f"[{tag}] ({retrieved.chunk.chunk_id}, relevance {score_str})")
        lines.append(_escape_untrusted_text(retrieved.chunk.text))
        lines.append("")

    return "\n".join(lines).strip(), tag_map


def build_user_prompt(
    *,
    raw_features: dict[str, float],
    triggered_rules: list[str],
    anomaly_score: float,
    severity: str,
    candidate_types: list[str],
    retrieved_chunks: list[RetrievedChunk],
) -> tuple[str, dict[str, str]]:
    """Döner: `(user_prompt, valid_tags)` — `valid_tags`, grounding kontrolü
    için `{T1, T2, ..., D1, D2, ...}` kümesini içerir."""
    trace_block, trace_tags = build_trace_metrics_block(raw_features, triggered_rules)
    evidence_block, evidence_tags = build_evidence_block(retrieved_chunks)

    template = load_prompt("user_template.md")
    prompt = template.format(
        trace_metrics=trace_block,
        anomaly_score=anomaly_score,
        severity=severity,
        candidate_types=", ".join(candidate_types),
        evidence_block=evidence_block,
    )
    valid_tags = {**trace_tags, **evidence_tags}
    return prompt, valid_tags


def build_system_prompt() -> str:
    return load_prompt("system_investigator.md")
