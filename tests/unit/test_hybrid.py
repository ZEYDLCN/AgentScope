from __future__ import annotations

from agentguard.rag.hybrid import diversify_by_doc, fuse_and_rank, rrf


def test_rrf_boosts_items_ranked_high_in_multiple_lists() -> None:
    bm25_ranking = ["a", "b", "c"]
    vector_ranking = ["b", "a", "c"]

    scores = rrf([bm25_ranking, vector_ranking], k=60)

    # 'a' 1. ve 2. sırada, 'b' 2. ve 1. sırada -> ikisi de üstte, ikisi eşit
    assert scores["a"] == scores["b"]
    assert scores["a"] > scores["c"]


def test_rrf_reference_example_produces_expected_order() -> None:
    # Klasik RRF referans örneği: bir öğe her iki listede de 1. ise en üstte olmalı
    rankings = [["x", "y", "z"], ["x", "z", "y"]]
    fused = fuse_and_rank(rankings, k=60)
    assert fused[0][0] == "x"


def test_fuse_and_rank_returns_descending_scores() -> None:
    rankings = [["a", "b", "c"], ["c", "b", "a"]]
    fused = fuse_and_rank(rankings)
    scores = [s for _, s in fused]
    assert scores == sorted(scores, reverse=True)


def test_item_only_in_one_list_still_included() -> None:
    rankings = [["a", "b"], ["c"]]
    scores = rrf(rankings)
    assert set(scores.keys()) == {"a", "b", "c"}


def test_diversify_by_doc_caps_chunks_per_document() -> None:
    ranked = ["d1#c0", "d1#c1", "d1#c2", "d1#c3", "d2#c0"]
    doc_lookup = {
        "d1#c0": "d1",
        "d1#c1": "d1",
        "d1#c2": "d1",
        "d1#c3": "d1",
        "d2#c0": "d2",
    }
    result = diversify_by_doc(ranked, doc_lookup, max_per_doc=3)
    assert result == ["d1#c0", "d1#c1", "d1#c2", "d2#c0"]


def test_diversify_by_doc_preserves_order() -> None:
    ranked = ["a#c0", "b#c0", "a#c1"]
    doc_lookup = {"a#c0": "a", "b#c0": "b", "a#c1": "a"}
    result = diversify_by_doc(ranked, doc_lookup, max_per_doc=5)
    assert result == ranked
