"""`/v1/anomalies` — filtrelenebilir anomali listesi (§16.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from agentguard.api.deps import get_db_session, require_api_key
from agentguard.storage.repositories import DetectionRepository

router = APIRouter(prefix="/v1", tags=["anomalies"], dependencies=[Depends(require_api_key)])

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


@router.get("/anomalies")
async def list_anomalies(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    severity: str | None = None,
    date_from: datetime | None = Query(default=None, alias="from"),
    date_to: datetime | None = Query(default=None, alias="to"),
    cursor: datetime | None = None,
    limit: int = Query(default=DEFAULT_LIMIT, le=MAX_LIMIT, ge=1),
) -> dict[str, object]:
    records, next_cursor = await DetectionRepository(session).list_anomalies(
        severity=severity, since=date_from, until=date_to, cursor=cursor, limit=limit
    )
    return {
        "items": [
            {
                "trace_id": r.trace_id,
                "is_anomaly": r.is_anomaly,
                "score": r.score,
                "severity": r.severity,
                "threshold": r.threshold,
                "triggered_rules": r.triggered_rules,
                "detected_at": r.detected_at.isoformat(),
            }
            for r in records
        ],
        "next_cursor": next_cursor.isoformat() if next_cursor else None,
    }
