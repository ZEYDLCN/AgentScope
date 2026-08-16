from __future__ import annotations

from agentguard.logging import bind_request_id, bind_trace_id, configure_logging, get_logger


def test_configure_logging_and_get_logger_smoke() -> None:
    configure_logging("INFO")
    logger = get_logger("test.component")
    bind_trace_id("trace-123")
    bind_request_id("req-456")
    # Ham log çıktısı stdout'a yazılır; burada yalnızca çağrının
    # exception fırlatmadığını doğruluyoruz.
    logger.info("smoke.event", extra_field=1)
