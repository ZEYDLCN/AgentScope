"""LLM'den istenen JSON çıktı şeması — §14.1, §14.3.

`Investigation` domain şemasının bir alt kümesidir; `trace_id`,
`retrieved_docs`, `model_name`, `prompt_version`, `latency_ms`,
`generated_at` gibi sistem tarafından doldurulan alanlar LLM'den
istenmez. `severity`, LLM'den gelse de nihai kararda kullanılmaz
(§8, ADR-001) — yalnızca tutarsızlık metriği için loglanır.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentguard.schemas.anomaly import AnomalyType, Severity
from agentguard.schemas.investigation import EvidenceItem, Recommendation


class LLMInvestigationOutput(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    anomaly_type: AnomalyType
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    root_cause: str = Field(max_length=500)
    evidence: list[EvidenceItem] = Field(min_length=1, max_length=8)
    recommendations: list[Recommendation] = Field(min_length=1, max_length=6)


def investigation_json_schema() -> dict[str, object]:
    return LLMInvestigationOutput.model_json_schema()
