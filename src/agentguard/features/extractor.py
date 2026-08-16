"""Özellik çıkarımı — §7.

Kritik kurallar:
- Tekrar tanımı: `repeated_call_count`/`max_consecutive_repeats`, aynı
  `tool_name` **ve** aynı `input_hash` eşleşmesine dayanır (§7.2) — yalnızca
  ad eşleşmesi meşru sayfalamayı yanlış pozitif yapar.
- `bigram_novelty`, eğitim aşamasında hesaplanan sabit bir bigram sözlüğüne
  bağlıdır (`artifacts/.../bigrams.json`); inference'ta yeniden hesaplanmaz.
- Sıfıra bölme: tüm oranlarda `max(1, x)` payda koruması.
"""

from __future__ import annotations

import math
import re
from collections import Counter

from agentguard.features.definitions import (
    API_PREFIXES,
    DB_PREFIX,
    FEATURE_ORDER,
    FILE_PREFIX,
    INJECTION_LEXICAL_PATTERNS,
    RESTRICTED_TOOLS,
)
from agentguard.schemas.features import FeatureVector
from agentguard.schemas.trace import AgentTrace, ToolStatus

_INJECTION_RE = re.compile(
    "|".join(re.escape(p) for p in INJECTION_LEXICAL_PATTERNS), re.IGNORECASE
)


def _tool_bigrams(tool_names: list[str]) -> list[tuple[str, str]]:
    return [(tool_names[i], tool_names[i + 1]) for i in range(len(tool_names) - 1)]


def build_bigram_vocabulary(traces: list[AgentTrace]) -> set[tuple[str, str]]:
    """Eğitim (normal) trace'lerinden bigram sözlüğü çıkarır (model artefaktı)."""
    vocab: set[tuple[str, str]] = set()
    for trace in traces:
        names = [c.tool_name for c in sorted(trace.tool_calls, key=lambda c: c.index)]
        vocab.update(_tool_bigrams(names))
    return vocab


def injection_lexical_score(text: str | None) -> float:
    if not text:
        return 0.0
    matches = len(_INJECTION_RE.findall(text))
    return min(1.0, matches / 2.0)


class FeatureExtractor:
    """Ham (dönüşümsüz) 24 boyutlu özellik vektörü üretir.

    log1p/clip/scale adımları `features/transforms.py`'de, bu sınıfın
    çıktısı üzerinde ayrıca uygulanır — extractor yalnızca trace'ten ham
    sayıları türetir.
    """

    def __init__(self, bigram_vocabulary: set[tuple[str, str]]) -> None:
        self._bigrams = bigram_vocabulary

    def extract_raw(self, trace: AgentTrace) -> dict[str, float]:
        calls = sorted(trace.tool_calls, key=lambda c: c.index)
        n_calls = len(calls)
        names = [c.tool_name for c in calls]
        durations = [c.duration_ms for c in calls]

        unique_tools = len(set(names))
        errors = sum(1 for c in calls if c.status == ToolStatus.ERROR)
        timeouts = sum(1 for c in calls if c.status == ToolStatus.TIMEOUT)
        denied = sum(1 for c in calls if c.status == ToolStatus.DENIED)

        repeated_count, max_consecutive = self._repeat_stats(calls)
        distinct_inputs = len({c.input_hash for c in calls})

        db_count = sum(1 for n in names if n.startswith(DB_PREFIX))
        api_count = sum(1 for n in names if n.startswith(API_PREFIXES))
        file_count = sum(1 for n in names if n.startswith(FILE_PREFIX))
        restricted_count = sum(1 for n in names if n in RESTRICTED_TOOLS)

        duration_sec = max(0.001, (trace.ended_at - trace.started_at).total_seconds())
        p95_duration = self._percentile(durations, 95) if durations else 0.0
        mean_duration = sum(durations) / max(1, n_calls) if durations else 0.0

        bigrams = _tool_bigrams(names)
        novel = sum(1 for bg in bigrams if bg not in self._bigrams)
        bigram_novelty = novel / max(1, len(bigrams)) if bigrams else 0.0

        raw: dict[str, float] = {
            "tool_call_count": float(n_calls),
            "unique_tool_count": float(unique_tools),
            "tool_diversity_ratio": unique_tools / max(1, n_calls),
            "duration_sec": duration_sec,
            "mean_tool_duration_ms": mean_duration,
            "p95_tool_duration_ms": p95_duration,
            "total_tokens": float(trace.token_usage.total_tokens),
            "tokens_per_call": trace.token_usage.total_tokens / max(1, n_calls),
            "completion_ratio": trace.token_usage.completion_tokens
            / max(1, trace.token_usage.total_tokens),
            "error_count": float(errors),
            "error_rate": errors / max(1, n_calls),
            "timeout_count": float(timeouts),
            "denied_count": float(denied),
            "repeated_call_count": float(repeated_count),
            "max_consecutive_repeats": float(max_consecutive),
            "distinct_input_ratio": distinct_inputs / max(1, n_calls),
            "db_query_count": float(db_count),
            "external_api_count": float(api_count),
            "file_op_count": float(file_count),
            "restricted_tool_count": float(restricted_count),
            "tool_entropy": self._entropy(names),
            "bigram_novelty": bigram_novelty,
            "calls_per_second": n_calls / duration_sec,
            "injection_lexical_score": injection_lexical_score(trace.user_prompt_preview),
        }
        return raw

    def extract(self, trace: AgentTrace) -> FeatureVector:
        raw = self.extract_raw(trace)
        return FeatureVector(trace_id=trace.trace_id, values=[raw[name] for name in FEATURE_ORDER])

    @staticmethod
    def _repeat_stats(calls: list) -> tuple[int, int]:  # type: ignore[type-arg]
        if not calls:
            return 0, 0
        keys = [(c.tool_name, c.input_hash) for c in calls]
        counts = Counter(keys)
        repeated_count = sum(v - 1 for v in counts.values() if v > 1)

        best = current = 1
        for i in range(1, len(keys)):
            current = current + 1 if keys[i] == keys[i - 1] else 1
            best = max(best, current)
        max_consecutive = best - 1  # ilk oluşumdan SONRAKİ tekrar sayısı
        return repeated_count, max(0, max_consecutive)

    @staticmethod
    def _percentile(values: list[int], pct: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        k = (len(ordered) - 1) * (pct / 100)
        f, c = math.floor(k), math.ceil(k)
        if f == c:
            return float(ordered[int(k)])
        return ordered[f] + (ordered[c] - ordered[f]) * (k - f)

    @staticmethod
    def _entropy(names: list[str]) -> float:
        if not names:
            return 0.0
        counts = Counter(names)
        total = len(names)
        return -sum((c / total) * math.log2(c / total) for c in counts.values())
