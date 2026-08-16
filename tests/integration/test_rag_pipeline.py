"""RAGPipeline uçtan uca testleri — gerçek embedding/reranker modelleri ağ
erişimi gerektirdiğinden (Hugging Face Hub), burada `Embedder`/`Reranker`
Protocol'lerini karşılayan deterministik fake'ler kullanılır (§1.5:
"Testlerde fake, prodda gerçek implementasyon")."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
from numpy.typing import NDArray

from agentguard.rag.pipeline import RAGPipeline
from agentguard.schemas.knowledge import Chunk

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"


class FakeEmbedder:
    """Kelime-hash tabanlı deterministik "embedding" — anlam taşımaz ama
    aynı kelimeleri paylaşan metinler birbirine yakın vektör üretir."""

    dimension = 32

    def embed(self, texts: list[str]) -> NDArray[np.float32]:
        vectors = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for i, text in enumerate(texts):
            for word in text.lower().split():
                h = int(hashlib.sha256(word.encode()).hexdigest(), 16)
                vectors[i, h % self.dimension] += 1.0
            norm = np.linalg.norm(vectors[i])
            if norm > 0:
                vectors[i] /= norm
        return vectors


class FakeReranker:
    """Jaccard kelime örtüşmesine dayalı basit reranker."""

    def rerank(self, query: str, chunks: list[Chunk]) -> list[tuple[Chunk, float]]:
        query_words = set(query.lower().split())
        scored = []
        for chunk in chunks:
            chunk_words = set(chunk.text.lower().split())
            union = query_words | chunk_words
            score = len(query_words & chunk_words) / len(union) if union else 0.0
            scored.append((chunk, score))
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored


@pytest.fixture
def small_kb(tmp_path: Path) -> Path:
    kb = tmp_path / "knowledge"
    (kb / "failure_modes").mkdir(parents=True)
    (kb / "runbooks").mkdir(parents=True)

    (kb / "failure_modes" / "tool_loop.md").write_text(
        "---\n"
        "doc_id: tool_loop\n"
        "title: Tool Loop\n"
        "category: reference\n"
        "anomaly_types: [tool_loop]\n"
        "severity_scope: [high]\n"
        "version: 1.0\n"
        "updated: 2026-07-01\n"
        "---\n\n"
        "## Tespit Sinyalleri\n\n"
        "Tekrarlanan araç çağrıları, aynı input_hash ile tool loop belirtisidir. "
        "max_consecutive_repeats sinyali izlenmelidir.\n"
    )
    (kb / "runbooks" / "rb_terminate.md").write_text(
        "---\n"
        "doc_id: rb_terminate\n"
        "title: Terminate Runbook\n"
        "category: runbook\n"
        "anomaly_types: [tool_loop]\n"
        "severity_scope: [critical]\n"
        "version: 1.0\n"
        "updated: 2026-07-01\n"
        "---\n\n"
        "## Adımlar\n\n"
        "Agent'ı duraklat ve loop döngüsünü incele. Weather forecast unrelated text here.\n"
    )
    return kb


def test_pipeline_build_indexes_all_chunks(small_kb: Path) -> None:
    pipeline = RAGPipeline.build(small_kb, FakeEmbedder())
    assert pipeline.manifest.chunk_count >= 2
    assert pipeline.manifest.dimension == 32


def test_bm25_and_faiss_share_same_chunk_id_set(small_kb: Path) -> None:
    pipeline = RAGPipeline.build(small_kb, FakeEmbedder())
    bm25_ids = set(pipeline._bm25._chunk_ids)
    vector_ids = set(pipeline._vector_store._chunk_ids)
    assert bm25_ids == vector_ids
    assert bm25_ids == set(pipeline._docstore.keys())


def test_retrieve_without_reranker_returns_rrf_order(small_kb: Path) -> None:
    pipeline = RAGPipeline.build(small_kb, FakeEmbedder(), reranker=None)
    results = pipeline.retrieve("tool loop repeated calls input_hash")
    assert results
    assert results[0].chunk.doc_id == "tool_loop"
    assert results[0].rrf_score is not None
    assert results[0].rerank_score is None


def test_retrieve_with_reranker_filters_below_threshold(small_kb: Path) -> None:
    pipeline = RAGPipeline.build(small_kb, FakeEmbedder(), reranker=FakeReranker())
    # rerank_min_score çoğu chunk'ı eleyecek kadar yüksek tutulur
    results = pipeline.retrieve("tool loop repeated calls input_hash", rerank_min_score=0.9)
    # Yüksek eşik nedeniyle 5'ten AZ (muhtemelen 0) sonuç dönebilir — bu beklenen davranış (§13).
    assert len(results) <= 5
    for r in results:
        assert r.rerank_score is not None
        assert r.rerank_score >= 0.9


def test_retrieve_empty_result_when_nothing_passes_threshold(small_kb: Path) -> None:
    pipeline = RAGPipeline.build(small_kb, FakeEmbedder(), reranker=FakeReranker())
    results = pipeline.retrieve("completely unrelated query xyz123", rerank_min_score=0.99)
    assert results == []


def test_save_and_load_roundtrip(tmp_path: Path, small_kb: Path) -> None:
    pipeline = RAGPipeline.build(small_kb, FakeEmbedder())
    out_dir = tmp_path / "index"
    pipeline.save(out_dir)

    loaded = RAGPipeline.load(out_dir, FakeEmbedder())
    assert loaded.manifest.chunk_count == pipeline.manifest.chunk_count

    original = pipeline.retrieve("tool loop", rerank_min_score=0.0)
    reloaded = loaded.retrieve("tool loop", rerank_min_score=0.0)
    assert [r.chunk.chunk_id for r in original] == [r.chunk.chunk_id for r in reloaded]


def test_build_against_real_knowledge_base_tool_loop_query() -> None:
    pipeline = RAGPipeline.build(KNOWLEDGE_DIR, FakeEmbedder(), reranker=FakeReranker())
    results = pipeline.retrieve(
        "agent tool loop repeated calls max_consecutive_repeats", rerank_min_score=0.0
    )
    assert results
    top_doc_ids = {r.chunk.doc_id for r in results}
    assert "tool_loop" in top_doc_ids


def test_retrieve_debug_exposes_each_stage() -> None:
    # Küçük 2 dokümanlık fixture'da BM25 IDF'i neredeyse sıfırlayabilir;
    # gerçek 18 dokümanlık KB ile aşama yapısı daha güvenilir doğrulanır.
    pipeline = RAGPipeline.build(KNOWLEDGE_DIR, FakeEmbedder(), reranker=FakeReranker())
    debug = pipeline.retrieve_debug(
        "agent tool loop repeated calls max_consecutive_repeats", rerank_min_score=0.0
    )

    assert debug.bm25_ranking
    assert debug.vector_ranking
    assert debug.fused_ranking
    assert debug.final_results
    # Her aşamanın kendi skorları olmalı (yan yana karşılaştırma için, §18)
    assert all(isinstance(score, float) for _, score in debug.bm25_ranking)
    assert all(isinstance(score, float) for _, score in debug.vector_ranking)


def test_retrieve_matches_retrieve_debug_final_results(small_kb: Path) -> None:
    pipeline = RAGPipeline.build(small_kb, FakeEmbedder(), reranker=FakeReranker())
    direct = pipeline.retrieve("tool loop", rerank_min_score=0.0)
    debug = pipeline.retrieve_debug("tool loop", rerank_min_score=0.0)
    assert [r.chunk.chunk_id for r in direct] == [r.chunk.chunk_id for r in debug.final_results]
