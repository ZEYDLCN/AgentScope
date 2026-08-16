"""Cross-encoder reranker — §13.

`BAAI/bge-reranker-v2-m3` (küçük donanımda `bge-reranker-base`).
Model süreç ömrü boyunca bir kez yüklenir; skorlar sigmoid ile [0,1]'e
normalize edilir.
"""

from __future__ import annotations

import math
from typing import Any

from agentguard.schemas.knowledge import Chunk

MAX_SEQ_LENGTH = 512
BATCH_SIZE = 8


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class CrossEncoderReranker:
    """`agentguard.rag.base.Reranker` Protocol'ünü karşılayan gerçek implementasyon."""

    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3") -> None:
        self._model_name = model_name
        self._model: Any | None = None  # tembel yüklenir; FlagEmbedding stub'ları eksik

    def _ensure_loaded(self) -> Any:  # noqa: ANN401 — FlagEmbedding stub'ları eksik
        if self._model is None:
            from FlagEmbedding import FlagReranker

            self._model = FlagReranker(self._model_name, use_fp16=False)
        return self._model

    def rerank(self, query: str, chunks: list[Chunk]) -> list[tuple[Chunk, float]]:
        if not chunks:
            return []
        model = self._ensure_loaded()
        pairs = [[query, c.text[: MAX_SEQ_LENGTH * 4]] for c in chunks]  # kaba karakter sınırı
        raw_scores = model.compute_score(pairs, batch_size=BATCH_SIZE, max_length=MAX_SEQ_LENGTH)
        if isinstance(raw_scores, float):
            raw_scores = [raw_scores]
        scored = [(c, _sigmoid(float(s))) for c, s in zip(chunks, raw_scores, strict=True)]
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored
