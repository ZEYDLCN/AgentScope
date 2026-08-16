"""IP başına hız sınırlama — `slowapi` (§16.2, §21.3).

`POST /v1/traces` (ingest, 60 req/dk) ve `POST /v1/anomalies/{id}/investigate`
(LLM soruşturma tetikleme, 10 req/dk — daha pahalı bir işlem, Ollama'ya iş
yükler) için farklı limitler tanımlanır. `/health` ve `/metrics` limite
tabi değildir.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from agentguard.api.errors import problem_response

limiter = Limiter(key_func=get_remote_address)

INGEST_RATE = "60/minute"
INVESTIGATE_RATE = "10/minute"


def register_rate_limiting(app: FastAPI) -> None:
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_problem_handler(request: Request, exc: RateLimitExceeded) -> object:
        # slowapi'nin varsayılan handler'ı düz JSON döner (§16.2 problem+json
        # sözleşmesini bozar); RFC 9457 gövdesiyle sarmalanır.
        return problem_response(
            429,
            "Rate limit exceeded",
            f"Rate limit exceeded: {exc.detail}",
            str(request.url.path),
        )


__all__ = ["INGEST_RATE", "INVESTIGATE_RATE", "limiter", "register_rate_limiting"]
