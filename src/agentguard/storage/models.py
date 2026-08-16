"""SQLAlchemy ORM modelleri — §17.1.

SQLite'ta `JSONB` yerine `JSON` kullanılır; SQLAlchemy `JSON` tipi ikisini
de karşılar (dev=SQLite, prod=PostgreSQL).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TraceRecord(Base):
    __tablename__ = "traces"

    trace_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(128), index=True)
    agent_version: Mapped[str] = mapped_column(String(64), default="unknown")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, object]] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("ix_traces_agent_started", "agent_id", "started_at"),)


class FeatureRecord(Base):
    __tablename__ = "features"

    trace_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("traces.trace_id"), primary_key=True
    )
    version: Mapped[str] = mapped_column(String(16))
    values: Mapped[list[float]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DetectionRecord(Base):
    __tablename__ = "detections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trace_id: Mapped[str] = mapped_column(String(64), ForeignKey("traces.trace_id"), index=True)
    is_anomaly: Mapped[bool]
    score: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(16))
    threshold: Mapped[float] = mapped_column(Float)
    detector_scores: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    triggered_rules: Mapped[list[str]] = mapped_column(JSON)
    model_version: Mapped[str] = mapped_column(String(64))
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    __table_args__ = (Index("ix_detections_severity_detected", "severity", "detected_at"),)


class InvestigationRecord(Base):
    __tablename__ = "investigations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trace_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("traces.trace_id"), unique=True, index=True
    )
    anomaly_type: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float)
    root_cause: Mapped[str] = mapped_column(String(500))
    evidence: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    recommendations: Mapped[list[dict[str, object]]] = mapped_column(JSON)
    retrieved_docs: Mapped[list[str]] = mapped_column(JSON)
    model_name: Mapped[str] = mapped_column(String(128))
    prompt_version: Mapped[str] = mapped_column(String(32))
    generated_by: Mapped[str] = mapped_column(String(16), default="llm")
    latency_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class JobRecord(Base):
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    kind: Mapped[str] = mapped_column(String(32))
    trace_id: Mapped[str] = mapped_column(String(64), ForeignKey("traces.trace_id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
