"""Retriever / Reranker / Embedder Protocol'leri — §1.5, §12, §13.

Testlerde fake, prodda gerçek implementasyon. Bu dosya `agentguard.schemas`
dışında hiçbir iç modüle bağımlı değildir.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from agentguard.schemas.knowledge import Chunk


class Embedder(Protocol):
    """Metinleri yoğun vektörlere dönüştürür (§12.2)."""

    @property
    def dimension(self) -> int: ...

    def embed(self, texts: list[str]) -> NDArray[np.float32]: ...


class Retriever(Protocol):
    """Bir sorgu için `top_k` chunk_id + skor döner (yüksek = daha alakalı)."""

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]: ...


class Reranker(Protocol):
    """(sorgu, chunk) çiftlerini yeniden puanlar (§13)."""

    def rerank(self, query: str, chunks: list[Chunk]) -> list[tuple[Chunk, float]]: ...
