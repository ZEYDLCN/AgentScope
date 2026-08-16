from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentguard.config import Settings, get_settings


def test_settings_defaults() -> None:
    # AG_ENV testte conftest tarafından "test" olarak ayarlanır; burada
    # default *değer*i değil, override edilmeyen diğer alanları doğrularız.
    settings = Settings(_env_file=None)
    assert settings.env in {"dev", "test", "prod"}
    assert settings.feature_version == "v1"
    assert settings.fusion_weight_if == pytest.approx(0.5)
    assert settings.fusion_weight_ae == pytest.approx(0.5)


def test_settings_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, unknown_field="boom")  # type: ignore[call-arg]


def test_get_settings_is_cached() -> None:
    assert get_settings() is get_settings()
