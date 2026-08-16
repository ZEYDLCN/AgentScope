from __future__ import annotations

import httpx
import pytest

from agentguard.config import Settings
from agentguard.llm.ollama_client import (
    CIRCUIT_BREAKER_THRESHOLD,
    LLMUnavailableError,
    OllamaClient,
    OllamaModelMissingError,
)

pytestmark = pytest.mark.slow  # httpx.AsyncClient event loop kurulumu -> asyncio testleri


@pytest.fixture(autouse=True)
def _fast_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retry backoff'unu (1s, 4s) testlerde beklememek için no-op'a çevirir."""

    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("agentguard.llm.ollama_client.asyncio.sleep", _no_sleep)


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        api_key="test",
        ollama_model="qwen2.5:7b-instruct-q4_K_M",
        llm_timeout_connect_s=1,
        llm_timeout_read_s=5,
    )


def _client_with_transport(transport: httpx.MockTransport) -> OllamaClient:
    client = OllamaClient(_settings())
    client._client = httpx.AsyncClient(base_url="http://fake-ollama", transport=transport)
    return client


async def test_generate_success_returns_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": '{"ok": true}'}})

    client = _client_with_transport(httpx.MockTransport(handler))
    result = await client.generate(system_prompt="sys", user_prompt="usr", json_schema={})
    assert result == '{"ok": true}'
    await client.aclose()


async def test_generate_retries_on_5xx_then_succeeds() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(503, json={"error": "unavailable"})
        return httpx.Response(200, json={"message": {"content": "ok"}})

    client = _client_with_transport(httpx.MockTransport(handler))
    result = await client.generate(system_prompt="sys", user_prompt="usr", json_schema={})
    assert result == "ok"
    assert calls["n"] == 2
    await client.aclose()


async def test_generate_raises_after_exhausting_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "down"})

    client = _client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(LLMUnavailableError):
        await client.generate(system_prompt="sys", user_prompt="usr", json_schema={})
    await client.aclose()


async def test_circuit_breaker_opens_after_threshold_failures() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "down"})

    client = _client_with_transport(httpx.MockTransport(handler))

    for _ in range(CIRCUIT_BREAKER_THRESHOLD):
        with pytest.raises(LLMUnavailableError):
            await client.generate(system_prompt="sys", user_prompt="usr", json_schema={})

    # Devre açık olmalı; artık HTTP isteği bile yapılmadan hemen hata vermeli
    with pytest.raises(LLMUnavailableError, match="circuit breaker"):
        await client.generate(system_prompt="sys", user_prompt="usr", json_schema={})
    await client.aclose()


async def test_warmup_sets_is_ready_when_model_present() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b-instruct-q4_K_M"}]})
        return httpx.Response(200, json={"message": {"content": "pong"}})

    client = _client_with_transport(httpx.MockTransport(handler))
    await client.warmup()
    assert client.is_ready is True
    await client.aclose()


async def test_warmup_raises_when_model_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "some-other-model"}]})

    client = _client_with_transport(httpx.MockTransport(handler))
    with pytest.raises(OllamaModelMissingError):
        await client.warmup()
    assert client.is_ready is False
    await client.aclose()


async def test_warmup_does_not_raise_on_connection_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = _client_with_transport(httpx.MockTransport(handler))
    await client.warmup()  # exception fırlatmamalı, yalnızca loglamalı
    assert client.is_ready is False
    await client.aclose()
