"""Dashboard sayfalarının en azından hatasız yüklendiğini doğrular
(`streamlit.testing.v1.AppTest`). API erişilemez olduğunda sayfaların
çökmeden zarif bir uyarı göstermesi beklenir (§18 — dashboard, API'siz
de ayakta kalmalı)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest

DASHBOARD_DIR = Path(__file__).resolve().parents[2] / "dashboard"

pytestmark = pytest.mark.slow  # Streamlit script çalıştırma modül import'ları içerir


@pytest.fixture(autouse=True)
def _unreachable_api(monkeypatch: pytest.MonkeyPatch) -> None:
    # Gerçek bir API çalışmadığından, istemcinin "erişilemez" yolunu
    # (graceful degradation) egzersiz ederiz.
    monkeypatch.setenv("AG_API_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("AG_API_KEY", "test")


def _run(path: Path):  # type: ignore[no-untyped-def]
    old_cwd = os.getcwd()
    os.chdir(DASHBOARD_DIR)
    try:
        at = AppTest.from_file(str(path), default_timeout=10)
        at.run()
        return at
    finally:
        os.chdir(old_cwd)


def test_app_overview_handles_unreachable_api() -> None:
    at = _run(DASHBOARD_DIR / "app.py")
    assert not at.exception


def test_anomalies_page_handles_unreachable_api() -> None:
    at = _run(DASHBOARD_DIR / "pages" / "1_Anomalies.py")
    assert not at.exception


def test_investigation_page_without_trace_id_shows_prompt() -> None:
    at = _run(DASHBOARD_DIR / "pages" / "2_Investigation.py")
    assert not at.exception


def test_knowledge_page_handles_unreachable_api() -> None:
    at = _run(DASHBOARD_DIR / "pages" / "3_Knowledge.py")
    assert not at.exception


def test_models_page_handles_missing_reports() -> None:
    at = _run(DASHBOARD_DIR / "pages" / "4_Models.py")
    assert not at.exception
