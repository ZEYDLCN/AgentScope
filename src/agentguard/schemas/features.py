"""Özellik vektörü kontratı — §5.2, §7."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FeatureVector(BaseModel):
    trace_id: str
    values: list[float] = Field(min_length=1)  # FEATURE_ORDER ile aynı sırada
    version: str = "v1"  # özellik seti sürümü
