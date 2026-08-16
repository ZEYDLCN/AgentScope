"""`scripts/run_rag_eval.py` metrik fonksiyonlarının testleri (§15.2).

`scripts/` doğrudan pytest tarafından bulunamaz (paket değil); `sys.path`e
kök dizin eklenerek import edilir (bkz. `test_synthetic_generator.py`).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from run_rag_eval import _mrr_at_k, _ndcg_at_k, _recall_at_k


def test_recall_at_k_counts_unique_relevant_hits() -> None:
    ranked = ["a", "b", "c", "d", "e"]
    relevant = {"c", "z"}  # "z" hiç dönmüyor
    assert _recall_at_k(ranked, relevant, 5) == 0.5


def test_recall_at_k_empty_relevant_set_is_zero() -> None:
    assert _recall_at_k(["a", "b"], set(), 5) == 0.0


def test_mrr_at_k_uses_first_hit_rank() -> None:
    ranked = ["x", "y", "a", "b"]
    assert _mrr_at_k(ranked, {"a"}, 5) == 1 / 3


def test_mrr_at_k_zero_when_no_hit_within_k() -> None:
    assert _mrr_at_k(["x", "y", "z"], {"a"}, 2) == 0.0


def test_ndcg_at_k_perfect_ranking_is_one() -> None:
    ranked = ["a", "b", "x", "y"]
    assert _ndcg_at_k(ranked, {"a", "b"}, 4) == 1.0


def test_ndcg_at_k_zero_when_no_relevant_docs_at_all() -> None:
    assert _ndcg_at_k(["x", "y"], set(), 4) == 0.0


def test_ndcg_at_k_penalizes_relevant_doc_ranked_lower() -> None:
    perfect = _ndcg_at_k(["a", "x", "y"], {"a"}, 3)
    worse = _ndcg_at_k(["x", "y", "a"], {"a"}, 3)
    assert worse < perfect
