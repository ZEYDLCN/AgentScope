"""Reciprocal Rank Fusion (RRF) — §12.3.

Skor ölçekleri karşılaştırılamaz (BM25 sınırsız, kosinüs [-1,1]); RRF
sıra-tabanlı ve ölçek-bağımsızdır.
"""

from __future__ import annotations

from collections import defaultdict

DEFAULT_RRF_K = 60
MAX_CHUNKS_PER_DOC = 3  # tek dokümanın bağlamı domine etmesini önler (§12.4)


def rrf(rankings: list[list[str]], k: int = DEFAULT_RRF_K) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] += 1.0 / (k + rank)
    return dict(scores)


def fuse_and_rank(rankings: list[list[str]], *, k: int = DEFAULT_RRF_K) -> list[tuple[str, float]]:
    scores = rrf(rankings, k=k)
    return sorted(scores.items(), key=lambda t: t[1], reverse=True)


def diversify_by_doc(
    ranked_chunk_ids: list[str],
    doc_id_lookup: dict[str, str],
    *,
    max_per_doc: int = MAX_CHUNKS_PER_DOC,
) -> list[str]:
    """Aynı `doc_id`'den `max_per_doc`'tan fazla chunk varsa budar (§12.4)."""
    counts: dict[str, int] = defaultdict(int)
    out: list[str] = []
    for chunk_id in ranked_chunk_ids:
        doc_id = doc_id_lookup.get(chunk_id, chunk_id)
        if counts[doc_id] >= max_per_doc:
            continue
        counts[doc_id] += 1
        out.append(chunk_id)
    return out
