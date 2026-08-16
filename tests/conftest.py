from __future__ import annotations

import os

os.environ.setdefault("AG_ENV", "test")
os.environ.setdefault("AG_API_KEY", "test-api-key")
os.environ.setdefault("AG_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
# Testler, geliştirme sandbox'ında `make bootstrap`'tan kalan gerçek
# artifacts/index dizinlerini YANLIŞLIKLA yüklememeli — aksi halde testler
# ortam durumuna bağımlı hale gelir (bazen detector yüklü, bazen değil) ve
# gerçek Ollama'ya bağlanmaya çalışıp yavaşlar. Var olmayan sabit yollar
# kullanılır; detector/rag enjeksiyonu isteyen testler `app.state`'i
# TestClient başladıktan SONRA elle override eder (bkz. test_investigate_api.py).
os.environ.setdefault("AG_ARTIFACTS_PATH", "/nonexistent/artifacts/current")
os.environ.setdefault("AG_INDEX_PATH", "/nonexistent/artifacts/index")

import pytest
from fastapi.testclient import TestClient

from agentguard.api.app import create_app
from agentguard.api.ratelimit import limiter
from agentguard.config import get_settings

TEST_API_KEY = "test-api-key"


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    # `limiter` modül düzeyinde tekil (prodda tek app instance'ı için doğru),
    # ama testlerde her `client` fixture'ı yeni bir app kurduğundan, önceki
    # testin sayaçları sızmasın diye her testten önce/sonra sıfırlanır.
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    with TestClient(app, headers={"X-API-Key": TEST_API_KEY}) as test_client:
        yield test_client
