"""Model eğitimi — §8, §9.

Boru hattı:
  1. `data/synthetic/traces.jsonl` + `labels.jsonl` yükle
  2. Kronolojik böl: train(normal 60%) / val(normal+anomali 20%) / test(20%)
     (§9.3 — kategoriler arası zaman örtüşmesi nedeniyle etiket-grubu bazlı
     yaklaşık kronolojik böl; bkz. modül docstring'i)
  3. Train-normal'den bigram sözlüğü + clip sınırları + scaler fit et
  4. IsolationForest'i train-normal üzerinde eğit
  5. İki aşamalı temizlik: IF'in en anormal %1'i çıkarılıp Autoencoder bu
     temizlenmiş sette eğitilir (§8.3 — eğitim tuzağı: anomali sızarsa AE
     onu da iyi yeniden yapılandırmayı öğrenir ve tespit çöker)
  6. Her iki dedektör için ECDF kalibrasyonu
  7. Val setinde füzyon ağırlıkları grid search ile seçilir (PR-AUC maks., §8.4)
  8. Val setinde eşik (τ) seç: FPR<=0.01 kısıtı altında recall maksimize
  9. artifacts/<timestamp>__v1/ altına kaydet, artifacts/current symlink'i güncelle

Not (kronolojik böl sınırlılığı): `generate_synthetic.py` her anomali
kategorisini kendi `base_time`'ından başlatır; bu nedenle kategoriler
arası gerçek zaman sıralaması yoktur. Bu script, etiket grubu İÇİNDE
(normal / anomali) kronolojik sırayı korur — tam üretim ortamında gerçek
trace zaman damgaları global olarak sıralı olacağından bu sınırlama
ortadan kalkar. Bu, `reports/`'a dürüstçe not düşülür (§9.1 dürüstlük ilkesi).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agentguard.anomaly.autoencoder import AutoencoderDetector
from agentguard.anomaly.isolation_forest import IsolationForestDetector
from agentguard.anomaly.registry import DetectorBundle, Manifest
from agentguard.anomaly.rules import evaluate_rules
from agentguard.anomaly.scoring import (
    ECDFCalibrator,
    final_score,
    fuse_scores,
    grid_search_fusion_weights,
    select_threshold,
)
from agentguard.features.definitions import FEATURE_ORDER, FEATURE_VERSION
from agentguard.features.extractor import FeatureExtractor, build_bigram_vocabulary
from agentguard.features.transforms import (
    apply_clip,
    apply_log1p,
    compute_clip_bounds,
    fit_scaler,
)
from agentguard.schemas.trace import AgentTrace

TWO_STAGE_CLEANUP_FRACTION = 0.01  # IF'in en anormal %1'i AE eğitiminden çıkarılır


def load_dataset(data_dir: Path) -> tuple[list[AgentTrace], list[dict]]:  # type: ignore[type-arg]
    traces: list[AgentTrace] = []
    with (data_dir / "traces.jsonl").open() as f:
        for line in f:
            traces.append(AgentTrace.model_validate(json.loads(line)))

    labels: list[dict] = []  # type: ignore[type-arg]
    with (data_dir / "labels.jsonl").open() as f:
        for line in f:
            labels.append(json.loads(line))

    return traces, labels


def chronological_split(
    traces: list[AgentTrace],
    labels_by_id: dict[str, dict],  # type: ignore[type-arg]
) -> tuple[list[AgentTrace], list[AgentTrace], list[AgentTrace]]:
    """§9.3: train(normal 60%) / val(normal+anomali 20%) / test(20%), etiket
    grubu içinde kronolojik sıraya göre bölünür (bkz. modül docstring'i)."""
    normal = sorted(
        (t for t in traces if labels_by_id[t.trace_id]["label"] == "normal"),
        key=lambda t: t.started_at,
    )
    anomaly = sorted(
        (t for t in traces if labels_by_id[t.trace_id]["label"] == "anomaly"),
        key=lambda t: t.started_at,
    )

    n_normal_train = int(len(normal) * 0.6)
    train = normal[:n_normal_train]
    normal_rest = normal[n_normal_train:]

    n_normal_val = len(normal_rest) // 2
    n_anomaly_val = len(anomaly) // 2

    val = normal_rest[:n_normal_val] + anomaly[:n_anomaly_val]
    test = normal_rest[n_normal_val:] + anomaly[n_anomaly_val:]
    return train, val, test


def build_feature_matrix(
    traces: list[AgentTrace], extractor: FeatureExtractor
) -> tuple[np.ndarray, list[dict[str, float]]]:
    raw_dicts = [extractor.extract_raw(t) for t in traces]
    matrix = np.array([[d[name] for name in FEATURE_ORDER] for d in raw_dicts], dtype=np.float64)
    return matrix, raw_dicts


def git_sha() -> str:
    try:
        return (
            subprocess.check_output(  # noqa: S603 — sabit argüman listesi, kullanıcı girdisi yok
                ["git", "rev-parse", "HEAD"],  # noqa: S607 — PATH üzerinden git, tehlike yok
                cwd=Path(__file__).parent,
            )
            .decode()
            .strip()
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="AgentGuard model eğitimi (§8, §9)")
    parser.add_argument("--data-dir", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--artifacts-dir", type=Path, default=Path("artifacts"))
    parser.add_argument("--skip-autoencoder", action="store_true")
    args = parser.parse_args(argv)

    traces, labels = load_dataset(args.data_dir)
    labels_by_id = {label_row["trace_id"]: label_row for label_row in labels}

    train_traces, val_traces, test_traces = chronological_split(traces, labels_by_id)
    print(f"split: train={len(train_traces)} val={len(val_traces)} test={len(test_traces)}")

    bigram_vocab = build_bigram_vocabulary(train_traces)
    extractor = FeatureExtractor(bigram_vocabulary=bigram_vocab)

    train_raw, _ = build_feature_matrix(train_traces, extractor)
    train_log = apply_log1p(train_raw)
    clip_low, clip_high = compute_clip_bounds(train_log)
    train_clipped = apply_clip(train_log, clip_low, clip_high)

    scaler = fit_scaler(train_clipped)
    train_scaled = scaler.transform(train_clipped)

    detector_if = IsolationForestDetector()
    detector_if.fit(train_scaled)
    train_if_scores = detector_if.raw_score(train_scaled)
    ecdf_if = ECDFCalibrator(train_if_scores)

    detector_ae: AutoencoderDetector | None = None
    ecdf_ae: ECDFCalibrator | None = None
    if not args.skip_autoencoder:
        # İki aşamalı temizlik (§8.3): IF'in en anormal %1'i AE eğitiminden çıkarılır
        cutoff = np.quantile(train_if_scores, 1 - TWO_STAGE_CLEANUP_FRACTION)
        clean_mask = train_if_scores <= cutoff
        train_scaled_clean = train_scaled[clean_mask]
        print(
            f"iki aşamalı temizlik: {len(train_scaled) - len(train_scaled_clean)} "
            f"örnek AE eğitiminden çıkarıldı ({len(train_scaled_clean)} kaldı)"
        )

        detector_ae = AutoencoderDetector()
        detector_ae.fit(train_scaled_clean)
        train_ae_scores = detector_ae.raw_score(train_scaled_clean)
        ecdf_ae = ECDFCalibrator(train_ae_scores)

    def score_split(
        split_traces: list[AgentTrace], weights: dict[str, float]
    ) -> tuple[np.ndarray, list[dict[str, float]]]:
        raw, raw_dicts = build_feature_matrix(split_traces, extractor)
        log = apply_log1p(raw)
        clipped = apply_clip(log, clip_low, clip_high)
        scaled = scaler.transform(clipped)

        normalized: dict[str, np.ndarray] = {
            "isolation_forest": ecdf_if.normalize(detector_if.raw_score(scaled))
        }
        if detector_ae is not None and ecdf_ae is not None:
            normalized["autoencoder"] = ecdf_ae.normalize(detector_ae.raw_score(scaled))

        scores = np.zeros(len(split_traces))
        for i, raw_dict in enumerate(raw_dicts):
            rule_eval = evaluate_rules(raw_dict)
            fused = fuse_scores({k: float(v[i]) for k, v in normalized.items()}, weights)
            scores[i] = final_score(fused, rule_eval.rule_floor)
        return scores, raw_dicts

    val_labels = np.array(
        [0 if labels_by_id[t.trace_id]["label"] == "normal" else 1 for t in val_traces]
    )

    if detector_ae is not None and ecdf_ae is not None:
        val_raw, _ = build_feature_matrix(val_traces, extractor)
        val_scaled = scaler.transform(apply_clip(apply_log1p(val_raw), clip_low, clip_high))
        val_if_norm = ecdf_if.normalize(detector_if.raw_score(val_scaled))
        val_ae_norm = ecdf_ae.normalize(detector_ae.raw_score(val_scaled))
        fusion_weights, best_pr_auc = grid_search_fusion_weights(
            {"isolation_forest": val_if_norm, "autoencoder": val_ae_norm}, val_labels
        )
        print(f"füzyon ağırlıkları (grid search, val PR-AUC={best_pr_auc:.4f}): {fusion_weights}")
    else:
        fusion_weights = {"isolation_forest": 1.0}

    val_scores, _ = score_split(val_traces, fusion_weights)
    tau = select_threshold(val_scores, val_labels, max_fpr=0.01)
    print(f"selected threshold tau={tau:.4f}")

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_dir = args.artifacts_dir / f"{timestamp}__{FEATURE_VERSION}"

    bundle = DetectorBundle(
        scaler=scaler,
        isolation_forest=detector_if,
        ecdf_if=ecdf_if,
        bigram_vocabulary=bigram_vocab,
        thresholds={
            "tau": tau,
            "clip_low": clip_low.tolist(),
            "clip_high": clip_high.tolist(),
        },
        manifest=Manifest(
            feature_version=FEATURE_VERSION,
            git_sha=git_sha(),
            train_rows=len(train_traces),
            fusion_weights=fusion_weights,
            created_at=datetime.now(UTC).isoformat(),
        ),
        autoencoder=detector_ae,
        ecdf_ae=ecdf_ae,
    )
    bundle.save(out_dir)

    current_link = args.artifacts_dir / "current"
    if current_link.is_symlink() or current_link.exists():
        current_link.unlink()
    current_link.symlink_to(out_dir.name)

    print(f"artefaktlar kaydedildi -> {out_dir} (current -> {out_dir.name})")


if __name__ == "__main__":
    main()
