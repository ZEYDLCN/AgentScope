"""Başlık-farkında (header-aware) recursive chunking — §11.3.

| Parametre | Değer |
|---|---|
| Birincil sınır | `##` başlıkları |
| Hedef boyut | 512 "token" (basit kelime-tabanlı yaklaşık sayım) |
| Maksimum | 800 |
| Örtüşme | 64 |
| Minimum | 80 (altındaki chunk bir öncekine birleştirilir) |
| Başlık enjeksiyonu | her chunk'a `"{title} > {section}\\n\\n"` öneki |
| Kod blokları | bölünmez, atomik |

Not: Gerçek bir LLM tokenizer'ı (tiktoken/HF) yerine basit kelime-tabanlı
bir yaklaşık sayım kullanılır — yerel geliştirmede ek bağımlılık/ağ
erişimi gerektirmez. Token sayıları bu nedenle yaklaşıktır; embedding
modeli entegrasyonunda (M4 devamı) gerçek tokenizer'a geçilebilir.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from agentguard.schemas.knowledge import Chunk, DocumentMeta

TARGET_TOKENS = 512
MAX_TOKENS = 800
OVERLAP_TOKENS = 64
MIN_TOKENS = 80

_FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
_HEADER_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def approx_token_count(text: str) -> int:
    """Basit kelime-tabanlı yaklaşık token sayımı (bkz. modül docstring'i)."""
    return len(text.split())


def parse_front_matter(raw_text: str) -> tuple[DocumentMeta, str]:
    match = _FRONT_MATTER_RE.match(raw_text)
    if not match:
        raise ValueError("Doküman zorunlu YAML front-matter içermiyor (--- ... ---)")
    front_matter_raw, body = match.groups()
    data = yaml.safe_load(front_matter_raw)
    # YAML, tırnaksız "1.0" gibi değerleri float olarak parse eder;
    # DocumentMeta.version bir str'dir (ör. "1.10" != 1.1 semantiği için).
    if "version" in data:
        data["version"] = str(data["version"])
    meta = DocumentMeta.model_validate(data)
    return meta, body


def _split_by_headers(body: str) -> list[tuple[str, str]]:
    """`##` başlıklarına göre böler; başlık öncesi giriş metni "Giriş" olarak tutulur."""
    matches = list(_HEADER_RE.finditer(body))
    if not matches:
        return [("Giriş", body.strip())] if body.strip() else []

    sections: list[tuple[str, str]] = []
    intro = body[: matches[0].start()].strip()
    if intro:
        sections.append(("Giriş", intro))

    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections.append((title, body[start:end].strip()))
    return sections


def _split_section_into_pieces(section_text: str) -> list[str]:
    """Kod bloklarını atomik tutarak metni hedef/max boyuta göre parçalar."""
    # Kod bloklarını geçici olarak koru (bölünmesinler)
    code_blocks = _CODE_FENCE_RE.findall(section_text)
    placeholder_text = section_text
    for i, block in enumerate(code_blocks):
        placeholder_text = placeholder_text.replace(block, f"\x00CODE{i}\x00", 1)

    paragraphs = [p for p in re.split(r"\n\s*\n", placeholder_text) if p.strip()]

    pieces: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = f"{current}\n\n{para}".strip() if current else para
        if approx_token_count(candidate) > MAX_TOKENS and current:
            pieces.append(current)
            current = para
        else:
            current = candidate
            if approx_token_count(current) >= TARGET_TOKENS:
                pieces.append(current)
                current = ""
    if current:
        pieces.append(current)

    # Kod bloklarını geri yerleştir
    restored = []
    for piece in pieces:
        for i, block in enumerate(code_blocks):
            piece = piece.replace(f"\x00CODE{i}\x00", block)
        restored.append(piece)
    return restored


def _merge_small_pieces_flat(flat: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Min boyutun altındaki parçalar, BÖLÜM SINIRINI AŞARAK bir öncekiyle
    birleştirilir (§11.3). Birleşen parça, önceki parçanın bölüm başlığını
    devralır — bu, "başlık enjeksiyonu"nun tutarlı kalmasını sağlar."""
    if not flat:
        return flat
    merged: list[tuple[str, str]] = [flat[0]]
    for section_title, piece in flat[1:]:
        if approx_token_count(piece) < MIN_TOKENS:
            prev_section, prev_piece = merged[-1]
            merged[-1] = (prev_section, f"{prev_piece}\n\n{piece}")
        else:
            merged.append((section_title, piece))
    return merged


def _apply_overlap(pieces: list[str]) -> list[str]:
    """Ardışık parçalar arasına (kelime bazlı) örtüşme ekler."""
    if len(pieces) <= 1:
        return pieces
    out = [pieces[0]]
    for i in range(1, len(pieces)):
        prev_words = pieces[i - 1].split()
        overlap = " ".join(prev_words[-OVERLAP_TOKENS:]) if prev_words else ""
        out.append(f"{overlap}\n\n{pieces[i]}".strip() if overlap else pieces[i])
    return out


def chunk_document(raw_text: str) -> list[Chunk]:
    meta, body = parse_front_matter(raw_text)
    sections = _split_by_headers(body)

    # Önce tüm dokümanı (bölüm, parça) çiftleri halinde düzleştir; minimum
    # boyut birleştirmesi BÖLÜM SINIRLARINI AŞARAK dokümanın tamamı
    # üzerinde uygulanır (§11.3: "altındaki chunk bir öncekine
    # birleştirilir" — yalnızca bölüm içi değil, doküman geneli).
    flat: list[tuple[str, str]] = []
    for section_title, section_text in sections:
        for piece in _split_section_into_pieces(section_text):
            flat.append((section_title, piece))

    merged = _merge_small_pieces_flat(flat)
    pieces_only = _apply_overlap([piece for _, piece in merged])

    chunks: list[Chunk] = []
    for index, ((section_title, _original_piece), overlapped_piece) in enumerate(
        zip(merged, pieces_only, strict=True)
    ):
        prefixed = f"{meta.title} > {section_title}\n\n{overlapped_piece}"
        chunks.append(
            Chunk(
                chunk_id=f"{meta.doc_id}#c{index}",
                doc_id=meta.doc_id,
                section=section_title,
                text=prefixed,
                token_count=approx_token_count(prefixed),
                meta=meta,
            )
        )
    return chunks


def chunk_file(path: Path) -> list[Chunk]:
    return chunk_document(path.read_text(encoding="utf-8"))


def chunk_knowledge_base(knowledge_dir: Path) -> list[Chunk]:
    """`knowledge/**.md` altındaki tüm dokümanları chunk'lar (§11.4)."""
    chunks: list[Chunk] = []
    for path in sorted(knowledge_dir.rglob("*.md")):
        chunks.extend(chunk_file(path))
    return chunks
