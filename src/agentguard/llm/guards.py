"""Çıktı doğrulama zinciri — §14.3.

```
ham metin
  → 1. JSON ayıklama (kod bloğu fence'lerini soy, ilk {...} bloğunu al)
  → 2. json.loads (başarısız → json_repair → yine başarısız → hata)
  → 3. Pydantic doğrulaması
  → 4. Grounding kontrolü: her evidence.source, [T#]/[D#] kümesinde mi?
       geçersiz atıflı maddeler DÜŞÜRÜLÜR
  → 5. min_length kontrolü: evidence boş kaldıysa confidence *= 0.5
  → 6. Otorite kontrolü: LLM severity/type dedektörle karşılaştırılır,
       NİHAİ DEĞER dedektörden alınır
  → 7. Uzunluk/temizlik: root_cause ≤ 500 karakter, kontrol karakterleri strip
  → 8. Fallback: retry'lar tükenirse şablon tabanlı deterministik rapor
```

Kullanıcıya asla ham LLM metni gösterilmez; yalnızca doğrulanmış
`Investigation` nesnesi gösterilir.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime

from json_repair import repair_json
from pydantic import ValidationError

from agentguard.llm.schema import LLMInvestigationOutput
from agentguard.schemas.anomaly import AnomalyType, Severity
from agentguard.schemas.investigation import EvidenceItem, Investigation, Recommendation

MAX_ROOT_CAUSE_LENGTH = 500
LOW_CONFIDENCE_PENALTY = 0.5
FALLBACK_CONFIDENCE = 0.3

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class OutputParseError(ValueError):
    """LLM çıktısı JSON'a ayrıştırılamadı ya da şemayı sağlamadı."""


def extract_json_block(text: str) -> str:
    """Kod bloğu fence'lerini soyar, ilk `{...}` bloğunu alır."""
    fence_match = _CODE_FENCE_RE.search(text)
    candidate = fence_match.group(1) if fence_match else text
    obj_match = _JSON_OBJECT_RE.search(candidate)
    return obj_match.group(0) if obj_match else candidate.strip()


def parse_and_validate(raw_text: str) -> LLMInvestigationOutput:
    """JSON ayıklama → parse (repair ile) → Pydantic doğrulama. Başarısızsa `OutputParseError`."""
    json_text = extract_json_block(raw_text)
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        try:
            data = json.loads(str(repair_json(json_text)))
        except (json.JSONDecodeError, TypeError) as exc:
            raise OutputParseError(f"JSON ayrıştırılamadı: {exc}") from exc

    try:
        return LLMInvestigationOutput.model_validate(data)
    except ValidationError as exc:
        raise OutputParseError(f"şema doğrulaması başarısız: {exc}") from exc


def apply_grounding(
    evidence: list[EvidenceItem], valid_tags: dict[str, str]
) -> tuple[list[EvidenceItem], int]:
    """Kaynağı `[T#]`/`[D#]` kümesinde olmayan kanıt maddeleri düşürülür."""
    kept: list[EvidenceItem] = []
    dropped = 0
    for item in evidence:
        tag_match = re.search(r"\[?([TD]\d+)\]?", item.source)
        if tag_match and tag_match.group(1) in valid_tags:
            kept.append(item)
        else:
            dropped += 1
    return kept, dropped


def apply_authority(
    llm_severity: Severity,
    llm_type: AnomalyType,
    detector_severity: Severity,
    detector_type: AnomalyType | None,
) -> bool:
    """LLM'in severity/type önerisi ile dedektör kararı karşılaştırılır.

    Döner: `disagreement` (bool). NİHAİ DEĞER her zaman dedektördendir —
    bu fonksiyon yalnızca tutarsızlığı raporlar, üzerine yazmaz (çağıran
    zaten dedektör değerlerini kullanır).
    """
    type_mismatch = detector_type is not None and llm_type != detector_type
    severity_mismatch = llm_severity != detector_severity
    return type_mismatch or severity_mismatch


def sanitize_root_cause(text: str) -> str:
    cleaned = "".join(
        ch for ch in text if not unicodedata.category(ch).startswith("C") or ch == "\n"
    )
    cleaned = _CONTROL_CHAR_RE.sub("", cleaned)
    return cleaned[:MAX_ROOT_CAUSE_LENGTH]


@dataclass
class GuardOutcome:
    investigation: Investigation
    schema_valid_first_try: bool
    grounding_dropped: int
    detector_llm_disagreement: bool
    generated_by: str  # "llm" | "fallback"


def assemble_investigation(
    *,
    llm_output: LLMInvestigationOutput,
    valid_tags: dict[str, str],
    trace_id: str,
    detector_severity: Severity,
    detector_type: AnomalyType | None,
    retrieved_doc_ids: list[str],
    model_name: str,
    prompt_version: str,
    latency_ms: int,
    schema_valid_first_try: bool,
) -> GuardOutcome:
    evidence, dropped = apply_grounding(llm_output.evidence, valid_tags)
    confidence = llm_output.confidence

    if not evidence:
        confidence *= LOW_CONFIDENCE_PENALTY
        evidence = [
            EvidenceItem(
                statement="Yeterli doğrulanabilir kanıt bulunamadı; tüm atıflar geçersizdi.",
                source="system:grounding_check",
            )
        ]

    disagreement = apply_authority(
        llm_output.severity, llm_output.anomaly_type, detector_severity, detector_type
    )

    investigation = Investigation(
        trace_id=trace_id,
        anomaly_type=detector_type or llm_output.anomaly_type,
        severity=detector_severity,  # ADR-001: nihai severity LLM'den GELMEZ
        confidence=confidence,
        root_cause=sanitize_root_cause(llm_output.root_cause),
        evidence=evidence,
        recommendations=llm_output.recommendations,
        retrieved_docs=retrieved_doc_ids,
        model_name=model_name,
        prompt_version=prompt_version,
        generated_by="llm",
        latency_ms=latency_ms,
        generated_at=datetime.now(UTC),
    )
    return GuardOutcome(
        investigation=investigation,
        schema_valid_first_try=schema_valid_first_try,
        grounding_dropped=dropped,
        detector_llm_disagreement=disagreement,
        generated_by="llm",
    )


def build_fallback_investigation(
    *,
    trace_id: str,
    detector_severity: Severity,
    detector_type: AnomalyType,
    triggered_rules: list[str],
    model_name: str,
    prompt_version: str,
    latency_ms: int,
) -> Investigation:
    """2 retry sonrası hâlâ geçersizse: kural motorundan şablon tabanlı
    deterministik rapor (§14.3.8)."""
    triggered = ", ".join(triggered_rules) or "belirlenemedi"
    return Investigation(
        trace_id=trace_id,
        anomaly_type=detector_type,
        severity=detector_severity,
        confidence=FALLBACK_CONFIDENCE,
        root_cause=(
            f"LLM soruşturma raporu üretilemedi (şema/JSON doğrulaması 2 denemede de "
            f"başarısız oldu). Tetiklenen deterministik kurallar: {triggered}. "
            f"Kök neden analizi için manuel inceleme gereklidir."
        ),
        evidence=[
            EvidenceItem(
                statement=f"Tetiklenen kural(lar): {triggered}",
                source="trace:triggered_rules",
            )
        ],
        recommendations=[
            Recommendation(
                action="Trace'i manuel olarak incele",
                priority=1,
                rationale="Otomatik soruşturma raporu üretilemedi",
            )
        ],
        retrieved_docs=[],
        model_name=model_name,
        prompt_version=prompt_version,
        generated_by="fallback",
        latency_ms=latency_ms,
        generated_at=datetime.now(UTC),
    )
