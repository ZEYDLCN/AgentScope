from __future__ import annotations

import numpy as np
import pytest

from agentguard.anomaly.autoencoder import AutoencoderDetector


def _normal_like_data(n: int = 200, d: int = 24, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(0, 1, size=(n, d))


@pytest.mark.slow
def test_fit_and_raw_score_returns_nonnegative_reconstruction_error() -> None:
    detector = AutoencoderDetector(seed=42, max_epochs=10)
    x = _normal_like_data()
    detector.fit(x)

    scores = detector.raw_score(x)
    assert scores.shape == (200,)
    assert (scores >= 0).all()


@pytest.mark.slow
def test_out_of_distribution_sample_scores_higher() -> None:
    detector = AutoencoderDetector(seed=42, max_epochs=15)
    x = _normal_like_data(n=300)
    detector.fit(x)

    normal_sample = _normal_like_data(n=20, seed=1)
    outlier_sample = _normal_like_data(n=20, seed=2) + 10.0  # aşırı uç

    normal_scores = detector.raw_score(normal_sample)
    outlier_scores = detector.raw_score(outlier_sample)
    assert outlier_scores.mean() > normal_scores.mean()


@pytest.mark.slow
def test_fit_is_deterministic_with_same_seed() -> None:
    x = _normal_like_data()
    d1 = AutoencoderDetector(seed=42, max_epochs=8)
    d1.fit(x)
    d2 = AutoencoderDetector(seed=42, max_epochs=8)
    d2.fit(x)

    np.testing.assert_allclose(d1.raw_score(x), d2.raw_score(x), rtol=1e-4)


@pytest.mark.slow
def test_raw_score_before_fit_raises() -> None:
    detector = AutoencoderDetector()
    with pytest.raises(RuntimeError):
        detector.raw_score(_normal_like_data(n=5))


@pytest.mark.slow
def test_save_load_roundtrip(tmp_path) -> None:  # type: ignore[no-untyped-def]
    x = _normal_like_data()
    detector = AutoencoderDetector(seed=42, max_epochs=8)
    detector.fit(x)

    path = tmp_path / "autoencoder.pt"
    detector.save(path)
    loaded = AutoencoderDetector.load(path)

    np.testing.assert_allclose(detector.raw_score(x), loaded.raw_score(x))
