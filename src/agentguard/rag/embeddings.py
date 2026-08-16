"""Embedding modeli sarmalayıcısı — §3, §12.2.

`sentence-transformers` üzerinden `BAAI/bge-m3` (veya küçük donanımda
`bge-small-en-v1.5`) yükler. Model ağırlıkları ilk kullanımda Hugging
Face Hub'dan indirilir ve `HF_HOME` altında önbelleğe alınır — bu nedenle
model, süreç ömrü boyunca **tembel (lazy)** yüklenir; import anında ağ
erişimi gerekmez.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

QUERY_PREFIX = "Represent this query for retrieval: "
EMBED_BATCH_SIZE = 32


class SentenceTransformerEmbedder:
    """`agentguard.rag.base.Embedder` Protocol'ünü karşılayan gerçek implementasyon."""

    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        self._model_name = model_name
        self._model: Any | None = None  # tembel yüklenir; gerçek tipi sentence_transformers'a özel

    @property
    def dimension(self) -> int:
        model = self._ensure_loaded()
        dim: int = model.get_sentence_embedding_dimension()
        return dim

    def _ensure_loaded(self) -> Any:  # noqa: ANN401 — sentence_transformers stub'ları eksik
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed(self, texts: list[str]) -> NDArray[np.float32]:
        model = self._ensure_loaded()
        embeddings: NDArray[np.float32] = model.encode(
            texts,
            batch_size=EMBED_BATCH_SIZE,
            normalize_embeddings=True,
            convert_to_numpy=True,
        ).astype(np.float32)
        return embeddings

    def embed_query(self, query: str) -> NDArray[np.float32]:
        result: NDArray[np.float32] = self.embed([QUERY_PREFIX + query])[0]
        return result
