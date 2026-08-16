"""Model kayıt (registry) ve versiyonlama — §8.6.

`manifest.json`'daki `feature_version`, çalışan koddaki `FEATURE_VERSION`
ile eşleşmezse uygulama başlamamalı (fail-fast, M5'te API açılışına
bağlanacak). Sessiz özellik kayması en sinsi hata sınıfıdır.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentguard.anomaly.autoencoder import AutoencoderDetector
from agentguard.anomaly.isolation_forest import IsolationForestDetector
from agentguard.anomaly.scoring import ECDFCalibrator
from agentguard.features.transforms import StandardScaler, load_scaler, save_scaler


@dataclass
class Manifest:
    feature_version: str
    git_sha: str
    train_rows: int
    metrics: dict[str, float] = field(default_factory=dict)
    fusion_weights: dict[str, float] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "feature_version": self.feature_version,
            "git_sha": self.git_sha,
            "train_rows": self.train_rows,
            "metrics": self.metrics,
            "fusion_weights": self.fusion_weights,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Manifest:
        return cls(
            feature_version=str(data["feature_version"]),
            git_sha=str(data.get("git_sha", "")),
            train_rows=int(data.get("train_rows", 0)),
            metrics=dict(data.get("metrics", {})),
            fusion_weights=dict(data.get("fusion_weights", {})),
            created_at=str(data.get("created_at", "")),
        )


class FeatureVersionMismatchError(RuntimeError):
    """`manifest.json`'daki `feature_version`, koddaki ile uyuşmuyor."""


@dataclass
class DetectorBundle:
    scaler: StandardScaler
    isolation_forest: IsolationForestDetector
    ecdf_if: ECDFCalibrator
    bigram_vocabulary: set[tuple[str, str]]
    thresholds: dict[str, float]
    manifest: Manifest
    autoencoder: AutoencoderDetector | None = None
    ecdf_ae: ECDFCalibrator | None = None

    def save(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        save_scaler(self.scaler, directory / "scaler.joblib")
        self.isolation_forest.save(directory / "isolation_forest.joblib")
        self.ecdf_if.save(directory / "ecdf_if.npy")
        if self.autoencoder is not None:
            self.autoencoder.save(directory / "autoencoder.pt")
        if self.ecdf_ae is not None:
            self.ecdf_ae.save(directory / "ecdf_ae.npy")
        (directory / "bigrams.json").write_text(
            json.dumps([list(bg) for bg in sorted(self.bigram_vocabulary)])
        )
        (directory / "thresholds.json").write_text(json.dumps(self.thresholds, indent=2))
        (directory / "manifest.json").write_text(json.dumps(self.manifest.to_dict(), indent=2))

    @classmethod
    def load(cls, directory: Path, *, expected_feature_version: str) -> DetectorBundle:
        manifest = Manifest.from_dict(json.loads((directory / "manifest.json").read_text()))
        if manifest.feature_version != expected_feature_version:
            raise FeatureVersionMismatchError(
                f"artefakt feature_version={manifest.feature_version!r} != "
                f"kod FEATURE_VERSION={expected_feature_version!r}"
            )

        bigrams_raw: list[list[str]] = json.loads((directory / "bigrams.json").read_text())
        thresholds: dict[str, float] = json.loads((directory / "thresholds.json").read_text())

        ae_path = directory / "autoencoder.pt"
        ecdf_ae_path = directory / "ecdf_ae.npy"

        return cls(
            scaler=load_scaler(directory / "scaler.joblib"),
            isolation_forest=IsolationForestDetector.load(directory / "isolation_forest.joblib"),
            ecdf_if=ECDFCalibrator.load(directory / "ecdf_if.npy"),
            bigram_vocabulary={(bg[0], bg[1]) for bg in bigrams_raw},
            thresholds=thresholds,
            manifest=manifest,
            autoencoder=AutoencoderDetector.load(ae_path) if ae_path.exists() else None,
            ecdf_ae=ECDFCalibrator.load(ecdf_ae_path) if ecdf_ae_path.exists() else None,
        )
