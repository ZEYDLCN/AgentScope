"""Bilgi tabanı doküman/chunk kontratları — §11.

Retrieval katmanı (M4) tarafından üretilir ve tüketilir; şema burada tek
doğruluk kaynağı olarak tanımlanır.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field

from agentguard.schemas.anomaly import AnomalyType, Severity


class DocCategory(StrEnum):
    POLICY = "policy"
    RUNBOOK = "runbook"
    INCIDENT = "incident"
    REFERENCE = "reference"


class DocumentMeta(BaseModel):
    """`knowledge/**.md` dosyalarının YAML front-matter'ı — §11.1."""

    doc_id: str
    title: str
    category: DocCategory
    anomaly_types: list[AnomalyType] = Field(default_factory=list)
    severity_scope: list[Severity] = Field(default_factory=list)
    version: str = "1.0"
    updated: date


class Chunk(BaseModel):
    """`chunk_id` formatı: `{doc_id}#c{index}` — kanıt atıflarında birebir kullanılır."""

    chunk_id: str
    doc_id: str
    section: str
    text: str
    token_count: int = Field(ge=0)
    meta: DocumentMeta


class RetrievedChunk(BaseModel):
    chunk: Chunk
    retrieval_rank: int = Field(ge=1)
    rrf_score: float | None = None
    rerank_score: float | None = None
