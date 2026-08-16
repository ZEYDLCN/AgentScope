"""Dönüşüm yardımcıları — log1p, clipping, scaler I/O — §7.2.

`StandardScaler` yalnızca **normal** trace'lerle fit edilir ve artefakt
olarak kaydedilir; inference'ta yalnızca `transform` çağrılır.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from numpy.typing import NDArray
from sklearn.preprocessing import StandardScaler

from agentguard.features.definitions import FEATURE_ORDER, LOG1P_FEATURES

__all__ = [
    "StandardScaler",
    "apply_clip",
    "apply_log1p",
    "compute_clip_bounds",
    "fit_scaler",
    "load_scaler",
    "save_scaler",
]


def apply_log1p(raw_matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    """`FEATURE_ORDER` sırasındaki matrise, yalnızca `LOG1P_FEATURES` için log1p uygular."""
    out = raw_matrix.copy()
    for i, name in enumerate(FEATURE_ORDER):
        if name in LOG1P_FEATURES:
            out[:, i] = np.log1p(np.clip(out[:, i], a_min=0, a_max=None))
    return out


def compute_clip_bounds(
    matrix: NDArray[np.float64], *, low_pct: float = 0.5, high_pct: float = 99.5
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Eğitim setinin p0.5–p99.5 aralığı — aşırı uçlar autoencoder/IF eğitimini bozar.

    Eğitimde (normal trace'lerde) varyansı sıfır olan özellikler (ör.
    `denied_count`, `injection_lexical_score` — normal trafikte hiç
    görülmez) için `low == high == 0` çıkar; bu sütunları olduğu gibi
    kırpmak, test/inference'taki tek anomali sinyalini sıfıra ezer. Bu
    tür dejenere sütunlarda kırpma devre dışı bırakılır (±inf).
    """
    low = np.percentile(matrix, low_pct, axis=0)
    high = np.percentile(matrix, high_pct, axis=0)
    degenerate = low == high
    low = np.where(degenerate, -np.inf, low)
    high = np.where(degenerate, np.inf, high)
    return low, high


def apply_clip(
    matrix: NDArray[np.float64], low: NDArray[np.float64], high: NDArray[np.float64]
) -> NDArray[np.float64]:
    return np.clip(matrix, low, high)


def fit_scaler(matrix: NDArray[np.float64]) -> StandardScaler:
    scaler = StandardScaler()
    scaler.fit(matrix)
    return scaler


def save_scaler(scaler: StandardScaler, path: Path) -> None:
    joblib.dump(scaler, path)


def load_scaler(path: Path) -> StandardScaler:
    scaler: StandardScaler = joblib.load(path)
    return scaler
