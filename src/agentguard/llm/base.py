"""LLMClient Protocol — §1.5, §14.

Testlerde `FakeLLMClient` (sabit JSON döner), prodda `OllamaClient`.
"""

from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    async def generate(
        self, *, system_prompt: str, user_prompt: str, json_schema: dict[str, object]
    ) -> str:
        """Ham LLM çıktısını (JSON metni) döner. Ayrıştırma/doğrulama `guards.py`'dedir."""
        ...

    async def warmup(self) -> None: ...

    async def aclose(self) -> None: ...
