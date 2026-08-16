from __future__ import annotations

from agentguard.rag.bm25 import BM25Retriever, tokenize


def test_tokenize_lowercases_and_strips_stopwords() -> None:
    tokens = tokenize("Bu bir Tool Loop ve API Abuse durumudur.")
    assert "bu" not in tokens
    assert "ve" not in tokens
    assert "tool" in tokens
    assert "loop" in tokens


def test_search_ranks_relevant_document_first() -> None:
    chunk_ids = ["a#c0", "b#c0", "c#c0"]
    texts = [
        "tool loop repeated calls detected in database queries",
        "token spike total tokens exceeded ceiling",
        "unrelated document about weather forecasting",
    ]
    retriever = BM25Retriever(chunk_ids, texts)

    results = retriever.search("tool loop database", top_k=3)
    assert results[0][0] == "a#c0"


def test_search_respects_top_k() -> None:
    chunk_ids = [f"doc{i}#c0" for i in range(10)]
    texts = [f"tool loop event number {i}" for i in range(10)]
    retriever = BM25Retriever(chunk_ids, texts)

    results = retriever.search("tool loop", top_k=3)
    assert len(results) <= 3


def test_search_excludes_zero_score_results() -> None:
    chunk_ids = ["a#c0", "b#c0"]
    texts = ["tool loop database", "completely unrelated weather forecast text"]
    retriever = BM25Retriever(chunk_ids, texts)

    results = retriever.search("tool loop database", top_k=10)
    returned_ids = {cid for cid, _ in results}
    assert "b#c0" not in returned_ids


def test_save_load_roundtrip_produces_same_results(tmp_path) -> None:  # type: ignore[no-untyped-def]
    chunk_ids = ["a#c0", "b#c0"]
    texts = ["tool loop database repeated", "token spike ceiling exceeded"]
    retriever = BM25Retriever(chunk_ids, texts)

    path = tmp_path / "bm25.json"
    retriever.save(path)
    loaded = BM25Retriever.load(path)

    assert retriever.search("tool loop", top_k=5) == loaded.search("tool loop", top_k=5)
