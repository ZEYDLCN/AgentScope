# AgentGuard backend + Ollama — Hugging Face Spaces (Docker SDK) için TEK
# container'lı deploy. `docker/Dockerfile.api` (prod, çok servisli
# docker-compose) ile KARIŞTIRMAYIN — bu, HF Spaces'in "tek Dockerfile,
# kalıcı disk yok (ücretsiz katman)" modeline özel, kendi kendine yeten bir
# varyanttır: Ollama + API aynı container'da, açılışta bootstrap kendini
# (idempotent) çalıştırır.
#
# Kullanım: bkz. deploy/huggingface/README.md

FROM python:3.11-slim

# --- Ollama'nın kendi kurulum betiği için gerekli araçlar ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://ollama.com/install.sh | sh

# --- HF Spaces container'ları non-root (UID 1000) çalıştırmayı önerir ---
RUN useradd -m -u 1000 appuser
WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY knowledge/ ./knowledge/
COPY scripts/ ./scripts/
COPY deploy/huggingface/entrypoint.sh ./entrypoint.sh

RUN pip install --no-cache-dir -e . && chmod +x ./entrypoint.sh

# HF Spaces varsayılan port beklentisi (Space ayarlarında değiştirilmedikçe)
ENV PORT=7860 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/hf \
    TOKENIZERS_PARALLELISM=false \
    HOME=/home/appuser \
    OLLAMA_HOST=127.0.0.1:11434 \
    AG_ARTIFACTS_PATH=/app/artifacts/current \
    AG_INDEX_PATH=/app/artifacts/index \
    AG_KNOWLEDGE_PATH=/app/knowledge \
    AG_DATABASE_URL=sqlite+aiosqlite:////app/data/agentguard.db \
    AG_OLLAMA_BASE_URL=http://127.0.0.1:11434 \
    AG_OLLAMA_MODEL=qwen2.5:3b-instruct

RUN mkdir -p /app/data /app/artifacts /app/.cache/hf /home/appuser/.ollama \
    && chown -R appuser:appuser /app /home/appuser

USER appuser
EXPOSE 7860

CMD ["./entrypoint.sh"]
