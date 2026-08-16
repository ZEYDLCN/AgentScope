"""IsolationForest baseline dedektörü — §8.2.

Eğitim verisi yalnızca **normal** trace'lerdir (one-class kurulum).
Ham skor: `-clf.score_samples(X)` (yüksek = anormal).
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from numpy.typing import NDArray
from sklearn.ensemble import IsolationForest


class IsolationForestDetector:
    name = "isolation_forest"

    def __init__(self, version: str = "v1", *, random_state: int = 42) -> None:
        self.version = version
        self._model = IsolationForest(
            n_estimators=200,
            max_samples=256,  # orijinal makalenin önerisi; büyük örneklem maskeleme yapar
            contamination="auto",  # eşiği biz belirleriz, sklearn'e bırakma
            max_features=1.0,
            bootstrap=False,
            random_state=random_state,
            n_jobs=-1,
        )
        self._fitted = False

    def fit(self, x: NDArray[np.float64]) -> None:
        self._model.fit(x)
        self._fitted = True

    def raw_score(self, x: NDArray[np.float64]) -> NDArray[np.float64]:
        if not self._fitted:
            raise RuntimeError("IsolationForestDetector henüz fit edilmedi")
        scores: NDArray[np.float64] = -self._model.score_samples(x)
        return scores

    def top_contributing_features(
        self, x_row: NDArray[np.float64], feature_names: list[str], *, top_k: int = 3
    ) -> list[tuple[str, float]]:
        """Model-ajnostik "leave-one-feature-out" özellik katkısı (§8.2).

        Her özelliği medyana (0, çünkü girdi zaten standardize) sabitleyip
        skor düşüşünü ölçer.
        """
        base_score = float(-self._model.score_samples(x_row.reshape(1, -1))[0])
        contributions: list[tuple[str, float]] = []
        for i, name in enumerate(feature_names):
            perturbed = x_row.copy()
            perturbed[i] = 0.0
            perturbed_score = float(-self._model.score_samples(perturbed.reshape(1, -1))[0])
            contributions.append((name, base_score - perturbed_score))
        contributions.sort(key=lambda t: abs(t[1]), reverse=True)
        return contributions[:top_k]

    def save(self, path: Path) -> None:
        joblib.dump(self._model, path)

    @classmethod
    def load(cls, path: Path, *, version: str = "v1") -> IsolationForestDetector:
        instance = cls(version=version)
        instance._model = joblib.load(path)
        instance._fitted = True
        return instance
