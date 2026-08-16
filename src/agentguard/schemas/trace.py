"""Trace (girdi kontratı) — §5.1.

`schemas` katmanı hiçbir iç modüle bağımlı değildir (import-linter ile
zorlanır); yalnızca pydantic'e bağımlıdır.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class ToolStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    DENIED = "denied"  # yetki reddi — permission_violation sinyali


class ToolCall(BaseModel):
    index: int = Field(ge=0)  # trace içindeki sıra
    tool_name: str = Field(min_length=1, max_length=128)
    started_at: datetime
    ended_at: datetime
    status: ToolStatus
    duration_ms: int = Field(ge=0)
    input_hash: str  # ham girdi DEĞİL, sha256[:16]
    input_preview: str | None = Field(default=None, max_length=512)
    output_size_bytes: int = Field(ge=0, default=0)
    error_type: str | None = None

    @model_validator(mode="after")
    def _check_time(self) -> ToolCall:
        if self.ended_at < self.started_at:
            raise ValueError("ended_at < started_at")
        return self


class TokenUsage(BaseModel):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)


class AgentTrace(BaseModel):
    trace_id: str = Field(pattern=r"^[a-zA-Z0-9_\-]{8,64}$")
    agent_id: str
    agent_version: str = "unknown"
    session_id: str | None = None
    started_at: datetime
    ended_at: datetime
    user_prompt_preview: str | None = Field(default=None, max_length=1024)
    tool_calls: list[ToolCall] = Field(default_factory=list, max_length=500)
    token_usage: TokenUsage
    final_status: str = "completed"  # completed | failed | terminated
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_time(self) -> AgentTrace:
        if self.ended_at < self.started_at:
            raise ValueError("ended_at < started_at")
        return self
