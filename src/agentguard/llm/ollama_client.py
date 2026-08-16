"""Ollama istemcisi — §14.1.

- `format=json_schema`, `temperature=0`, `seed=42` (determinizm)
- Timeout: connect 5s, read 120s
- Retry: 2 deneme, exponential backoff (1s, 4s), yalnızca 5xx/timeout'ta
- Circuit breaker: 5 ardışık hata → 60s açık
- Warm-up: açılışta 1 token'lık ısınma isteği
"""

from __future__ import annotations

import asyncio
import time

import httpx

from agentguard.config import Settings
from agentguard.logging import get_logger

logger = get_logger("llm.ollama")

RETRY_DELAYS_S = (1.0, 4.0)
CIRCUIT_BREAKER_THRESHOLD = 5
CIRCUIT_BREAKER_COOLDOWN_S = 60.0
WARMUP_TIMEOUT_S = 30.0


class LLMUnavailableError(RuntimeError):
    """Circuit breaker açık ya da Ollama erişilemez durumda."""


class OllamaModelMissingError(RuntimeError):
    """`ollama pull <model>` çalıştırılmamış — model `/api/tags`'te yok."""


class OllamaClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=httpx.Timeout(
                settings.llm_timeout_read_s,
                connect=settings.llm_timeout_connect_s,
                read=settings.llm_timeout_read_s,
            ),
        )
        self._consecutive_failures = 0
        self._circuit_open_until: float = 0.0
        self.is_ready = False

    def _circuit_is_open(self) -> bool:
        return time.monotonic() < self._circuit_open_until

    def _record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
            self._circuit_open_until = time.monotonic() + CIRCUIT_BREAKER_COOLDOWN_S
            logger.warning("circuit_breaker.opened", cooldown_s=CIRCUIT_BREAKER_COOLDOWN_S)

    def _record_success(self) -> None:
        self._consecutive_failures = 0

    async def generate(
        self, *, system_prompt: str, user_prompt: str, json_schema: dict[str, object]
    ) -> str:
        if self._circuit_is_open():
            raise LLMUnavailableError("circuit breaker açık — Ollama geçici olarak devre dışı")

        payload = {
            "model": self._settings.ollama_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": json_schema,
            "options": {
                "temperature": 0.0,
                "top_p": 1.0,
                "seed": 42,
                "num_ctx": 8192,
                "num_predict": 1024,
                "repeat_penalty": 1.05,
            },
        }

        last_exc: Exception | None = None
        for attempt, delay in enumerate((0.0, *RETRY_DELAYS_S)):
            if delay:
                await asyncio.sleep(delay)
            try:
                response = await self._client.post("/api/chat", json=payload)
                if response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"Ollama {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                self._record_success()
                data = response.json()
                content: str = data["message"]["content"]
                return content
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_exc = exc
                logger.warning("llm.request_failed", attempt=attempt, error=str(exc))

        self._record_failure()
        raise LLMUnavailableError(
            f"Ollama isteği {len(RETRY_DELAYS_S) + 1} denemede başarısız"
        ) from last_exc

    async def warmup(self) -> None:
        try:
            tags_response = await self._client.get("/api/tags", timeout=WARMUP_TIMEOUT_S)
            tags_response.raise_for_status()
            models = [m["name"] for m in tags_response.json().get("models", [])]
            if self._settings.ollama_model not in models:
                raise OllamaModelMissingError(
                    f"model {self._settings.ollama_model!r} yüklü değil — "
                    f"'ollama pull {self._settings.ollama_model}' çalıştırın"
                )
            await self._client.post(
                "/api/chat",
                json={
                    "model": self._settings.ollama_model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "stream": False,
                    "options": {"num_predict": 1},
                },
                timeout=WARMUP_TIMEOUT_S,
            )
            self.is_ready = True
            logger.info("llm.warmup.complete")
        except OllamaModelMissingError:
            raise
        except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
            logger.warning("llm.warmup.failed", error=str(exc))

    async def aclose(self) -> None:
        await self._client.aclose()
