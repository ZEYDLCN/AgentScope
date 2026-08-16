"""PII redaksiyonu — §21.2.

`input_preview` ve `user_prompt_preview` alanları kayıt öncesi bu
fonksiyondan geçirilir. E-posta, telefon, IBAN/kart benzeri diziler ve
JWT/API-key kalıpları maskelenir.
"""

from __future__ import annotations

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[REDACTED:EMAIL]"),
    (re.compile(r"\bTR\d{2}(?:[ ]?\d{4}){5}[ ]?\d{2}\b"), "[REDACTED:IBAN]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[REDACTED:CARD]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"), "[REDACTED:JWT]"),
    (re.compile(r"\b(?:sk|pk|api)[-_][A-Za-z0-9]{16,}\b", re.IGNORECASE), "[REDACTED:APIKEY]"),
    (re.compile(r"\+?\d[\d ()-]{7,14}\d"), "[REDACTED:PHONE]"),
]


def redact_pii(text: str | None) -> str | None:
    if text is None:
        return None
    redacted = text
    for pattern, replacement in _PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted
