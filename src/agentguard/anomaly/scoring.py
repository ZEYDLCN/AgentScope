"""Skor normalizasyonu, füzyon ve severity haritalama — §8.4, §8.5.

İki dedektörün ham skorları farklı ölçektedir; doğrudan toplanamaz.
Kalibrasyon: eğitim (normal) dağılımının ham skorlarından ampirik CDF
çıkarılır (`ECDFCalibrator`) ve [0,1]'e normalize edilir — "normal
trafiğin yüzde kaçından daha anormal" anlamına gelir.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics import average_precision_score

from agentguard.schemas.anomaly import Severity

HIGH_THRESHOLD = 0.85
CRITICAL_THRESHOLD = 0.95


class ECDFCalibrator:
    """Eğitim dağılımından ampirik CDF; `normalized = P(raw_train <= x)`."""

    def __init__(self, sorted_train_scores: NDArray[np.float64]) -> None:
        self._sorted = np.sort(sorted_train_scores)

    def normalize(self, raw_scores: NDArray[np.float64]) -> NDArray[np.float64]:
        # searchsorted: raw_scores'un sorted train dizisindeki konumu / n
        ranks = np.searchsorted(self._sorted, raw_scores, side="right")
        result: NDArray[np.float64] = ranks / len(self._sorted)
        return result

    def save(self, path: Path) -> None:
        np.save(path, self._sorted)

    @classmethod
    def load(cls, path: Path) -> ECDFCalibrator:
        return cls(np.load(path))


def fuse_scores(normalized_scores: dict[str, float], weights: dict[str, float]) -> float:
    """Yalnızca mevcut dedektörlerin ağırlıkları normalize edilerek toplanır.

    M2'de yalnızca `isolation_forest` mevcuttur; M3'te `autoencoder` eklenince
    `weights` config'teki `fusion_weight_if`/`fusion_weight_ae` kullanılır.
    """
    present = {k: w for k, w in weights.items() if k in normalized_scores}
    total_weight = sum(present.values()) or 1.0
    return sum(normalized_scores[k] * (w / total_weight) for k, w in present.items())


def final_score(fusion_score: float, rule_floor: float) -> float:
    return max(fusion_score, rule_floor)


def grid_search_fusion_weights(
    normalized_scores_by_detector: dict[str, NDArray[np.float64]],
    labels: NDArray[np.int_],
    *,
    step: float = 0.1,
) -> tuple[dict[str, float], float]:
    """§8.4: ağırlıklar validation setinde PR-AUC'yi maksimize edecek şekilde seçilir.

    Yalnızca iki dedektör (`isolation_forest`, `autoencoder`) desteklenir;
    `w_if + w_ae = 1` kısıtı altında `step` aralıklarla taranır. Tek
    dedektör varsa (M2) ağırlık zaten (1.0,) sabittir — grid search gereksiz.
    """
    names = sorted(normalized_scores_by_detector)
    if len(names) == 1:
        return {names[0]: 1.0}, average_precision_score(
            labels, normalized_scores_by_detector[names[0]]
        )
    if len(names) != 2:
        raise ValueError("grid_search_fusion_weights yalnızca 1 veya 2 dedektörü destekler")

    a_name, b_name = names
    a_scores = normalized_scores_by_detector[a_name]
    b_scores = normalized_scores_by_detector[b_name]

    best_weights = {a_name: 0.5, b_name: 0.5}
    best_pr_auc = -1.0
    w = 0.0
    while w <= 1.0 + 1e-9:
        fused = a_scores * w + b_scores * (1 - w)
        pr_auc = float(average_precision_score(labels, fused))
        if pr_auc > best_pr_auc:
            best_pr_auc = pr_auc
            best_weights = {a_name: round(w, 4), b_name: round(1 - w, 4)}
        w += step

    return best_weights, best_pr_auc


def severity_for_score(
    score: float, threshold: float, *, has_critical_rule: bool = False
) -> Severity:
    if score < threshold:
        return Severity.LOW
    if has_critical_rule or score > CRITICAL_THRESHOLD:
        return Severity.CRITICAL
    if score >= HIGH_THRESHOLD:
        return Severity.HIGH
    return Severity.MEDIUM


def select_threshold(
    scores: NDArray[np.float64], labels: NDArray[np.int_], *, max_fpr: float = 0.01
) -> float:
    """§9.2: yalnızca validation setinde hesaplanır.

    `FPR <= max_fpr` kısıtını sağlayan eşikler arasından recall'ı
    maksimize edeni seçer. Kısıt hiçbir eşikte sağlanamazsa en düşük
    FPR'yi veren eşik döner (güvenli varsayılan).
    """
    candidates = np.unique(scores)
    normal_mask = labels == 0
    anomaly_mask = labels == 1
    n_normal = max(1, int(normal_mask.sum()))
    n_anomaly = max(1, int(anomaly_mask.sum()))

    best_threshold = float(candidates.max()) if len(candidates) else 1.0
    best_recall = -1.0
    best_fpr_fallback = (float("inf"), best_threshold)

    for t in candidates:
        predicted_anomaly = scores >= t
        fp = int((predicted_anomaly & normal_mask).sum())
        tp = int((predicted_anomaly & anomaly_mask).sum())
        fpr = fp / n_normal
        recall = tp / n_anomaly

        if fpr < best_fpr_fallback[0]:
            best_fpr_fallback = (fpr, float(t))

        if fpr <= max_fpr and recall > best_recall:
            best_recall = recall
            best_threshold = float(t)

    if best_recall < 0:
        return best_fpr_fallback[1]
    return best_threshold
