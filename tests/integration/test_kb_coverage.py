"""§11.2 kalite kuralı: her `AnomalyType` için en az bir failure-mode
dokümanı + bir runbook + bir olay raporu bulunmalıdır. Aksi halde o tip
için retrieval boş kalır ve LLM halüsinasyona zorlanır."""

from __future__ import annotations

from pathlib import Path

from agentguard.rag.chunking import parse_front_matter
from agentguard.schemas.anomaly import AnomalyType
from agentguard.schemas.knowledge import DocCategory

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"

# UNKNOWN bir yakalama tipi (catch-all), ayrılmış bir doküman kategorisi gerektirmez.
COVERED_TYPES = [t for t in AnomalyType if t != AnomalyType.UNKNOWN]


def _docs_by_category() -> dict[DocCategory, list[list[AnomalyType]]]:
    result: dict[DocCategory, list[list[AnomalyType]]] = {c: [] for c in DocCategory}
    for path in KNOWLEDGE_DIR.rglob("*.md"):
        meta, _ = parse_front_matter(path.read_text(encoding="utf-8"))
        result[meta.category].append(meta.anomaly_types)
    return result


def test_exactly_eighteen_documents_present() -> None:
    assert len(list(KNOWLEDGE_DIR.rglob("*.md"))) == 18


def test_every_anomaly_type_has_a_failure_mode_reference_doc() -> None:
    by_category = _docs_by_category()
    covered = {t for types in by_category[DocCategory.REFERENCE] for t in types}
    missing = [t for t in COVERED_TYPES if t not in covered]
    assert not missing, f"failure_modes/ altında eksik anomali tipleri: {missing}"


def test_every_anomaly_type_has_a_runbook() -> None:
    by_category = _docs_by_category()
    covered = {t for types in by_category[DocCategory.RUNBOOK] for t in types}
    missing = [t for t in COVERED_TYPES if t not in covered]
    assert not missing, f"runbooks/ altında eksik anomali tipleri: {missing}"


def test_every_anomaly_type_has_an_incident_report() -> None:
    by_category = _docs_by_category()
    covered = {t for types in by_category[DocCategory.INCIDENT] for t in types}
    missing = [t for t in COVERED_TYPES if t not in covered]
    assert not missing, f"incidents/ altında eksik anomali tipleri: {missing}"


def test_all_doc_ids_are_unique() -> None:
    doc_ids = []
    for path in KNOWLEDGE_DIR.rglob("*.md"):
        meta, _ = parse_front_matter(path.read_text(encoding="utf-8"))
        doc_ids.append(meta.doc_id)
    assert len(doc_ids) == len(set(doc_ids))


def test_doc_id_matches_filename_stem() -> None:
    for path in KNOWLEDGE_DIR.rglob("*.md"):
        meta, _ = parse_front_matter(path.read_text(encoding="utf-8"))
        assert meta.doc_id == path.stem, f"{path}: doc_id={meta.doc_id!r} != dosya adı"
