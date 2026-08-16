"""RAG retrieval ablation değerlendirmesi — §15.

`tests/fixtures/golden_rag.jsonl` altın kümesi üzerinde dört yapılandırmayı
karşılaştırır: sadece BM25, sadece vector, hibrit (RRF), hibrit + reranker.
Metrikler doküman (`doc_id`) düzeyinde ikili (binary) relevance ile
hesaplanır — chunk sınırları chunking parametreleri değiştikçe kayabildiği
için altın küme doküman düzeyinde tutulur (§15.1'in basitleştirilmiş bir
uygulaması; tam chunk-düzeyi altın küme v2'de ele alınabilir).

Bu ortamda Hugging Face Hub'a ağ erişimi olmadığından, varsayılan olarak
`train_models.py`/M4 testlerindeki ile aynı deterministik "fake" embedder
ve reranker kullanılır (§1.5: "testlerde fake, prodda gerçek
implementasyon"). Gerçek `bge-m3`/`bge-reranker-v2-m3` ile çalıştırmak için
`--real` bayrağını kullanın (ağ erişimi gerektirir).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentguard.rag.pipeline import RAGPipeline
from agentguard.schemas.knowledge import Chunk

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = ROOT / "tests" / "fixtures" / "golden_rag.jsonl"
TOP_K = 20
RERANK_TOP_K = 5
# Prod eşiği (§13) 0.20'dir; burada 0.0 kullanılır çünkü bu script'in amacı
# reranker'ın SIRALAMA kalitesini ablation olarak ölçmektir, eşik-altı
# filtrelemeyi değil — filtreleme skor dağılımına duyarlıdır ve fake
# (Jaccard) reranker'ın ham skorları gerçek cross-encoder'ınkiyle aynı
# ölçekte değildir.
RERANK_MIN_SCORE = 0.0


class FakeEmbedder:
    """Kelime-hash tabanlı deterministik "embedding" — bkz.
    `tests/integration/test_rag_pipeline.py::FakeEmbedder`."""

    dimension = 64
    _model_name = "fake-bow-hash-eval"

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


def _load_golden(path: Path) -> list[dict[str, object]]:
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _dcg(relevances: list[int]) -> float:
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))


def _ndcg_at_k(ranked_docs: list[str], relevant: set[str], k: int) -> float:
    top = ranked_docs[:k]
    gains = [1 if d in relevant else 0 for d in top]
    ideal = sorted(gains, reverse=True)
    ideal_dcg = _dcg(ideal)
    if ideal_dcg == 0:
        return 0.0
    return _dcg(gains) / ideal_dcg


def _recall_at_k(ranked_docs: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    hit = len(set(ranked_docs[:k]) & relevant)
    return hit / len(relevant)


def _mrr_at_k(ranked_docs: list[str], relevant: set[str], k: int) -> float:
    for i, d in enumerate(ranked_docs[:k]):
        if d in relevant:
            return 1.0 / (i + 1)
    return 0.0


def _dedupe_docs(chunk_ids: list[str], doc_lookup: dict[str, str]) -> list[str]:
    seen: list[str] = []
    for cid in chunk_ids:
        doc_id = doc_lookup.get(cid)
        if doc_id is not None and doc_id not in seen:
            seen.append(doc_id)
    return seen


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(int(math.ceil(pct / 100 * len(ordered))) - 1, len(ordered) - 1)
    return ordered[max(idx, 0)]


def _evaluate_config(
    name: str,
    pipeline: RAGPipeline,
    golden: list[dict[str, object]],
    doc_lookup: dict[str, str],
    stage: str,
) -> dict[str, object]:
    recalls_5: list[float] = []
    recalls_20: list[float] = []
    ndcgs_5: list[float] = []
    mrrs_5: list[float] = []
    latencies_ms: list[float] = []

    for row in golden:
        query = str(row["query"])
        relevant = set(row["relevant_docs"])  # type: ignore[arg-type]

        started = time.perf_counter()
        debug = pipeline.retrieve_debug(
            query, top_k=TOP_K, rerank_top_k=RERANK_TOP_K, rerank_min_score=RERANK_MIN_SCORE
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        latencies_ms.append(elapsed_ms)

        if stage == "bm25":
            ranked = _dedupe_docs([cid for cid, _ in debug.bm25_ranking], doc_lookup)
        elif stage == "vector":
            ranked = _dedupe_docs([cid for cid, _ in debug.vector_ranking], doc_lookup)
        elif stage == "hybrid":
            ranked = _dedupe_docs([cid for cid, _ in debug.fused_ranking], doc_lookup)
        else:  # hybrid_rerank
            ranked = _dedupe_docs([rc.chunk.chunk_id for rc in debug.final_results], doc_lookup)

        recalls_5.append(_recall_at_k(ranked, relevant, 5))
        recalls_20.append(_recall_at_k(ranked, relevant, 20))
        ndcgs_5.append(_ndcg_at_k(ranked, relevant, 5))
        mrrs_5.append(_mrr_at_k(ranked, relevant, 5))

    return {
        "config": name,
        "recall_at_5": round(sum(recalls_5) / len(recalls_5), 4),
        "recall_at_20": round(sum(recalls_20) / len(recalls_20), 4),
        "ndcg_at_5": round(sum(ndcgs_5) / len(ndcgs_5), 4),
        "mrr_at_5": round(sum(mrrs_5) / len(mrrs_5), 4),
        "p95_latency_ms": round(_percentile(latencies_ms, 95), 3),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="RAG retrieval ablation değerlendirmesi (§15)")
    parser.add_argument("--knowledge-dir", type=Path, default=ROOT / "knowledge")
    parser.add_argument("--golden", type=Path, default=GOLDEN_PATH)
    parser.add_argument("--out", type=Path, default=ROOT / "reports")
    parser.add_argument(
        "--real",
        action="store_true",
        help="Gerçek bge-m3/bge-reranker-v2-m3 modelleriyle çalıştır (ağ erişimi gerekir)",
    )
    args = parser.parse_args(argv)

    golden = _load_golden(args.golden)

    if args.real:
        from agentguard.rag.embeddings import SentenceTransformerEmbedder
        from agentguard.rag.reranker import CrossEncoderReranker

        embedder = SentenceTransformerEmbedder("BAAI/bge-m3")
        reranker: object = CrossEncoderReranker("BAAI/bge-reranker-v2-m3")
    else:
        embedder = FakeEmbedder()
        reranker = FakeReranker()

    pipeline = RAGPipeline.build(args.knowledge_dir, embedder, reranker=reranker)  # type: ignore[arg-type]
    doc_lookup = {cid: c.doc_id for cid, c in pipeline._docstore.items()}

    results = [
        _evaluate_config("Sadece BM25", pipeline, golden, doc_lookup, "bm25"),
        _evaluate_config("Sadece Vector", pipeline, golden, doc_lookup, "vector"),
        _evaluate_config("Hybrid (RRF)", pipeline, golden, doc_lookup, "hybrid"),
        _evaluate_config("Hybrid + Reranker", pipeline, golden, doc_lookup, "hybrid_rerank"),
    ]

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    args.out.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": timestamp,
        "golden_set_size": len(golden),
        "chunk_count": pipeline.manifest.chunk_count,
        "embedder": "real" if args.real else "fake-bow-hash",
        "results": results,
    }
    json_path = args.out / f"rag_eval_{timestamp}.json"
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    lines = [
        f"# AgentGuard RAG Ablation Raporu — {timestamp}",
        "",
        f"Altın küme: {len(golden)} sorgu, {pipeline.manifest.chunk_count} chunk "
        f"({'gerçek' if args.real else 'fake (bag-of-words hash)'} embedder).",
        "",
        "| Yapılandırma | Recall@5 | Recall@20 | nDCG@5 | MRR@5 | p95 latency (ms) |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['config']} | {r['recall_at_5']:.4f} | {r['recall_at_20']:.4f} | "
            f"{r['ndcg_at_5']:.4f} | {r['mrr_at_5']:.4f} | {r['p95_latency_ms']:.2f} |"
        )
    lines.append("")
    lines.append("## Hedefler (§15.2, v1)")
    lines.append("")
    lines.append(
        "- Recall@20 (füzyon sonrası) ≥ 0.90 · Recall@5 (rerank sonrası) ≥ 0.85 · "
        "MRR@5 ≥ 0.75 · nDCG@5 ≥ 0.80"
    )
    if not args.real:
        lines.append("")
        lines.append(
            "**Not:** bu rapor deterministik fake embedder/reranker ile üretildi (ağ "
            "erişimi olmayan CI/sandbox ortamı); mutlak sayılar gerçek `bge-m3`/"
            "`bge-reranker-v2-m3` ile farklılık gösterecektir — asıl kanıt değeri "
            "**yapılandırmalar arası göreli sıralamadır** (hybrid+rerank ≥ hybrid ≥ "
            "tekil kollar beklenir). `--real` bayrağıyla prod modelleriyle yeniden "
            "üretilmelidir."
        )
    md_path = args.out / f"rag_eval_{timestamp}.md"
    md_path.write_text("\n".join(lines) + "\n")

    print(f"yazıldı: {json_path}")
    print(f"yazıldı: {md_path}")
    for r in results:
        print(
            f"{r['config']:<20} recall@5={r['recall_at_5']:.4f} "
            f"recall@20={r['recall_at_20']:.4f} ndcg@5={r['ndcg_at_5']:.4f} "
            f"mrr@5={r['mrr_at_5']:.4f} p95={r['p95_latency_ms']:.2f}ms"
        )


if __name__ == "__main__":
    main()
