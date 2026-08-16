"""`/v1/knowledge` — retrieval debug + yeniden indeksleme (§16.1, §18).

Retrieval debug sayfası, hibrit aramanın ve reranker'ın sıralamayı nasıl
değiştirdiğini yan yana gösterir; dashboard'da en çok etki eden ekrandır.
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, HTTPException, Request, status

from agentguard.api.deps import require_api_key
from agentguard.logging import get_logger

router = APIRouter(prefix="/v1", tags=["knowledge"], dependencies=[Depends(require_api_key)])
logger = get_logger("api.knowledge")


@router.get("/knowledge/search")
async def search_knowledge(q: str, request: Request, top_k: int = 20) -> dict[str, object]:
    rag = getattr(request.app.state, "rag", None)
    if rag is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="RAG index yüklü değil"
        )

    debug = rag.retrieve_debug(q, top_k=top_k)
    return {
        "query": q,
        "bm25": [{"chunk_id": cid, "score": score} for cid, score in debug.bm25_ranking],
        "vector": [{"chunk_id": cid, "score": score} for cid, score in debug.vector_ranking],
        "fused_rrf": [{"chunk_id": cid, "score": score} for cid, score in debug.fused_ranking],
        "final": [
            {
                "chunk_id": r.chunk.chunk_id,
                "doc_id": r.chunk.doc_id,
                "section": r.chunk.section,
                "rank": r.retrieval_rank,
                "rrf_score": r.rrf_score,
                "rerank_score": r.rerank_score,
                "text_preview": r.chunk.text[:300],
            }
            for r in debug.final_results
        ],
    }


async def _reindex_task(app: FastAPI, knowledge_path: str, index_path: str) -> None:
    from pathlib import Path

    from agentguard.rag.pipeline import RAGPipeline

    rag: RAGPipeline | None = app.state.rag
    if rag is None:
        logger.error("knowledge.reindex_failed", reason="RAG pipeline yüklü değil (embedder yok)")
        return
    try:
        new_pipeline = RAGPipeline.build(Path(knowledge_path), rag.embedder, reranker=rag.reranker)
        new_pipeline.save(Path(index_path))
        app.state.rag = new_pipeline
        logger.info("knowledge.reindex_complete", chunk_count=new_pipeline.manifest.chunk_count)
    except Exception as exc:
        logger.error("knowledge.reindex_failed", error=str(exc))


@router.post("/knowledge/reindex", status_code=status.HTTP_202_ACCEPTED)
async def reindex_knowledge(request: Request, background_tasks: BackgroundTasks) -> dict[str, str]:
    from agentguard.config import get_settings

    settings = get_settings()
    background_tasks.add_task(
        _reindex_task, request.app, str(settings.knowledge_path), str(settings.index_path)
    )
    return {"status": "queued"}
