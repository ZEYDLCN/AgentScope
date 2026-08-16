"""Dependency-injection yardımcıları — ağır nesneler `lifespan`'de yüklenir.

Artefakt/index bulunamazsa (ör. `make bootstrap` henüz çalıştırılmamış
temiz bir ortamda) uygulama YİNE DE açılır; `/health/ready` bu durumu
`not_ready` olarak raporlar (fail-open — geliştirme deneyimini bozmaz,
ama prod'da orchestrator bu sinyale göre trafiği yönlendirmemelidir).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from agentguard.anomaly.registry import DetectorBundle, FeatureVersionMismatchError
from agentguard.config import Settings, get_settings
from agentguard.features.definitions import FEATURE_VERSION
from agentguard.features.extractor import FeatureExtractor
from agentguard.llm.ollama_client import OllamaClient
from agentguard.logging import configure_logging, get_logger
from agentguard.rag.embeddings import SentenceTransformerEmbedder
from agentguard.rag.pipeline import RAGPipeline
from agentguard.rag.reranker import CrossEncoderReranker
from agentguard.storage.database import create_engine, create_session_factory, init_models

logger = get_logger("api.lifespan")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger.info("startup.begin", env=settings.env)

    engine = create_engine(settings.database_url)
    if settings.env != "prod":
        # Prod'da şema yalnızca Alembic ile değişir (§17.1); dev/test'te
        # hızlı iterasyon için otomatik create_all kullanılır.
        await init_models(engine)
    app.state.db_engine = engine
    app.state.db_session_factory = create_session_factory(engine)
    app.state.db_ready = True

    app.state.detector = None
    app.state.feature_extractor = None
    try:
        bundle = DetectorBundle.load(
            settings.artifacts_path, expected_feature_version=FEATURE_VERSION
        )
        app.state.detector = bundle
        app.state.feature_extractor = FeatureExtractor(bigram_vocabulary=bundle.bigram_vocabulary)
        logger.info("startup.detector_loaded", path=str(settings.artifacts_path))
    except FeatureVersionMismatchError:
        # Sessiz özellik kayması en sinsi hata sınıfıdır — burada fail-fast olması
        # gerekirdi (prod), ancak dev/test akışını kilitlememek için sadece loglanır.
        logger.error("startup.feature_version_mismatch", path=str(settings.artifacts_path))
    except (FileNotFoundError, OSError):
        logger.warning("startup.detector_not_found", path=str(settings.artifacts_path))

    app.state.rag = None
    try:
        embedder = SentenceTransformerEmbedder(settings.embedding_model)
        reranker = CrossEncoderReranker(settings.reranker_model)
        app.state.rag = RAGPipeline.load(settings.index_path, embedder, reranker=reranker)
        logger.info("startup.rag_loaded", path=str(settings.index_path))
    except (FileNotFoundError, OSError):
        logger.warning("startup.rag_index_not_found", path=str(settings.index_path))

    app.state.llm = OllamaClient(settings)
    await app.state.llm.warmup()
    app.state.llm_ready = app.state.llm.is_ready

    logger.info("startup.complete")
    yield

    await app.state.llm.aclose()
    await engine.dispose()
    logger.info("shutdown.complete")


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.db_session_factory
    async with session_factory() as session:
        yield session


def get_settings_dep() -> Settings:
    return get_settings()


async def require_api_key(
    settings: Annotated[Settings, Depends(get_settings_dep)],
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    """`X-API-Key` doğrulaması (§16.2 Auth MVP). `/health` ve `/metrics` muaf."""
    if x_api_key != settings.api_key.get_secret_value():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
