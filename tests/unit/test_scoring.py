from __future__ import annotations

import numpy as np
import pytest

from agentguard.anomaly.scoring import (
    ECDFCalibrator,
    final_score,
    fuse_scores,
    grid_search_fusion_weights,
    select_threshold,
    severity_for_score,
)
from agentguard.schemas.anomaly import Severity


def test_ecdf_normalization_stays_in_unit_interval() -> None:
    train_scores = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    calibrator = ECDFCalibrator(train_scores)
    normalized = calibrator.normalize(np.array([0.0, 3.0, 100.0]))
    assert (normalized >= 0).all()
    assert (normalized <= 1).all()
    assert normalized[0] == 0.0  # 0.0, hiçbir eğitim skorunu geçmiyor
    assert normalized[2] == 1.0  # 100.0, tüm eğitim skorlarını geçiyor


def test_ecdf_roundtrip_save_load(tmp_path) -> None:  # type: ignore[no-untyped-def]
    calibrator = ECDFCalibrator(np.array([1.0, 2.0, 3.0]))
    path = tmp_path / "ecdf.npy"
    calibrator.save(path)
    loaded = ECDFCalibrator.load(path)
    np.testing.assert_array_equal(
        calibrator.normalize(np.array([2.5])), loaded.normalize(np.array([2.5]))
    )


def test_fuse_scores_normalizes_present_weights_only() -> None:
    # yalnızca isolation_forest mevcut -> ağırlığı 1.0'a normalize edilir
    result = fuse_scores({"isolation_forest": 0.8}, {"isolation_forest": 0.5, "autoencoder": 0.5})
    assert result == 0.8


def test_fuse_scores_weighted_average_when_both_present() -> None:
    result = fuse_scores(
        {"isolation_forest": 1.0, "autoencoder": 0.0},
        {"isolation_forest": 0.5, "autoencoder": 0.5},
    )
    assert result == 0.5


def test_final_score_takes_max_of_fusion_and_rule_floor() -> None:
    assert final_score(0.3, 0.85) == 0.85
    assert final_score(0.9, 0.5) == 0.9


def test_severity_for_score_bands() -> None:
    assert severity_for_score(0.5, threshold=0.6) == Severity.LOW
    assert severity_for_score(0.7, threshold=0.6) == Severity.MEDIUM
    assert severity_for_score(0.88, threshold=0.6) == Severity.HIGH
    assert severity_for_score(0.97, threshold=0.6) == Severity.CRITICAL
    assert severity_for_score(0.7, threshold=0.6, has_critical_rule=True) == Severity.CRITICAL


def test_select_threshold_respects_fpr_constraint() -> None:
    # 100 normal (skor ~N(0,1)), 20 anomali (skor ~N(3,1)) sentetik
    rng = np.random.default_rng(0)
    normal_scores = rng.normal(0, 1, 100)
    anomaly_scores = rng.normal(3, 1, 20)
    scores = np.concatenate([normal_scores, anomaly_scores])
    labels = np.concatenate([np.zeros(100), np.ones(20)])

    threshold = select_threshold(scores, labels, max_fpr=0.01)

    predicted = scores >= threshold
    fp = int((predicted & (labels == 0)).sum())
    fpr = fp / 100
    assert fpr <= 0.01 + 1e-9


def test_grid_search_single_detector_returns_full_weight() -> None:
    labels = np.array([0, 0, 1, 1])
    scores = np.array([0.1, 0.2, 0.8, 0.9])
    weights, pr_auc = grid_search_fusion_weights({"isolation_forest": scores}, labels)
    assert weights == {"isolation_forest": 1.0}
    assert pr_auc == 1.0


def test_grid_search_picks_the_better_detector() -> None:
    labels = np.array([0, 0, 0, 1, 1, 1])
    # isolation_forest mükemmel ayırır, autoencoder rastgele/gürültülü
    if_scores = np.array([0.1, 0.2, 0.3, 0.8, 0.9, 0.95])
    ae_scores = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.5])

    weights, pr_auc = grid_search_fusion_weights(
        {"isolation_forest": if_scores, "autoencoder": ae_scores}, labels, step=0.1
    )

    assert weights["isolation_forest"] > weights["autoencoder"]
    assert pr_auc == 1.0


def test_grid_search_weights_sum_to_one() -> None:
    labels = np.array([0, 0, 1, 1])
    rng = np.random.default_rng(0)
    weights, _ = grid_search_fusion_weights(
        {
            "isolation_forest": rng.uniform(size=4),
            "autoencoder": rng.uniform(size=4),
        },
        labels,
        step=0.25,
    )
    assert sum(weights.values()) == pytest.approx(1.0)
