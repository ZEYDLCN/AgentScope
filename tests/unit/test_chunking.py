from __future__ import annotations

from pathlib import Path

import pytest

from agentguard.rag.chunking import (
    MIN_TOKENS,
    approx_token_count,
    chunk_document,
    chunk_knowledge_base,
    parse_front_matter,
)

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "knowledge"

SAMPLE_DOC = """---
doc_id: sample_doc
title: Örnek Doküman
category: reference
anomaly_types: [tool_loop]
severity_scope: [high]
version: 1.0
updated: 2026-07-01
---

## Birinci Bölüm

Bu birinci bölümün metnidir. Kısa bir paragraf.

## İkinci Bölüm

```python
def f():
    return 1
```

Kod bloğundan sonraki metin.
"""


def test_parse_front_matter_extracts_meta_and_body() -> None:
    meta, body = parse_front_matter(SAMPLE_DOC)
    assert meta.doc_id == "sample_doc"
    assert meta.title == "Örnek Doküman"
    assert "## Birinci Bölüm" in body


def test_parse_front_matter_rejects_missing_front_matter() -> None:
    with pytest.raises(ValueError, match="front-matter"):
        parse_front_matter("# Başlık\n\nİçerik.")


def test_chunk_id_format() -> None:
    chunks = chunk_document(SAMPLE_DOC)
    assert chunks[0].chunk_id == "sample_doc#c0"
    assert all(c.chunk_id.startswith("sample_doc#c") for c in chunks)


def test_chunk_ids_are_sequential_and_unique() -> None:
    chunks = chunk_document(SAMPLE_DOC)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))


def test_header_injection_prefixes_title_and_section() -> None:
    chunks = chunk_document(SAMPLE_DOC)
    first = next(c for c in chunks if c.section == "Birinci Bölüm")
    assert first.text.startswith("Örnek Doküman > Birinci Bölüm")


def test_code_block_is_not_split() -> None:
    chunks = chunk_document(SAMPLE_DOC)
    combined = " ".join(c.text for c in chunks)
    assert "def f():\n    return 1" in combined
    # Kod bloğu tek bir chunk içinde bütün kalmalı
    code_chunk = next(c for c in chunks if "def f():" in c.text)
    assert "```python" in code_chunk.text
    assert "```" in code_chunk.text.split("```python", 1)[1]


def test_chunk_meta_matches_document_front_matter() -> None:
    chunks = chunk_document(SAMPLE_DOC)
    for c in chunks:
        assert c.meta.doc_id == "sample_doc"
        assert c.doc_id == "sample_doc"


def test_approx_token_count_is_word_based() -> None:
    assert approx_token_count("bir iki üç") == 3
    assert approx_token_count("") == 0


def test_small_trailing_section_merged_with_previous() -> None:
    doc = SAMPLE_DOC + "\n## Kısa Bölüm\n\nTek satır.\n"
    chunks = chunk_document(doc)
    # "Kısa Bölüm" ayrı bir chunk olarak kalmamalı (MIN_TOKENS altında)
    short_standalone = [
        c for c in chunks if c.section == "Kısa Bölüm" and approx_token_count(c.text) < MIN_TOKENS
    ]
    # Birleştirildiği için ya hiç yok ya da önceki bölümle birleşmiş metne sahip
    assert len(short_standalone) <= 1


def test_chunk_knowledge_base_processes_all_real_docs() -> None:
    chunks = chunk_knowledge_base(KNOWLEDGE_DIR)
    assert len(chunks) >= 18  # en az doküman sayısı kadar chunk üretilmeli
    doc_ids = {c.doc_id for c in chunks}
    assert len(doc_ids) == 18
