"""Bilgi tabanını indeksler — §11.4.

`knowledge/**.md` → front-matter parse → header-aware chunking →
embedding → FAISS + BM25 → `artifacts/index/`.

Not: Gerçek çalıştırma, `AG_EMBEDDING_MODEL` (varsayılan `BAAI/bge-m3`)
ağırlıklarını Hugging Face Hub'dan indirir; ağ erişimi gerektirir.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentguard.rag.embeddings import SentenceTransformerEmbedder
from agentguard.rag.pipeline import RAGPipeline


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="AgentGuard bilgi tabanı indeksleyici (§11.4)")
    parser.add_argument("--knowledge-dir", type=Path, default=Path("knowledge"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/index"))
    parser.add_argument("--embedding-model", type=str, default="BAAI/bge-m3")
    args = parser.parse_args(argv)

    embedder = SentenceTransformerEmbedder(args.embedding_model)
    pipeline = RAGPipeline.build(args.knowledge_dir, embedder)
    pipeline.save(args.out)

    print(
        f"indekslendi: {pipeline.manifest.chunk_count} chunk, "
        f"boyut={pipeline.manifest.dimension}, kb_hash={pipeline.manifest.kb_hash} -> {args.out}"
    )


if __name__ == "__main__":
    main()
