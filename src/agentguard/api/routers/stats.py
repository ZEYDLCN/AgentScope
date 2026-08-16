"""`/v1/stats` — dashboard özet sayaçları (§16.1, §18)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agentguard.api.deps import get_db_session, require_api_key
from agentguard.storage.repositories import (
    DetectionRepository,
    InvestigationRepository,
    TraceRepository,
)

router = APIRouter(prefix="/v1", tags=["stats"], dependencies=[Depends(require_api_key)])


@router.get("/stats")
async def get_stats(session: Annotated[AsyncSession, Depends(get_db_session)]) -> dict[str, object]:
    detection_repo = DetectionRepository(session)
    total_traces = await TraceRepository(session).count_total()
    total_anomalies = await detection_repo.count_anomalies()
    total_detections = await detection_repo.count_total()
    by_severity = await detection_repo.count_by_severity()
    by_generated_by = await InvestigationRepository(session).count_by_generated_by()

    return {
        "total_traces": total_traces,
        "total_detections": total_detections,
        "total_anomalies": total_anomalies,
        "anomaly_rate": (total_anomalies / total_detections) if total_detections else 0.0,
        "anomalies_by_severity": by_severity,
        "investigations_by_generated_by": by_generated_by,
    }
