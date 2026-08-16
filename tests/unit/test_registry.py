from __future__ import annotations

import numpy as np
import pytest

from agentguard.anomaly.autoencoder import AutoencoderDetector
from agentguard.anomaly.isolation_forest import IsolationForestDetector
from agentguard.anomaly.registry import (
    DetectorBundle,
    FeatureVersionMismatchError,
    Manifest,
)
from agentguard.anomaly.scoring import ECDFCalibrator
from agentguard.features.transforms import fit_scaler


def _bundle() -> DetectorBundle:
    rng = np.random.default_rng(0)
    x = rng.normal(size=(50, 3))

    scaler = fit_scaler(x)
    detector = IsolationForestDetector()
    detector.fit(scaler.transform(x))
    raw_scores = detector.raw_score(scaler.transform(x))

    return DetectorBundle(
        scaler=scaler,
        isolation_forest=detector,
        ecdf_if=ECDFCalibrator(raw_scores),
        bigram_vocabulary={("db.query", "api.search")},
        thresholds={"tau": 0.7},
        manifest=Manifest(feature_version="v1", git_sha="abc123", train_rows=50),
    )


def test_bundle_roundtrip_save_load(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bundle = _bundle()
    directory = tmp_path / "artifact-v1"
    bundle.save(directory)

    loaded = DetectorBundle.load(directory, expected_feature_version="v1")

    assert loaded.manifest.feature_version == "v1"
    assert loaded.manifest.train_rows == 50
    assert loaded.bigram_vocabulary == {("db.query", "api.search")}
    assert loaded.thresholds == {"tau": 0.7}

    rng = np.random.default_rng(1)
    sample = rng.normal(size=(5, 3))
    scaled = loaded.scaler.transform(sample)
    original_scores = bundle.isolation_forest.raw_score(bundle.scaler.transform(sample))
    loaded_scores = loaded.isolation_forest.raw_score(scaled)
    np.testing.assert_allclose(original_scores, loaded_scores)


def test_feature_version_mismatch_raises(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bundle = _bundle()
    directory = tmp_path / "artifact-v1"
    bundle.save(directory)

    with pytest.raises(FeatureVersionMismatchError):
        DetectorBundle.load(directory, expected_feature_version="v2")


def test_bundle_without_autoencoder_loads_with_none(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bundle = _bundle()
    directory = tmp_path / "artifact-v1"
    bundle.save(directory)

    loaded = DetectorBundle.load(directory, expected_feature_version="v1")
    assert loaded.autoencoder is None
    assert loaded.ecdf_ae is None


@pytest.mark.slow
def test_bundle_with_autoencoder_roundtrips(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bundle = _bundle()
    rng = np.random.default_rng(2)
    x = rng.normal(size=(60, 3))

    ae = AutoencoderDetector(d_in=3, seed=42, max_epochs=5)
    ae.fit(x)
    bundle.autoencoder = ae
    bundle.ecdf_ae = ECDFCalibrator(ae.raw_score(x))

    directory = tmp_path / "artifact-v1-ae"
    bundle.save(directory)

    loaded = DetectorBundle.load(directory, expected_feature_version="v1")
    assert loaded.autoencoder is not None
    assert loaded.ecdf_ae is not None
    np.testing.assert_allclose(loaded.autoencoder.raw_score(x), ae.raw_score(x))
