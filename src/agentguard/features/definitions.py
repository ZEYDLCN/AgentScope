"""Özellik seti tanımı — §7.1.

`FEATURE_ORDER` tek doğruluk kaynağıdır. Sıra **asla** değişmez; yeni
özellik yalnızca sona eklenir ve `FEATURE_VERSION` artırılır.
"""

from __future__ import annotations

FEATURE_VERSION = "v1"

# (özellik adı, dönüşüm) — dönüşüm "log1p" | "raw"
FEATURE_SPECS: list[tuple[str, str]] = [
    ("tool_call_count", "log1p"),
    ("unique_tool_count", "raw"),
    ("tool_diversity_ratio", "raw"),
    ("duration_sec", "log1p"),
    ("mean_tool_duration_ms", "log1p"),
    ("p95_tool_duration_ms", "log1p"),
    ("total_tokens", "log1p"),
    ("tokens_per_call", "log1p"),
    ("completion_ratio", "raw"),
    ("error_count", "log1p"),
    ("error_rate", "raw"),
    ("timeout_count", "log1p"),
    ("denied_count", "raw"),
    ("repeated_call_count", "log1p"),
    ("max_consecutive_repeats", "raw"),
    ("distinct_input_ratio", "raw"),
    ("db_query_count", "log1p"),
    ("external_api_count", "log1p"),
    ("file_op_count", "log1p"),
    ("restricted_tool_count", "raw"),
    ("tool_entropy", "raw"),
    ("bigram_novelty", "raw"),
    ("calls_per_second", "log1p"),
    ("injection_lexical_score", "raw"),
]

FEATURE_ORDER: list[str] = [name for name, _ in FEATURE_SPECS]
FEATURE_INDEX: dict[str, int] = {name: i for i, name in enumerate(FEATURE_ORDER)}
LOG1P_FEATURES: frozenset[str] = frozenset(name for name, t in FEATURE_SPECS if t == "log1p")

# Politika listesindeki kısıtlı araçlar (§7.1 #20) — knowledge/policies/tool_usage_policy.md
# ile hizalı tutulur (M4).
RESTRICTED_TOOLS: frozenset[str] = frozenset({"db.write", "db.migrate", "file.write"})

DB_PREFIX = "db."
API_PREFIXES = ("api.", "http.")
FILE_PREFIX = "file."

INJECTION_LEXICAL_PATTERNS: tuple[str, ...] = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "disregard previous instructions",
    "system override",
    "you are now",
    "reveal the",
    "reveal your",
    "admin password",
    "önceki tüm talimatları yok say",
    "önceki talimatları yok say",
    "sistem geçersiz kıl",
    "gizli anahtar",
    "tüm veritabanını dök",
    "<<<evidence_end>>>",
    "<<<evidence_start>>>",
)
