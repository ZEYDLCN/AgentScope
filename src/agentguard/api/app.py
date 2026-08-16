"""FastAPI uygulama fabrikası."""

from __future__ import annotations

from fastapi import FastAPI
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.cors import CORSMiddleware

from agentguard import __version__
from agentguard.api.deps import lifespan
from agentguard.api.errors import register_exception_handlers
from agentguard.api.ratelimit import register_rate_limiting
from agentguard.api.routers import anomalies, health, investigate, knowledge, stats, traces
from agentguard.config import get_settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="AgentGuard AI",
        description=(
            "AI agent yürütmelerinde anomali tespiti, hibrit RAG ile kök neden "
            "araştırması ve yerel LLM ile kanıta dayalı soruşturma raporları."
        ),
        version=__version__,
        lifespan=lifespan,
    )

    settings = get_settings()
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["X-API-Key", "Content-Type"],
    )

    register_rate_limiting(app)
    app.add_middleware(SlowAPIMiddleware)

    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(traces.router)
    app.include_router(investigate.router)
    app.include_router(anomalies.router)
    app.include_router(stats.router)
    app.include_router(knowledge.router)

    return app
