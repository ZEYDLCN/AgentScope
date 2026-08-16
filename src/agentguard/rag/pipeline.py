"""RAGPipeline facade — §11.4, §12, §13.

Chunking → embedding → BM25 + FAISS indeksleme → hibrit retrieval (RRF)
→ çeşitlendirme → reranking → eşik filtresi tek bir yüzeyde birleşir.
`Embedder`/`Reranker` Protocol üzerinden enjekte edilir (testlerde fake,
prodda `SentenceTransformerEmbedder`/`CrossEncoderReranker`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from agentguard.rag.base import Embedder, Reranker
from agentguard.rag.bm25 import BM25Retriever
from agentguard.rag.chunking import chunk_knowledge_base
from agentguard.rag.hybrid import diversify_by_doc, fuse_and_rank
from agentguard.rag.vector_store import FaissVectorStore
from agentguard.schemas.knowledge import Chunk, RetrievedChunk

RETRIEVAL_TOP_K = 20
RERANK_TOP_K = 5
RERANK_MIN_SCORE = 0.20


@dataclass
class RetrievalDebugInfo:
    """§18 Dashboard "Retrieval debug" sayfası için — hibrit aramanın ve
    reranker'ın sıralamayı nasıl değiştirdiğini aşama aşama gösterir."""

    bm25_ranking: list[tuple[str, float]]
    vector_ranking: list[tuple[str, float]]
    fused_ranking: list[tuple[str, float]]
    final_results: list[RetrievedChunk]


@dataclass
class IndexManifest:
    embedding_model: str
    dimension: int
    chunk_count: int
    kb_hash: str

    def to_dict(self) -> dict[str, object]:
        return {
            "embedding_model": self.embedding_model,
            "dimension": self.dimension,
            "chunk_count": self.chunk_count,
            "kb_hash": self.kb_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IndexManifest:
        return cls(
            embedding_model=str(data["embedding_model"]),
            dimension=int(data["dimension"]),
            chunk_count=int(data["chunk_count"]),
            kb_hash=str(data["kb_hash"]),
        )


class RAGPipeline:
    def __init__(
        self,
        docstore: dict[str, Chunk],
        bm25: BM25Retriever,
        vector_store: FaissVectorStore,
        embedder: Embedder,
        reranker: Reranker | None,
        manifest: IndexManifest,
    ) -> None:
        self._docstore = docstore
        self._bm25 = bm25
        self._vector_store = vector_store
        self._embedder = embedder
        self._reranker = reranker
        self.manifest = manifest

    @property
    def embedder(self) -> Embedder:
        return self._embedder

    @property
    def reranker(self) -> Reranker | None:
        return self._reranker

    @classmethod
    def build(
        cls, knowledge_dir: Path, embedder: Embedder, *, reranker: Reranker | None = None
    ) -> RAGPipeline:
        chunks = chunk_knowledge_base(knowledge_dir)
        if not chunks:
            raise ValueError(f"{knowledge_dir} içinde chunk bulunamadı")

        docstore = {c.chunk_id: c for c in chunks}
        chunk_ids = [c.chunk_id for c in chunks]
        texts = [c.text for c in chunks]

        bm25 = BM25Retriever(chunk_ids, texts)

        vectors = embedder.embed(texts)
        vector_store = FaissVectorStore(dimension=vectors.shape[1])
        vector_store.add(chunk_ids, vectors)

        manifest = IndexManifest(
            embedding_model=getattr(embedder, "_model_name", "unknown"),
            dimension=vectors.shape[1],
            chunk_count=len(chunks),
            kb_hash=_hash_knowledge_dir(knowledge_dir),
        )

        return cls(docstore, bm25, vector_store, embedder, reranker, manifest)

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = RETRIEVAL_TOP_K,
        rerank_top_k: int = RERANK_TOP_K,
        rerank_min_score: float = RERANK_MIN_SCORE,
    ) -> list[RetrievedChunk]:
        return self.retrieve_debug(
            query, top_k=top_k, rerank_top_k=rerank_top_k, rerank_min_score=rerank_min_score
        ).final_results

    def retrieve_debug(
        self,
        query: str,
        *,
        top_k: int = RETRIEVAL_TOP_K,
        rerank_top_k: int = RERANK_TOP_K,
        rerank_min_score: float = RERANK_MIN_SCORE,
    ) -> RetrievalDebugInfo:
        """`retrieve()` ile aynı boru hattı, ama her aşamayı ayrı ayrı döner
        (§18 dashboard retrieval debug sayfası için)."""
        bm25_ranking = self._bm25.search(query, top_k)
        bm25_hits = [cid for cid, _ in bm25_ranking]

        query_vector = self._embedder.embed([query])[0].astype(np.float32)
        vector_ranking = self._vector_store.search(query_vector, top_k)
        vector_hits = [cid for cid, _ in vector_ranking]

        fused = fuse_and_rank([bm25_hits, vector_hits])
        fused_ids = [cid for cid, _ in fused]
        doc_lookup = {cid: c.doc_id for cid, c in self._docstore.items()}
        diversified = diversify_by_doc(fused_ids, doc_lookup)[:top_k]

        candidates = [self._docstore[cid] for cid in diversified if cid in self._docstore]

        if not candidates:
            final_results: list[RetrievedChunk] = []
        elif self._reranker is None:
            # Reranker yoksa (M4 unit testlerinde) RRF sırası korunur.
            fused_scores = dict(fused)
            final_results = [
                RetrievedChunk(
                    chunk=c, retrieval_rank=i + 1, rrf_score=fused_scores.get(c.chunk_id)
                )
                for i, c in enumerate(candidates)
            ]
        else:
            reranked = self._reranker.rerank(query, candidates)
            filtered = [(c, s) for c, s in reranked if s >= rerank_min_score]
            final_results = [
                RetrievedChunk(chunk=chunk, retrieval_rank=i + 1, rerank_score=score)
                for i, (chunk, score) in enumerate(filtered[:rerank_top_k])
            ]

        return RetrievalDebugInfo(
            bm25_ranking=bm25_ranking,
            vector_ranking=vector_ranking,
            fused_ranking=fused,
            final_results=final_results,
        )

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "docstore.jsonl").write_text(
            "\n".join(c.model_dump_json() for c in self._docstore.values())
        )
        self._bm25.save(directory / "bm25.json")
        self._vector_store.save(directory / "vector_store")
        manifest_json = json.dumps(self.manifest.to_dict(), indent=2)
        (directory / "index_manifest.json").write_text(manifest_json)

    @classmethod
    def load(
        cls, directory: Path, embedder: Embedder, *, reranker: Reranker | None = None
    ) -> RAGPipeline:
        docstore: dict[str, Chunk] = {}
        for line in (directory / "docstore.jsonl").read_text().splitlines():
            if not line.strip():
                continue
            chunk = Chunk.model_validate_json(line)
            docstore[chunk.chunk_id] = chunk

        bm25 = BM25Retriever.load(directory / "bm25.json")
        vector_store = FaissVectorStore.load(directory / "vector_store")
        manifest_data = json.loads((directory / "index_manifest.json").read_text())
        manifest = IndexManifest.from_dict(manifest_data)

        return cls(docstore, bm25, vector_store, embedder, reranker, manifest)


def _hash_knowledge_dir(knowledge_dir: Path) -> str:
    import hashlib

    hasher = hashlib.sha256()
    for path in sorted(knowledge_dir.rglob("*.md")):
        hasher.update(path.read_bytes())
    return hasher.hexdigest()[:16]
