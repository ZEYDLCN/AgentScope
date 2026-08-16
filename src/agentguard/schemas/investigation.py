"""Soruşturma raporu kontratları — §5.2, §14.

`Investigation.severity` LLM'den GELMEZ; `AnomalyResult.severity` kopyalanır.
LLM'in önerdiği severity yalnızca loglanır ve tutarsızlık metriği olarak
sayılır (§8, ADR-001).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from agentguard.schemas.anomaly import AnomalyType, Severity


class EvidenceItem(BaseModel):
    statement: str = Field(max_length=300)
    source: str  # "trace:repeated_tool_calls" | "doc:tool_loop.md#c3"
    value: str | None = None


class Recommendation(BaseModel):
    action: str
    priority: int = Field(ge=1, le=5)
    rationale: str


class Investigation(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    trace_id: str
    anomaly_type: AnomalyType
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    root_cause: str = Field(max_length=500)
    evidence: list[EvidenceItem] = Field(min_length=1, max_length=8)
    recommendations: list[Recommendation] = Field(min_length=1, max_length=6)
    retrieved_docs: list[str] = Field(default_factory=list)  # chunk_id listesi
    model_name: str
    prompt_version: str
    generated_by: str = "llm"  # "llm" | "fallback"
    latency_ms: int
    generated_at: datetime
