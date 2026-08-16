from __future__ import annotations

import numpy as np

from agentguard.features.definitions import FEATURE_ORDER
from agentguard.features.transforms import (
    apply_clip,
    apply_log1p,
    compute_clip_bounds,
    fit_scaler,
    load_scaler,
    save_scaler,
)


def _zeros_matrix(rows: int = 10) -> np.ndarray:
    return np.zeros((rows, len(FEATURE_ORDER)))


def test_apply_log1p_only_transforms_log1p_columns() -> None:
    matrix = _zeros_matrix(3)
    matrix[:, FEATURE_ORDER.index("tool_call_count")] = [0, 1, np.e - 1]  # log1p sütunu
    matrix[:, FEATURE_ORDER.index("tool_diversity_ratio")] = [0.5, 0.5, 0.5]  # raw sütunu

    out = apply_log1p(matrix)

    np.testing.assert_allclose(
        out[:, FEATURE_ORDER.index("tool_call_count")], np.log1p([0, 1, np.e - 1])
    )
    np.testing.assert_allclose(out[:, FEATURE_ORDER.index("tool_diversity_ratio")], [0.5, 0.5, 0.5])


def test_compute_clip_bounds_degenerate_column_becomes_unbounded() -> None:
    matrix = _zeros_matrix(20)  # tüm sütunlar sıfır varyanslı
    low, high = compute_clip_bounds(matrix)

    assert np.all(low == -np.inf)
    assert np.all(high == np.inf)


def test_apply_clip_preserves_signal_on_degenerate_training_column() -> None:
    """Eğitimde her zaman 0 olan bir özelliğin test'teki nadir >0 değeri silinmemeli."""
    train = _zeros_matrix(20)
    low, high = compute_clip_bounds(train)

    test_row = _zeros_matrix(1)
    denied_idx = FEATURE_ORDER.index("denied_count")
    test_row[0, denied_idx] = 3.0

    clipped = apply_clip(test_row, low, high)
    assert clipped[0, denied_idx] == 3.0  # sinyal korunmalı, 0'a ezilmemeli


def test_compute_clip_bounds_normal_column_still_clips() -> None:
    matrix = _zeros_matrix(1000)
    idx = FEATURE_ORDER.index("total_tokens")
    rng = np.random.default_rng(0)
    matrix[:, idx] = rng.normal(1000, 100, size=1000)
    matrix[0, idx] = 1_000_000  # aşırı uç

    low, high = compute_clip_bounds(matrix)
    clipped = apply_clip(matrix, low, high)

    assert clipped[0, idx] < 1_000_000
    assert clipped[0, idx] == high[idx]


def test_scaler_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    rng = np.random.default_rng(0)
    matrix = rng.normal(size=(50, len(FEATURE_ORDER)))
    scaler = fit_scaler(matrix)

    path = tmp_path / "scaler.joblib"
    save_scaler(scaler, path)
    loaded = load_scaler(path)

    np.testing.assert_allclose(scaler.transform(matrix), loaded.transform(matrix))
