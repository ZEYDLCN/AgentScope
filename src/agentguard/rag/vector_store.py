"""FAISS vektör deposu — §11.4, §12.2.

`IndexFlatIP`: normalize edilmiş vektörlerde iç çarpım = kosinüs benzerliği.
< 100k chunk'ta exact search yeterince hızlı ve `IVF`/`HNSW`'den daha
doğru (ADR-003).
"""

from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np
from numpy.typing import NDArray


class FaissVectorStore:
    def __init__(self, dimension: int) -> None:
        self._dimension = dimension
        self._index = faiss.IndexFlatIP(dimension)
        self._chunk_ids: list[str] = []

    def add(self, chunk_ids: list[str], vectors: NDArray[np.float32]) -> None:
        if vectors.shape[0] != len(chunk_ids):
            raise ValueError("chunk_ids ve vectors aynı sayıda satır içermeli")
        if vectors.shape[1] != self._dimension:
            raise ValueError(f"beklenen boyut {self._dimension}, alınan {vectors.shape[1]}")
        self._index.add(vectors.astype(np.float32))
        self._chunk_ids.extend(chunk_ids)

    def search(self, query_vector: NDArray[np.float32], top_k: int) -> list[tuple[str, float]]:
        if self._index.ntotal == 0:
            return []
        query = query_vector.reshape(1, -1).astype(np.float32)
        scores, indices = self._index.search(query, min(top_k, self._index.ntotal))
        results: list[tuple[str, float]] = []
        for idx, score in zip(indices[0], scores[0], strict=True):
            if idx == -1:
                continue
            results.append((self._chunk_ids[idx], float(score)))
        return results

    @property
    def size(self) -> int:
        return int(self._index.ntotal)

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(directory / "index.faiss"))
        (directory / "chunk_ids.json").write_text(json.dumps(self._chunk_ids))

    @classmethod
    def load(cls, directory: Path) -> FaissVectorStore:
        index = faiss.read_index(str(directory / "index.faiss"))
        chunk_ids = json.loads((directory / "chunk_ids.json").read_text())
        instance = cls.__new__(cls)
        instance._dimension = index.d
        instance._index = index
        instance._chunk_ids = chunk_ids
        return instance
