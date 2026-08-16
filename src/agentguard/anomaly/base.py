"""Detector Protocol — §8.1.

Testlerde fake, prodda gerçek implementasyon (`IsolationForestDetector`,
M3'te `AutoencoderDetector`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class Detector(Protocol):
    name: str
    version: str

    def fit(self, X: NDArray[np.float64]) -> None: ...  # noqa: N803 — sklearn konvansiyonu
    def raw_score(self, X: NDArray[np.float64]) -> NDArray[np.float64]: ...  # noqa: N803
    def save(self, path: Path) -> None: ...
    @classmethod
    def load(cls, path: Path) -> Detector: ...
