"""Anomali tespit kontratları — §5.2, §8."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AnomalyType(StrEnum):
    TOOL_LOOP = "tool_loop"
    TOKEN_SPIKE = "token_spike"  # noqa: S105 — anomali adı, sır değil
    API_ABUSE = "api_abuse"
    PROMPT_INJECTION = "prompt_injection"
    PERMISSION_VIOLATION = "permission_violation"
    UNUSUAL_TOOL_SEQUENCE = "unusual_tool_sequence"
    UNKNOWN = "unknown"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DetectorScore(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    detector: str  # "isolation_forest" | "autoencoder"
    raw_score: float
    normalized_score: float = Field(ge=0.0, le=1.0)
    model_version: str


class AnomalyResult(BaseModel):
    trace_id: str
    is_anomaly: bool
    score: float = Field(ge=0.0, le=1.0)
    severity: Severity
    detector_scores: list[DetectorScore] = Field(default_factory=list)
    triggered_rules: list[str] = Field(default_factory=list)
    top_contributing_features: list[tuple[str, float]] = Field(default_factory=list)
    threshold: float
    detected_at: datetime
