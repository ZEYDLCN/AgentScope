"""Sağlık kontrolleri + Prometheus metrikleri (§20.2, §20.3).

`/health/live`  — süreç ayakta mı.
`/health/ready` — artefakt + index + Ollama + DB hazır mı.
`/metrics`      — Prometheus scrape endpoint'i (§16.2: auth muaf).
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(request: Request, response: Response) -> dict[str, object]:
    """M0'da yalnızca iskelet döner; M2+'de gerçek bağımlılık kontrolleri eklenir."""
    checks: dict[str, bool] = {
        "detector_loaded": getattr(request.app.state, "detector", None) is not None,
        "rag_loaded": getattr(request.app.state, "rag", None) is not None,
        "llm_reachable": getattr(request.app.state, "llm_ready", False),
        "db_reachable": getattr(request.app.state, "db_ready", False),
    }
    ready = all(checks.values())
    response.status_code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "ok" if ready else "not_ready", "checks": checks}


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
