"""`/v1/anomalies/{trace_id}/investigate`, `/v1/investigations`, `/v1/jobs` — §16.1.

MVP'de kuyruk = FastAPI `BackgroundTasks` + DB'de `job` tablosu (§2.3).

Not: `from __future__ import annotations` kasıtlı olarak KULLANILMAZ — bkz.
`traces.py` başındaki not (`slowapi.limit()` + postponed evaluation
çakışması).
"""

from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from agentguard.anomaly.rules import evaluate_rules
from agentguard.api.deps import get_db_session, require_api_key
from agentguard.api.ratelimit import INVESTIGATE_RATE, limiter
from agentguard.config import get_settings
from agentguard.logging import get_logger
from agentguard.metrics import (
    investigation_fallback_total,
    llm_detector_disagreement_total,
    schema_valid_first_try_ratio,
)
from agentguard.schemas.anomaly import AnomalyResult, DetectorScore, Severity
from agentguard.schemas.investigation import Investigation
from agentguard.schemas.trace import AgentTrace
from agentguard.services.investigation import InvestigationService
from agentguard.storage.models import InvestigationRecord
from agentguard.storage.repositories import (
    DetectionRepository,
    InvestigationRepository,
    JobRepository,
    TraceRepository,
)

router = APIRouter(prefix="/v1", tags=["investigations"], dependencies=[Depends(require_api_key)])
logger = get_logger("api.investigate")


async def schedule_investigation(app: FastAPI, trace_id: str) -> None:
    """Arka plan görevi: trace + son tespiti yükler, soruşturmayı çalıştırır, kaydeder."""
    session_factory = app.state.db_session_factory
    async with session_factory() as session:
        job_repo = JobRepository(session)
        job = await job_repo.create(kind="investigate", trace_id=trace_id)
        await job_repo.mark_status(job.job_id, "running")
        try:
            await _execute_investigation(app, session, trace_id)
            await job_repo.mark_status(job.job_id, "completed")
        except Exception as exc:
            logger.error("investigation.job_failed", trace_id=trace_id, error=str(exc))
            await job_repo.mark_status(job.job_id, "failed", error=str(exc)[:1024])


async def _execute_investigation(
    app: FastAPI, session: AsyncSession, trace_id: str
) -> Investigation:
    trace_record = await TraceRepository(session).get(trace_id)
    if trace_record is None:
        raise ValueError(f"trace_id={trace_id} bulunamadı")
    trace = AgentTrace.model_validate(trace_record.payload)

    detection_record = await DetectionRepository(session).get_latest_for_trace(trace_id)
    if detection_record is None:
        raise ValueError(f"trace_id={trace_id} için tespit kaydı yok")

    extractor = app.state.feature_extractor
    if extractor is None:
        raise ValueError("feature_extractor yüklü değil (artefakt eksik)")
    raw_features = extractor.extract_raw(trace)
    rule_eval = evaluate_rules(raw_features)

    anomaly_result = AnomalyResult(
        trace_id=trace_id,
        is_anomaly=detection_record.is_anomaly,
        score=detection_record.score,
        severity=Severity(detection_record.severity),
        detector_scores=[DetectorScore.model_validate(s) for s in detection_record.detector_scores],
        triggered_rules=detection_record.triggered_rules,
        threshold=detection_record.threshold,
        detected_at=detection_record.detected_at,
    )

    llm = app.state.llm
    rag = app.state.rag
    service = InvestigationService(llm, rag=rag, model_name=get_settings().ollama_model)
    outcome = await service.investigate(trace, raw_features, anomaly_result, rule_eval)

    record = InvestigationRecord(
        trace_id=trace_id,
        anomaly_type=outcome.investigation.anomaly_type.value,
        severity=outcome.investigation.severity.value,
        confidence=outcome.investigation.confidence,
        root_cause=outcome.investigation.root_cause,
        evidence=[e.model_dump() for e in outcome.investigation.evidence],
        recommendations=[r.model_dump() for r in outcome.investigation.recommendations],
        retrieved_docs=outcome.investigation.retrieved_docs,
        model_name=outcome.investigation.model_name,
        prompt_version=outcome.investigation.prompt_version,
        generated_by=outcome.generated_by,
        latency_ms=outcome.investigation.latency_ms,
    )
    await InvestigationRepository(session).upsert(record)

    schema_valid_first_try_ratio.set(1.0 if outcome.schema_valid_first_try else 0.0)
    if outcome.detector_llm_disagreement:
        llm_detector_disagreement_total.inc()
    if outcome.generated_by == "fallback":
        investigation_fallback_total.inc()

    return outcome.investigation


@router.post("/anomalies/{trace_id}/investigate", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(INVESTIGATE_RATE)
async def trigger_investigation(
    trace_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    force: bool = False,
) -> dict[str, str]:
    existing = await InvestigationRepository(session).get_by_trace(trace_id)
    if existing is not None and not force:
        return {"trace_id": trace_id, "status": "already_completed"}

    trace_record = await TraceRepository(session).get(trace_id)
    if trace_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trace not found")

    background_tasks.add_task(schedule_investigation, request.app, trace_id)
    return {"trace_id": trace_id, "status": "queued"}


@router.get("/investigations/{trace_id}")
async def get_investigation(
    trace_id: str,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, object]:
    record = await InvestigationRepository(session).get_by_trace(trace_id)
    if record is None:
        pending_job = await JobRepository(session).get_pending_for_trace(
            trace_id, kind="investigate"
        )
        if pending_job is not None and pending_job.status in {"pending", "running"}:
            response.status_code = status.HTTP_202_ACCEPTED
            return {
                "trace_id": trace_id,
                "status": pending_job.status,
                "job_id": pending_job.job_id,
            }
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="investigation not found")
    return {
        "trace_id": record.trace_id,
        "anomaly_type": record.anomaly_type,
        "severity": record.severity,
        "confidence": record.confidence,
        "root_cause": record.root_cause,
        "evidence": record.evidence,
        "recommendations": record.recommendations,
        "retrieved_docs": record.retrieved_docs,
        "model_name": record.model_name,
        "prompt_version": record.prompt_version,
        "generated_by": record.generated_by,
        "latency_ms": record.latency_ms,
        "created_at": record.created_at.isoformat(),
    }


@router.get("/jobs/{job_id}")
async def get_job(
    job_id: str, session: Annotated[AsyncSession, Depends(get_db_session)]
) -> dict[str, object]:
    job = await JobRepository(session).get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return {
        "job_id": job.job_id,
        "kind": job.kind,
        "trace_id": job.trace_id,
        "status": job.status,
        "attempts": job.attempts,
        "error": job.error,
        "updated_at": job.updated_at.isoformat(),
    }
