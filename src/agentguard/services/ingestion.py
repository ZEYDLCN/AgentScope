"""Trace alım servisi — §6.3.

Kurallar:
- Idempotency: aynı `trace_id` tekrar gelirse mevcut kayıt döner (yeniden
  işlem başlatılmaz). İçerik farklıysa `TraceConflictError`.
- Sanitizasyon: `input_preview` / `user_prompt_preview` PII redaksiyonundan
  geçer.
- Saat çarpıklığı: `started_at` sunucu saatinden > 24 saat ileriyse reddedilir.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from agentguard.common.pii import redact_pii
from agentguard.schemas.trace import AgentTrace
from agentguard.storage.models import TraceRecord
from agentguard.storage.repositories import TraceRepository

MAX_CLOCK_SKEW = timedelta(hours=24)


class ClockSkewError(ValueError):
    """`started_at` sunucu saatinden çok ileride."""


class TraceConflictError(ValueError):
    """Aynı `trace_id`, farklı içerikle tekrar gönderildi."""


def sanitize_trace(trace: AgentTrace) -> AgentTrace:
    """PII redaksiyonu uygulanmış bir kopya döner (girdi mutasyona uğramaz)."""
    sanitized = trace.model_copy(deep=True)
    sanitized.user_prompt_preview = redact_pii(sanitized.user_prompt_preview)
    for call in sanitized.tool_calls:
        call.input_preview = redact_pii(call.input_preview)
    return sanitized


def check_clock_skew(trace: AgentTrace, *, now: datetime | None = None) -> None:
    reference = now or datetime.now(UTC)
    started_at = trace.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    if started_at - reference > MAX_CLOCK_SKEW:
        raise ClockSkewError(
            f"started_at ({started_at.isoformat()}) sunucu saatinden "
            f"{MAX_CLOCK_SKEW} fazla ileride"
        )


class IngestionService:
    def __init__(self, repository: TraceRepository) -> None:
        self._repository = repository

    async def ingest(self, trace: AgentTrace) -> tuple[TraceRecord, bool]:
        """Trace'i doğrular, sanitize eder ve kalıcı hale getirir.

        Döner: `(record, created)` — `created=False` ise idempotent tekrar.
        """
        check_clock_skew(trace)
        sanitized = sanitize_trace(trace)

        existing = await self._repository.get(trace.trace_id)
        if existing is not None:
            if existing.payload != sanitized.model_dump(mode="json"):
                raise TraceConflictError(f"trace_id={trace.trace_id} farklı içerikle zaten kayıtlı")
            return existing, False

        record = TraceRecord(
            trace_id=sanitized.trace_id,
            agent_id=sanitized.agent_id,
            agent_version=sanitized.agent_version,
            started_at=sanitized.started_at,
            ended_at=sanitized.ended_at,
            payload=sanitized.model_dump(mode="json"),
        )
        created = await self._repository.add(record)
        return created, True
