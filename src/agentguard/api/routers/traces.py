"""`/v1/traces` — trace alım uç noktaları (§6, §16.1).

Senkron yol: ingest → idempotency → persist → (dedektör yüklüyse) tespit.
`status=ANOMALY` ise soruşturma arka planda tetiklenir (§2.2, §2.3).

Not: `from __future__ import annotations` kasıtlı olarak KULLANILMAZ —
`slowapi`'nin `@limiter.limit()` dekoratörü sarmalanan fonksiyonun
`__globals__`'ını değil kendi modülünün globals'ını taşır; postponed
evaluation açıkken FastAPI, `Request`/`BackgroundTasks` gibi tipleri o
yanlış namespace'te arayıp `PydanticUndefinedAnnotation` ile patlar (§21.3
rate limit'in şart koştuğu bilinen bir slowapi+FastAPI etkileşimi).
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from agentguard.api.deps import get_db_session, require_api_key
from agentguard.api.ratelimit import INGEST_RATE, limiter
from agentguard.metrics import anomalies_detected_total, traces_ingested_total
from agentguard.schemas.anomaly import AnomalyResult
from agentguard.schemas.trace import AgentTrace
from agentguard.services.detection import DetectionService
from agentguard.services.ingestion import (
    ClockSkewError,
    IngestionService,
    TraceConflictError,
)
from agentguard.storage.models import DetectionRecord
from agentguard.storage.repositories import DetectionRepository, TraceRepository

router = APIRouter(prefix="/v1", tags=["traces"], dependencies=[Depends(require_api_key)])

MAX_TOOL_CALLS = 500
MAX_BATCH_SIZE = 100


class TraceAccepted(BaseModel):
    trace_id: str
    status: str  # "received" | "duplicate"
    detection: AnomalyResult | None = None


class BatchItemResult(BaseModel):
    trace_id: str
    status: str  # "received" | "duplicate" | "error"
    detail: str | None = None


class BatchTracesRequest(BaseModel):
    traces: list[AgentTrace] = Field(max_length=MAX_BATCH_SIZE)


async def _run_detection(
    request: Request, trace: AgentTrace, session: AsyncSession
) -> AnomalyResult | None:
    detector = getattr(request.app.state, "detector", None)
    extractor = getattr(request.app.state, "feature_extractor", None)
    if detector is None or extractor is None:
        return None

    outcome = DetectionService(detector, extractor).detect(trace)
    record = DetectionRecord(
        trace_id=trace.trace_id,
        is_anomaly=outcome.result.is_anomaly,
        score=outcome.result.score,
        severity=outcome.result.severity.value,
        threshold=outcome.result.threshold,
        detector_scores=[s.model_dump() for s in outcome.result.detector_scores],
        triggered_rules=outcome.result.triggered_rules,
        model_version=outcome.result.detector_scores[0].model_version
        if outcome.result.detector_scores
        else "unknown",
        detected_at=outcome.result.detected_at,
    )
    await DetectionRepository(session).add(record)

    anomalies_detected_total.labels(
        severity=outcome.result.severity.value,
        type=",".join(outcome.result.triggered_rules) or "none",
    ).inc()

    return outcome.result


@router.post(
    "/traces",
    status_code=status.HTTP_201_CREATED,
    response_model=TraceAccepted,
)
@limiter.limit(INGEST_RATE)
async def ingest_trace(
    trace: AgentTrace,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TraceAccepted:
    if len(trace.tool_calls) > MAX_TOOL_CALLS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"tool_calls > {MAX_TOOL_CALLS}",
        )

    service = IngestionService(TraceRepository(session))
    try:
        _, created = await service.ingest(trace)
    except ClockSkewError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except TraceConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    if not created:
        response.status_code = status.HTTP_200_OK
        return TraceAccepted(trace_id=trace.trace_id, status="duplicate")

    traces_ingested_total.labels(agent_id=trace.agent_id).inc()
    detection = await _run_detection(request, trace, session)

    if detection is not None and detection.is_anomaly:
        from agentguard.api.routers.investigate import schedule_investigation

        background_tasks.add_task(schedule_investigation, request.app, trace.trace_id)

    return TraceAccepted(trace_id=trace.trace_id, status="received", detection=detection)


@router.post(
    "/traces:batch",
    status_code=status.HTTP_207_MULTI_STATUS,
    response_model=list[BatchItemResult],
)
async def ingest_traces_batch(
    batch: BatchTracesRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[BatchItemResult]:
    service = IngestionService(TraceRepository(session))
    results: list[BatchItemResult] = []
    for trace in batch.traces:
        try:
            _, created = await service.ingest(trace)
        except (ClockSkewError, TraceConflictError) as exc:
            results.append(
                BatchItemResult(trace_id=trace.trace_id, status="error", detail=str(exc))
            )
            continue
        results.append(
            BatchItemResult(trace_id=trace.trace_id, status="received" if created else "duplicate")
        )
    return results


@router.get("/traces/{trace_id}")
async def get_trace(
    trace_id: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, object]:
    record = await TraceRepository(session).get(trace_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trace not found")
    return {
        "trace_id": record.trace_id,
        "agent_id": record.agent_id,
        "received_at": record.received_at.isoformat(),
        "payload": record.payload,
    }
