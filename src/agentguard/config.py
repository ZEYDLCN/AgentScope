"""Uygulama ayarları — tek doğruluk kaynağı, 12-factor.

Tüm çalışma zamanı yapılandırması buradan geçer; kod içinde sabit yol
veya sihirli sayı bulunmaz. Eşikler ve füzyon ağırlıkları burada
değil, `artifacts/current/thresholds.json` içinde tutulur (bkz. ADR-004).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="AG_",
        extra="forbid",  # yazım hatası = başlatma hatası
    )

    env: Literal["dev", "test", "prod"] = "dev"
    api_key: SecretStr = SecretStr("dev-local-key")
    database_url: str = "sqlite+aiosqlite:///./data/agentguard.db"

    # Yalnızca dashboard origin'i (§16.2 CORS, §21.3). Virgülle ayrılmış liste.
    cors_origins: str = "http://localhost:8501"

    artifacts_path: Path = Path("artifacts/current")
    index_path: Path = Path("artifacts/index")
    knowledge_path: Path = Path("knowledge")

    embedding_model: str = "BAAI/bge-m3"
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    rerank_top_k: int = 5
    rerank_min_score: float = 0.20
    retrieval_top_k: int = 20
    rrf_k: int = 60

    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:7b-instruct-q4_K_M"
    llm_timeout_connect_s: int = 5
    llm_timeout_read_s: int = 120

    fusion_weight_if: float = 0.5
    fusion_weight_ae: float = 0.5

    feature_version: str = "v1"

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Süreç ömrü boyunca tekil `Settings` örneği."""
    return Settings()
