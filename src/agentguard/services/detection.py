"""Senkron anomali tespiti — §2.2 adım 2-4, §8.

`DetectionService`, bir trace'i özellik çıkarımından geçirip
IsolationForest (+varsa Autoencoder) füzyonu ve deterministik kurallarla
`AnomalyResult` üretir. LLM bu adımda ÇAĞRILMAZ.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import numpy as np
from numpy.typing import NDArray

from agentguard.anomaly.registry import DetectorBundle
from agentguard.anomaly.rules import RuleEvaluation, evaluate_rules
from agentguard.anomaly.scoring import fuse_scores, severity_for_score
from agentguard.features.definitions import FEATURE_ORDER
from agentguard.features.extractor import FeatureExtractor
from agentguard.features.transforms import apply_clip, apply_log1p
from agentguard.schemas.anomaly import AnomalyResult, DetectorScore, Severity
from agentguard.schemas.trace import AgentTrace

CRITICAL_RULES = frozenset({"R002_denied_access", "R005_injection_lexical"})


@dataclass
class DetectionOutcome:
    result: AnomalyResult
    raw_features: dict[str, float]
    rule_eval: RuleEvaluation


class DetectionService:
    def __init__(self, bundle: DetectorBundle, extractor: FeatureExtractor) -> None:
        self._bundle = bundle
        self._extractor = extractor
        self._clip_low = np.array(bundle.thresholds["clip_low"], dtype=np.float64)
        self._clip_high = np.array(bundle.thresholds["clip_high"], dtype=np.float64)
        self._tau = float(bundle.thresholds["tau"])

    def detect(self, trace: AgentTrace) -> DetectionOutcome:
        raw_features = self._extractor.extract_raw(trace)
        vector = np.array([[raw_features[name] for name in FEATURE_ORDER]], dtype=np.float64)
        clipped = apply_clip(apply_log1p(vector), self._clip_low, self._clip_high)
        scaled = self._bundle.scaler.transform(clipped)

        detector_scores: list[DetectorScore] = []
        normalized: dict[str, float] = {}

        if_raw = self._bundle.isolation_forest.raw_score(scaled)[0]
        if_norm = float(self._bundle.ecdf_if.normalize(np.array([if_raw]))[0])
        normalized["isolation_forest"] = if_norm
        detector_scores.append(
            DetectorScore(
                detector="isolation_forest",
                raw_score=float(if_raw),
                normalized_score=if_norm,
                model_version=self._bundle.isolation_forest.version,
            )
        )

        if self._bundle.autoencoder is not None and self._bundle.ecdf_ae is not None:
            ae_raw = self._bundle.autoencoder.raw_score(scaled)[0]
            ae_norm = float(self._bundle.ecdf_ae.normalize(np.array([ae_raw]))[0])
            normalized["autoencoder"] = ae_norm
            detector_scores.append(
                DetectorScore(
                    detector="autoencoder",
                    raw_score=float(ae_raw),
                    normalized_score=ae_norm,
                    model_version=self._bundle.autoencoder.version,
                )
            )

        rule_eval = evaluate_rules(raw_features)
        fused = fuse_scores(normalized, self._bundle.manifest.fusion_weights)
        score = max(fused, rule_eval.rule_floor)
        is_anomaly = score >= self._tau

        has_critical_rule = bool(CRITICAL_RULES.intersection(rule_eval.triggered_rules))
        severity = (
            severity_for_score(score, self._tau, has_critical_rule=has_critical_rule)
            if is_anomaly
            else Severity.LOW
        )
        if rule_eval.min_severity is not None and is_anomaly:
            severity = max(severity, rule_eval.min_severity, key=_severity_rank)

        top_features = self._top_contributing_features(scaled[0])

        result = AnomalyResult(
            trace_id=trace.trace_id,
            is_anomaly=is_anomaly,
            score=score,
            severity=severity,
            detector_scores=detector_scores,
            triggered_rules=rule_eval.triggered_rules,
            top_contributing_features=top_features,
            threshold=self._tau,
            detected_at=datetime.now(UTC),
        )
        return DetectionOutcome(result=result, raw_features=raw_features, rule_eval=rule_eval)

    def _top_contributing_features(
        self, scaled_row: NDArray[np.float64]
    ) -> list[tuple[str, float]]:
        return self._bundle.isolation_forest.top_contributing_features(
            scaled_row, FEATURE_ORDER, top_k=3
        )


_SEVERITY_ORDER = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]


def _severity_rank(s: Severity) -> int:
    return _SEVERITY_ORDER.index(s)
