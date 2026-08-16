from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentguard.schemas.trace import AgentTrace
from agentguard.services.ingestion import IngestionService, TraceConflictError
from agentguard.storage.database import create_engine, create_session_factory, init_models
from agentguard.storage.repositories import TraceRepository

FIXTURES = Path(__file__).parent.parent / "fixtures" / "traces"


def load_fixture() -> AgentTrace:
    data = json.loads((FIXTURES / "normal_trace.json").read_text())
    return AgentTrace.model_validate(data)


@pytest.fixture
async def session_factory():  # type: ignore[no-untyped-def]
    engine = create_engine("sqlite+aiosqlite:///:memory:")
    await init_models(engine)
    yield create_session_factory(engine)
    await engine.dispose()


async def test_ingest_persists_trace_and_redacts_pii(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        service = IngestionService(TraceRepository(session))
        trace = load_fixture()
        record, created = await service.ingest(trace)

        assert created is True
        assert record.trace_id == trace.trace_id
        assert "[REDACTED:EMAIL]" in record.payload["user_prompt_preview"]


async def test_ingest_is_idempotent(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        service = IngestionService(TraceRepository(session))
        trace = load_fixture()

        _, created_first = await service.ingest(trace)
        _, created_second = await service.ingest(trace)

        assert created_first is True
        assert created_second is False


async def test_ingest_conflict_on_changed_payload(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as session:
        service = IngestionService(TraceRepository(session))
        trace = load_fixture()
        await service.ingest(trace)

        mutated = trace.model_copy(update={"agent_version": "2.0.0"})
        with pytest.raises(TraceConflictError):
            await service.ingest(mutated)
