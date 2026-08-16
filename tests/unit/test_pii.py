from __future__ import annotations

from agentguard.common.pii import redact_pii


def test_redacts_email() -> None:
    assert redact_pii("iletişim: test@example.com lütfen") == "iletişim: [REDACTED:EMAIL] lütfen"


def test_redacts_iban() -> None:
    text = "IBAN: TR33 0006 1005 1978 6457 8413 26"
    assert "[REDACTED:IBAN]" in redact_pii(text)  # type: ignore[operator]


def test_redacts_jwt() -> None:
    sample_jwt = (  # test amaçlı örnek JWT, gerçek bir sır değil
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
        "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    )
    assert redact_pii(f"token={sample_jwt}") == "token=[REDACTED:JWT]"


def test_none_passthrough() -> None:
    assert redact_pii(None) is None


def test_leaves_normal_text_untouched() -> None:
    text = "SELECT * FROM orders WHERE status='pending'"
    assert redact_pii(text) == text
