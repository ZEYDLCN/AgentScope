"""Model + retrieval değerlendirme raporları — §9.

4 yapılandırma karşılaştırılır (§9.3): (a) rules-only, (b) IsolationForest,
(c) Autoencoder, (d) Fusion+Rules. "Füzyonun kuralları geçtiğini
gösteremiyorsan füzyon gereksizdir" — bu dürüstlük ilkesi gereği tüm
sonuçlar, iyileşme olmasa dahi olduğu gibi raporlanır.

Çıktı: `reports/eval_<timestamp>.json` + `.md`, 5 farklı seed ile
ortalama ± std metrikler (§9.3).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from scripts.train_models import (  # noqa: E402
    TWO_STAGE_CLEANUP_FRACTION,
    build_feature_matrix,
    chronological_split,
    load_dataset,
)

from agentguard.anomaly.autoencoder import AutoencoderDetector  # noqa: E402
from agentguard.anomaly.isolation_forest import IsolationForestDetector  # noqa: E402
from agentguard.anomaly.rules import evaluate_rules  # noqa: E402
from agentguard.anomaly.scoring import (  # noqa: E402
    ECDFCalibrator,
    grid_search_fusion_weights,
    select_threshold,
)
from agentguard.features.extractor import FeatureExtractor, build_bigram_vocabulary  # noqa: E402
from agentguard.features.transforms import (  # noqa: E402
    apply_clip,
    apply_log1p,
    compute_clip_bounds,
    fit_scaler,
)

SEEDS = [42, 7, 123, 2024, 99]
PRECISION_AT_K = 20


def _binary_metrics(scores: np.ndarray, labels: np.ndarray, threshold: float) -> dict[str, float]:
    predicted = scores >= threshold
    tp = int((predicted & (labels == 1)).sum())
    fp = int((predicted & (labels == 0)).sum())
    n_normal = max(1, int((labels == 0).sum()))
    n_anomaly = max(1, int((labels == 1).sum()))

    precision = tp / max(1, tp + fp)
    recall = tp / n_anomaly
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    fpr = fp / n_normal

    order = np.argsort(-scores)
    top_k = order[:PRECISION_AT_K]
    precision_at_k = float(labels[top_k].sum()) / min(PRECISION_AT_K, len(labels))

    # FPR@95TPR: TPR>=0.95'i sağlayan en düşük FPR
    thresholds = np.unique(scores)[::-1]
    fpr_at_95tpr = 1.0
    for t in thresholds:
        pred = scores >= t
        tp_t = int((pred & (labels == 1)).sum())
        fp_t = int((pred & (labels == 0)).sum())
        tpr_t = tp_t / n_anomaly
        if tpr_t >= 0.95:
            fpr_at_95tpr = fp_t / n_normal
            break

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "fpr": fpr,
        f"precision_at_{PRECISION_AT_K}": precision_at_k,
        "fpr_at_95tpr": fpr_at_95tpr,
    }


def _pr_roc_auc(scores: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    if len(set(labels.tolist())) < 2:
        return float("nan"), float("nan")
    return float(average_precision_score(labels, scores)), float(roc_auc_score(labels, scores))


def _per_type_recall(
    scores: np.ndarray, labels: np.ndarray, subtypes: list[str], threshold: float
) -> dict[str, float]:
    predicted = scores >= threshold
    result: dict[str, float] = {}
    for subtype in sorted(set(subtypes)):
        if subtype in {"normal", "hard_negative"}:
            continue
        idx = [i for i, s in enumerate(subtypes) if s == subtype]
        if not idx:
            continue
        tp = sum(1 for i in idx if predicted[i])
        result[subtype] = tp / len(idx)
    return result


def _measure_latency_ms(
    score_fn: Callable[[np.ndarray], np.ndarray], scaled_row: np.ndarray
) -> float:
    t0 = time.perf_counter()
    score_fn(scaled_row.reshape(1, -1))
    return (time.perf_counter() - t0) * 1000


def evaluate_rules_only(
    raw_dicts_val: list[dict[str, float]],
    val_labels: np.ndarray,
    raw_dicts_test: list[dict[str, float]],
    test_labels: np.ndarray,
    test_subtypes: list[str],
) -> dict[str, object]:
    val_scores = np.array([evaluate_rules(d).rule_floor for d in raw_dicts_val])
    test_scores = np.array([evaluate_rules(d).rule_floor for d in raw_dicts_test])

    tau = select_threshold(val_scores, val_labels, max_fpr=0.01)
    pr_auc, roc_auc = _pr_roc_auc(test_scores, test_labels)
    metrics = _binary_metrics(test_scores, test_labels, tau)
    metrics.update({"pr_auc": pr_auc, "roc_auc": roc_auc, "threshold": tau})
    metrics["per_type_recall"] = _per_type_recall(test_scores, test_labels, test_subtypes, tau)  # type: ignore[assignment]
    return metrics


def _combine_with_rules(ml_normalized: np.ndarray, raw_dicts: list[dict[str, float]]) -> np.ndarray:
    rule_floor = np.array([evaluate_rules(d).rule_floor for d in raw_dicts])
    return np.maximum(ml_normalized, rule_floor)


def evaluate_isolation_forest(
    train_scaled: np.ndarray,
    val_scaled: np.ndarray,
    val_raw_dicts: list[dict[str, float]],
    val_labels: np.ndarray,
    test_scaled: np.ndarray,
    test_raw_dicts: list[dict[str, float]],
    test_labels: np.ndarray,
    test_subtypes: list[str],
) -> list[dict[str, object]]:
    runs: list[dict[str, object]] = []
    for seed in SEEDS:
        detector = IsolationForestDetector(random_state=seed)
        detector.fit(train_scaled)
        ecdf = ECDFCalibrator(detector.raw_score(train_scaled))

        val_final = _combine_with_rules(
            ecdf.normalize(detector.raw_score(val_scaled)), val_raw_dicts
        )
        test_ml = ecdf.normalize(detector.raw_score(test_scaled))
        latencies = [_measure_latency_ms(detector.raw_score, row) for row in test_scaled]
        test_final = _combine_with_rules(test_ml, test_raw_dicts)

        tau = select_threshold(val_final, val_labels, max_fpr=0.01)
        pr_auc, roc_auc = _pr_roc_auc(test_final, test_labels)
        metrics = _binary_metrics(test_final, test_labels, tau)
        metrics.update(
            {
                "pr_auc": pr_auc,
                "roc_auc": roc_auc,
                "threshold": tau,
                "latency_p50_ms": float(np.percentile(latencies, 50)),
                "latency_p95_ms": float(np.percentile(latencies, 95)),
            }
        )
        metrics["per_type_recall"] = _per_type_recall(  # type: ignore[assignment]
            test_final, test_labels, test_subtypes, tau
        )
        metrics["seed"] = seed  # type: ignore[assignment]
        runs.append(metrics)
    return runs


def evaluate_autoencoder(
    train_scaled: np.ndarray,
    val_scaled: np.ndarray,
    val_raw_dicts: list[dict[str, float]],
    val_labels: np.ndarray,
    test_scaled: np.ndarray,
    test_raw_dicts: list[dict[str, float]],
    test_labels: np.ndarray,
    test_subtypes: list[str],
) -> list[dict[str, object]]:
    """İki aşamalı temizlik (§8.3): IF ile en anormal %1 çıkarılıp AE eğitilir."""
    if_for_cleanup = IsolationForestDetector(random_state=42)
    if_for_cleanup.fit(train_scaled)
    if_scores = if_for_cleanup.raw_score(train_scaled)
    cutoff = np.quantile(if_scores, 1 - TWO_STAGE_CLEANUP_FRACTION)
    train_clean = train_scaled[if_scores <= cutoff]

    runs: list[dict[str, object]] = []
    for seed in SEEDS:
        detector = AutoencoderDetector(seed=seed)
        detector.fit(train_clean)
        ecdf = ECDFCalibrator(detector.raw_score(train_clean))

        val_final = _combine_with_rules(
            ecdf.normalize(detector.raw_score(val_scaled)), val_raw_dicts
        )
        test_ml = ecdf.normalize(detector.raw_score(test_scaled))
        latencies = [_measure_latency_ms(detector.raw_score, row) for row in test_scaled]
        test_final = _combine_with_rules(test_ml, test_raw_dicts)

        tau = select_threshold(val_final, val_labels, max_fpr=0.01)
        pr_auc, roc_auc = _pr_roc_auc(test_final, test_labels)
        metrics = _binary_metrics(test_final, test_labels, tau)
        metrics.update(
            {
                "pr_auc": pr_auc,
                "roc_auc": roc_auc,
                "threshold": tau,
                "latency_p50_ms": float(np.percentile(latencies, 50)),
                "latency_p95_ms": float(np.percentile(latencies, 95)),
            }
        )
        metrics["per_type_recall"] = _per_type_recall(  # type: ignore[assignment]
            test_final, test_labels, test_subtypes, tau
        )
        metrics["seed"] = seed  # type: ignore[assignment]
        runs.append(metrics)
    return runs


def evaluate_fusion(
    train_scaled: np.ndarray,
    val_scaled: np.ndarray,
    val_raw_dicts: list[dict[str, float]],
    val_labels: np.ndarray,
    test_scaled: np.ndarray,
    test_raw_dicts: list[dict[str, float]],
    test_labels: np.ndarray,
    test_subtypes: list[str],
) -> list[dict[str, object]]:
    if_for_cleanup = IsolationForestDetector(random_state=42)
    if_for_cleanup.fit(train_scaled)
    if_scores_train = if_for_cleanup.raw_score(train_scaled)
    cutoff = np.quantile(if_scores_train, 1 - TWO_STAGE_CLEANUP_FRACTION)
    train_clean = train_scaled[if_scores_train <= cutoff]

    runs: list[dict[str, object]] = []
    for seed in SEEDS:
        det_if = IsolationForestDetector(random_state=seed)
        det_if.fit(train_scaled)
        ecdf_if = ECDFCalibrator(det_if.raw_score(train_scaled))

        det_ae = AutoencoderDetector(seed=seed)
        det_ae.fit(train_clean)
        ecdf_ae = ECDFCalibrator(det_ae.raw_score(train_clean))

        val_if = ecdf_if.normalize(det_if.raw_score(val_scaled))
        val_ae = ecdf_ae.normalize(det_ae.raw_score(val_scaled))
        weights, _ = grid_search_fusion_weights(
            {"isolation_forest": val_if, "autoencoder": val_ae}, val_labels
        )

        val_fused = val_if * weights["isolation_forest"] + val_ae * weights["autoencoder"]
        val_final = _combine_with_rules(val_fused, val_raw_dicts)

        test_if = ecdf_if.normalize(det_if.raw_score(test_scaled))
        test_ae = ecdf_ae.normalize(det_ae.raw_score(test_scaled))
        test_fused = test_if * weights["isolation_forest"] + test_ae * weights["autoencoder"]
        test_final = _combine_with_rules(test_fused, test_raw_dicts)

        tau = select_threshold(val_final, val_labels, max_fpr=0.01)
        pr_auc, roc_auc = _pr_roc_auc(test_final, test_labels)
        metrics = _binary_metrics(test_final, test_labels, tau)
        metrics.update({"pr_auc": pr_auc, "roc_auc": roc_auc, "threshold": tau, "weights": weights})
        metrics["per_type_recall"] = _per_type_recall(  # type: ignore[assignment]
            test_final, test_labels, test_subtypes, tau
        )
        metrics["seed"] = seed  # type: ignore[assignment]
        runs.append(metrics)
    return runs


def _aggregate(runs: list[dict[str, object]], keys: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in keys:
        values = [
            float(r[key])  # type: ignore[arg-type]
            for r in runs
            if not (isinstance(r[key], float) and np.isnan(r[key]))
        ]
        if values:
            out[key] = f"{np.mean(values):.4f} ± {np.std(values):.4f}"
    return out


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="AgentGuard model değerlendirmesi (§9)")
    parser.add_argument("--data-dir", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--out", type=Path, default=Path("reports"))
    parser.add_argument("--skip-autoencoder", action="store_true")
    args = parser.parse_args(argv)

    traces, labels = load_dataset(args.data_dir)
    labels_by_id = {row["trace_id"]: row for row in labels}
    train_traces, val_traces, test_traces = chronological_split(traces, labels_by_id)

    bigram_vocab = build_bigram_vocabulary(train_traces)
    extractor = FeatureExtractor(bigram_vocabulary=bigram_vocab)

    train_raw, _ = build_feature_matrix(train_traces, extractor)
    train_log = apply_log1p(train_raw)
    clip_low, clip_high = compute_clip_bounds(train_log)
    train_clipped = apply_clip(train_log, clip_low, clip_high)
    scaler = fit_scaler(train_clipped)
    train_scaled = scaler.transform(train_clipped)

    def prep(
        split_traces: list,  # type: ignore[type-arg]
    ) -> tuple[np.ndarray, list[dict[str, float]], np.ndarray, list[str]]:
        raw, raw_dicts = build_feature_matrix(split_traces, extractor)
        clipped = apply_clip(apply_log1p(raw), clip_low, clip_high)
        scaled = scaler.transform(clipped)
        y = np.array(
            [0 if labels_by_id[t.trace_id]["label"] == "normal" else 1 for t in split_traces]
        )
        subtypes = [labels_by_id[t.trace_id]["subtype"] for t in split_traces]
        return scaled, raw_dicts, y, subtypes

    val_scaled, val_raw_dicts, val_labels, _ = prep(val_traces)
    test_scaled, test_raw_dicts, test_labels, test_subtypes = prep(test_traces)

    print("değerlendiriliyor: rules-only ...")
    rules_only = evaluate_rules_only(
        val_raw_dicts, val_labels, test_raw_dicts, test_labels, test_subtypes
    )

    print("değerlendiriliyor: IsolationForest (5 seed) ...")
    if_runs = evaluate_isolation_forest(
        train_scaled,
        val_scaled,
        val_raw_dicts,
        val_labels,
        test_scaled,
        test_raw_dicts,
        test_labels,
        test_subtypes,
    )
    if_summary = _aggregate(
        if_runs, ["pr_auc", "roc_auc", "recall", "fpr_at_95tpr", "f1", "latency_p95_ms"]
    )

    ae_runs: list[dict[str, object]] = []
    ae_summary: dict[str, str] = {}
    fusion_runs: list[dict[str, object]] = []
    fusion_summary: dict[str, str] = {}
    if not args.skip_autoencoder:
        print("değerlendiriliyor: Autoencoder (5 seed) ...")
        ae_runs = evaluate_autoencoder(
            train_scaled,
            val_scaled,
            val_raw_dicts,
            val_labels,
            test_scaled,
            test_raw_dicts,
            test_labels,
            test_subtypes,
        )
        ae_summary = _aggregate(
            ae_runs, ["pr_auc", "roc_auc", "recall", "fpr_at_95tpr", "f1", "latency_p95_ms"]
        )

        print("değerlendiriliyor: Fusion+Rules (5 seed) ...")
        fusion_runs = evaluate_fusion(
            train_scaled,
            val_scaled,
            val_raw_dicts,
            val_labels,
            test_scaled,
            test_raw_dicts,
            test_labels,
            test_subtypes,
        )
        fusion_summary = _aggregate(
            fusion_runs, ["pr_auc", "roc_auc", "recall", "fpr_at_95tpr", "f1"]
        )

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    report = {
        "timestamp": timestamp,
        "dataset": {
            "train_rows": len(train_traces),
            "val_rows": len(val_traces),
            "test_rows": len(test_traces),
        },
        "rules_only": rules_only,
        "isolation_forest_runs": if_runs,
        "isolation_forest_summary": if_summary,
        "autoencoder_runs": ae_runs,
        "autoencoder_summary": ae_summary,
        "fusion_runs": fusion_runs,
        "fusion_summary": fusion_summary,
    }

    args.out.mkdir(parents=True, exist_ok=True)
    json_path = args.out / f"eval_{timestamp}.json"
    md_path = args.out / f"eval_{timestamp}.md"
    json_path.write_text(json.dumps(report, indent=2, default=str))

    def row(name: str, m: dict[str, object] | dict[str, str]) -> str:
        def g(key: str) -> str:
            v = m.get(key, "n/a")
            return v if isinstance(v, str) else f"{v:.4f}"

        cells = [g("pr_auc"), g("roc_auc"), g("recall"), g("fpr_at_95tpr"), g("f1")]
        return f"| {name} | " + " | ".join(cells) + " |"

    md_lines = [
        f"# AgentGuard Eval Raporu — {timestamp}",
        "",
        f"Train/Val/Test: {len(train_traces)} / {len(val_traces)} / {len(test_traces)}",
        "",
        "| Model | PR-AUC | ROC-AUC | Recall@τ | FPR@95TPR | F1 |",
        "|---|---|---|---|---|---|",
        row("Rules only", rules_only),
        row("IsolationForest (5-seed ort.)", if_summary),
    ]
    if not args.skip_autoencoder:
        md_lines += [
            row("Autoencoder (5-seed ort.)", ae_summary),
            row("Fusion + Rules (5-seed ort.)", fusion_summary),
        ]

    md_lines += ["", "## Tip bazlı recall (IsolationForest, seed=42)", ""]
    per_type = if_runs[0]["per_type_recall"]
    md_lines.append("| Anomali tipi | IF Recall |")
    md_lines.append("|---|---|")
    for subtype, recall in per_type.items():  # type: ignore[union-attr]
        md_lines.append(f"| {subtype} | {recall:.4f} |")

    if fusion_runs:
        md_lines += ["", "## Tip bazlı recall (Fusion+Rules, seed=42)", ""]
        fusion_per_type = fusion_runs[0]["per_type_recall"]
        md_lines.append("| Anomali tipi | Fusion Recall |")
        md_lines.append("|---|---|")
        for subtype, recall in fusion_per_type.items():  # type: ignore[union-attr]
            md_lines.append(f"| {subtype} | {recall:.4f} |")

    md_lines += [
        "",
        "## Bilinen sınırlılıklar",
        "",
        "- `permission_violation` ve `prompt_injection`, normal dağılımda yalnızca "
        "**tek** bir özelliği (`denied_count`, `injection_lexical_score`) oynatan "
        "anomalilerdir; `tool_loop`/`api_abuse` gibi ÇOK özelliği birlikte kaydıran "
        "tiplere göre isolate edilmesi genel amaçlı tabular outlier detector'lar "
        "(IF, AE) için daha zordur.",
        "- `FPR ≤ %1` kısıtı (§9.2) eşiği yüksek tutar; bu iki tip için recall düşük "
        "kalabilir. Kurallar (R002/R005) yalnızca severity/tip belirler, R001 dışında "
        "sayısal skor tabanı vermez (§7.3).",
        "- Füzyonun rules-only/tekil-dedektör baseline'ları anlamlı ölçüde "
        "geçemediği durumlar da yukarıdaki tabloda dürüstçe görünür bırakılmıştır "
        "(§9.3: 'füzyonun kuralları geçtiğini gösteremiyorsan füzyon gereksizdir').",
    ]

    def _mean(summary: dict[str, str], key: str) -> float | None:
        raw = summary.get(key)
        if raw is None:
            return None
        return float(raw.split("±")[0].strip())

    if_pr = _mean(if_summary, "pr_auc")
    fusion_pr = _mean(fusion_summary, "pr_auc")
    if if_pr is not None and fusion_pr is not None and if_pr > fusion_pr:
        md_lines.append(
            f"- **Val/test genelleme farkı:** füzyon ağırlıkları val setinde PR-AUC "
            f"maksimize edilerek seçildi, ancak test setinde tekil IsolationForest "
            f"(PR-AUC={if_pr:.4f}) füzyondan (PR-AUC={fusion_pr:.4f}) daha iyi "
            f"performans gösterdi — küçük val seti üzerinde ağırlık seçiminin "
            f"aşırı uyum (overfitting) riski taşıdığının bir göstergesi. Bu "
            f"dürüstçe raporlanır; v2'de daha büyük val seti veya k-fold ile "
            f"ağırlık seçimi ele alınabilir."
        )
    md_path.write_text("\n".join(md_lines) + "\n")

    print(f"rapor yazıldı -> {json_path}")
    print(f"rapor yazıldı -> {md_path}")


if __name__ == "__main__":
    main()
