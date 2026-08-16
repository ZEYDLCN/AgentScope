"""RFC 9457 `application/problem+json` hata gövdeleri (§16.2)."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ProblemDetail(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    trace_id: str | None = None


def problem_response(status_code: int, title: str, detail: str, instance: str) -> JSONResponse:
    """RFC 9457 `problem+json` gövdesi üretir — diğer modüller (ör.
    `ratelimit.py`) tarafından da kullanılan genel yardımcı."""
    return _problem_response(status_code, title, detail, instance)


def _problem_response(status_code: int, title: str, detail: str, instance: str) -> JSONResponse:
    problem = ProblemDetail(
        type=f"https://agentguard/errors/{title.lower().replace(' ', '-')}",
        title=title,
        status=status_code,
        detail=detail,
        instance=instance,
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        detail = "; ".join(
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        )
        return _problem_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Invalid request",
            detail,
            str(request.url.path),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return _problem_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Internal server error",
            "An unexpected error occurred.",
            str(request.url.path),
        )


__all__ = ["ProblemDetail", "problem_response", "register_exception_handlers"]
