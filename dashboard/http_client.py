"""Dashboard'ın API istemcisi — §18: Streamlit uygulama mantığını
PAYLAŞMAZ, yalnızca REST API'yi HTTP üzerinden tüketir (ADR-006: tek
doğruluk kaynağı, ayrık dağıtım)."""

from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st

DEFAULT_API_URL = "http://localhost:8000"


@st.cache_resource
def get_client() -> httpx.Client:
    base_url = os.environ.get("AG_API_URL", DEFAULT_API_URL)
    api_key = os.environ.get("AG_API_KEY", "")
    return httpx.Client(base_url=base_url, headers={"X-API-Key": api_key}, timeout=30.0)


def api_get(path: str, **params: Any) -> dict[str, Any] | None:
    """`None` döner: API erişilemezse ya da hata dönerse (çağıran taraf
    `st.error` ile kullanıcıya gösterir)."""
    client = get_client()
    try:
        response = client.get(path, params=params)
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result
    except httpx.HTTPError as exc:
        st.error(f"API isteği başarısız: {path} — {exc}")
        return None


def api_post(path: str, json: dict[str, Any] | None = None) -> dict[str, Any] | None:
    client = get_client()
    try:
        response = client.post(path, json=json)
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result
    except httpx.HTTPError as exc:
        st.error(f"API isteği başarısız: {path} — {exc}")
        return None
