"""Repository katmanı — servislerin ORM'e doğrudan bağımlı olmasını önler."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agentguard.storage.models import DetectionRecord, InvestigationRecord, JobRecord, TraceRecord


class TraceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, trace_id: str) -> TraceRecord | None:
        return await self._session.get(TraceRecord, trace_id)

    async def add(self, record: TraceRecord) -> TraceRecord:
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def exists(self, trace_id: str) -> bool:
        stmt = select(TraceRecord.trace_id).where(TraceRecord.trace_id == trace_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def count_total(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(TraceRecord))
        return int(result.scalar_one())


class DetectionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: DetectionRecord) -> DetectionRecord:
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def get_latest_for_trace(self, trace_id: str) -> DetectionRecord | None:
        stmt = (
            select(DetectionRecord)
            .where(DetectionRecord.trace_id == trace_id)
            .order_by(DetectionRecord.detected_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_anomalies(
        self,
        *,
        severity: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        cursor: datetime | None = None,
        limit: int = 50,
    ) -> tuple[list[DetectionRecord], datetime | None]:
        """Cursor tabanlı sayfalama (§16.2) — `cursor`, bir önceki sayfanın
        son `detected_at` değeridir; sonraki sayfa bundan daha eski kayıtları döner."""
        stmt = select(DetectionRecord).where(DetectionRecord.is_anomaly.is_(True))
        if severity is not None:
            stmt = stmt.where(DetectionRecord.severity == severity)
        if since is not None:
            stmt = stmt.where(DetectionRecord.detected_at >= since)
        if until is not None:
            stmt = stmt.where(DetectionRecord.detected_at <= until)
        if cursor is not None:
            stmt = stmt.where(DetectionRecord.detected_at < cursor)
        stmt = stmt.order_by(DetectionRecord.detected_at.desc()).limit(limit + 1)

        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = rows[-1].detected_at if has_more and rows else None
        return rows, next_cursor

    async def count_total(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(DetectionRecord))
        return int(result.scalar_one())

    async def count_anomalies(self) -> int:
        stmt = (
            select(func.count())
            .select_from(DetectionRecord)
            .where(DetectionRecord.is_anomaly.is_(True))
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def count_by_severity(self) -> dict[str, int]:
        stmt = (
            select(DetectionRecord.severity, func.count())
            .where(DetectionRecord.is_anomaly.is_(True))
            .group_by(DetectionRecord.severity)
        )
        result = await self._session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}


class InvestigationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_trace(self, trace_id: str) -> InvestigationRecord | None:
        stmt = select(InvestigationRecord).where(InvestigationRecord.trace_id == trace_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, record: InvestigationRecord) -> InvestigationRecord:
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def upsert(self, record: InvestigationRecord) -> InvestigationRecord:
        """`add()`'in aksine, aynı `trace_id` için zaten bir kayıt varsa onu
        günceller — düz `INSERT` `trace_id` UNIQUE kısıtına çarpıp
        `IntegrityError` fırlatır (bkz. `models.InvestigationRecord.trace_id`).
        `POST /v1/anomalies/{id}/investigate?force=true` yeniden soruşturma
        akışı bunu kullanmalı; ilk (idempotent) soruşturma `add()` ile de
        çalışır ama tutarlılık için burası her zaman güvenli yoldur."""
        existing = await self.get_by_trace(record.trace_id)
        if existing is None:
            return await self.add(record)

        for field in (
            "anomaly_type",
            "severity",
            "confidence",
            "root_cause",
            "evidence",
            "recommendations",
            "retrieved_docs",
            "model_name",
            "prompt_version",
            "generated_by",
            "latency_ms",
        ):
            setattr(existing, field, getattr(record, field))
        # `record.created_at` bu noktada henüz `None` olabilir (transient nesne,
        # sütun `server_default=func.now()` ile yalnızca INSERT'te doldurulur) —
        # kopyalamak yerine "yeniden üretildi" zamanını burada açıkça set ederiz.
        existing.created_at = datetime.now(UTC)
        await self._session.commit()
        await self._session.refresh(existing)
        return existing

    async def count_by_generated_by(self) -> dict[str, int]:
        stmt = select(InvestigationRecord.generated_by, func.count()).group_by(
            InvestigationRecord.generated_by
        )
        result = await self._session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, kind: str, trace_id: str) -> JobRecord:
        record = JobRecord(job_id=str(uuid.uuid4()), kind=kind, trace_id=trace_id, status="pending")
        self._session.add(record)
        await self._session.commit()
        await self._session.refresh(record)
        return record

    async def get(self, job_id: str) -> JobRecord | None:
        return await self._session.get(JobRecord, job_id)

    async def get_pending_for_trace(self, trace_id: str, *, kind: str) -> JobRecord | None:
        stmt = (
            select(JobRecord)
            .where(JobRecord.trace_id == trace_id, JobRecord.kind == kind)
            .order_by(JobRecord.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_status(self, job_id: str, status: str, *, error: str | None = None) -> None:
        job = await self._session.get(JobRecord, job_id)
        if job is None:
            return
        job.status = status
        job.attempts += 1
        job.error = error
        job.updated_at = datetime.now(UTC)
        await self._session.commit()
