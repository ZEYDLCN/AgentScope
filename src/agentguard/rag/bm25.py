"""BM25 (keyword) retrieval — §12.2.

`k1=1.5`, `b=0.75`; lowercase + noktalama temizliği + basit stopword
listesi. `rank_bm25.BM25Okapi` üzerine ince bir sarmalayıcı.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

K1 = 1.5
B = 0.75

_TOKEN_RE = re.compile(r"[a-zA-ZçÇğĞıİöÖşŞüÜ0-9]+")

# Türkçe + İngilizce ortak stopword'ler (domain-bağımsız, kısa liste)
STOPWORDS: frozenset[str] = frozenset(
    {
        "ve",
        "veya",
        "ile",
        "bir",
        "bu",
        "şu",
        "o",
        "da",
        "de",
        "ki",
        "için",
        "gibi",
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "to",
        "in",
        "is",
        "are",
        "be",
        "on",
        "at",
        "as",
    }
)


def tokenize(text: str) -> list[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in STOPWORDS]


class BM25Retriever:
    def __init__(self, chunk_ids: list[str], texts: list[str]) -> None:
        if len(chunk_ids) != len(texts):
            raise ValueError("chunk_ids ve texts aynı uzunlukta olmalı")
        self._chunk_ids = chunk_ids
        self._corpus_tokens = [tokenize(t) for t in texts]
        self._bm25 = BM25Okapi(self._corpus_tokens, k1=K1, b=B)

    def search(self, query: str, top_k: int) -> list[tuple[str, float]]:
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(zip(self._chunk_ids, scores, strict=True), key=lambda t: t[1], reverse=True)
        return [(cid, float(score)) for cid, score in ranked[:top_k] if score > 0]

    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps({"chunk_ids": self._chunk_ids, "corpus_tokens": self._corpus_tokens})
        )

    @classmethod
    def load(cls, path: Path) -> BM25Retriever:
        data = json.loads(path.read_text())
        instance = cls.__new__(cls)
        instance._chunk_ids = data["chunk_ids"]
        instance._corpus_tokens = data["corpus_tokens"]
        instance._bm25 = BM25Okapi(instance._corpus_tokens, k1=K1, b=B)
        return instance
