#!/usr/bin/env python3
"""Extract immutable PDF evidence and materialize a working reader bundle.

This first, non-formal stage creates immutable source evidence plus a UTF-8-safe
``paper.md`` draft. The draft contains explicit completion markers; the active
primary model in the current user-facing session must still directly author
faithful translations, block-specific notes, and reconstructed LaTeX before
formal reader gates can run. Tools may add source-backed object evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader

from materialize_reader_markdown import materialize_reader_markdown


CAPTION_RE = re.compile(r"^(?:fig(?:ure)?\.?(?:\s|\u00a0)*\d+|table\s+[ivxlcdm\d]+)\b", re.I)
CAPTION_LINE_RE = re.compile(r"^(?:FIG(?:URE)?\.?\s*\d+|TABLE\s+[IVXLCDM\d]+)\s*[:.]", re.I)
PSEUDOCODE_RE = re.compile(r"\b(?:algorithm|procedure|pseudocode)\s*(?:\d+|:)", re.I)
REFERENCE_HEADING_RE = re.compile(r"^(?:references|bibliography)\s*$", re.I)
REFERENCE_ENTRY_RE = re.compile(r"^(?:\[\d+\]|\d+\.)\s+")
PAGE_NUMBER_RE = re.compile(r"^\s*\d+\s*$")
SPACE_RE = re.compile(r"[ \t]+")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    json.loads(temporary.read_text(encoding="utf-8"))
    temporary.replace(path)


def atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def require_executable(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise RuntimeError(f"required PDF utility is unavailable: {name}")
    return executable


def run(args: list[str]) -> None:
    completed = subprocess.run(args, text=True, encoding="utf-8", errors="replace", capture_output=True)
    if completed.returncode:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(args)}\n{completed.stderr.strip()}"
        )


def extract_reading_order_pages(pdf_path: Path, page_count: int) -> list[str]:
    """Use Poppler's raw content-stream order to avoid two-column interleaving."""
    pdftotext = require_executable("pdftotext")
    completed = subprocess.run(
        [pdftotext, "-raw", "-enc", "UTF-8", str(pdf_path), "-"],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if completed.returncode:
        raise RuntimeError(f"pdftotext -raw failed ({completed.returncode}): {completed.stderr.strip()}")
    pages = completed.stdout.replace("\r\n", "\n").split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    if len(pages) != page_count:
        raise RuntimeError(f"pdftotext returned {len(pages)} pages; expected {page_count}")
    return pages


def clean_line(value: str) -> str:
    value = value.replace("\u00ad", "")
    value = re.sub(r"([A-Za-z])-[\r\n]+\s*([A-Za-z])", r"\1\2", value)
    return SPACE_RE.sub(" ", value).strip()


def split_page_blocks(page_text: str) -> list[str]:
    paragraphs = [clean_line(part) for part in re.split(r"\n\s*\n", page_text) if clean_line(part)]
    result: list[str] = []
    for paragraph in paragraphs:
        if PAGE_NUMBER_RE.match(paragraph):
            continue
        if len(paragraph) <= 1500:
            result.append(paragraph)
            continue
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", paragraph)
        current: list[str] = []
        current_length = 0
        for sentence in sentences:
            if current and current_length + len(sentence) + 1 > 1200:
                result.append(" ".join(current))
                current = []
                current_length = 0
            current.append(sentence)
            current_length += len(sentence) + 1
        if current:
            result.append(" ".join(current))
    return result


def classify_block(text: str) -> str:
    if PSEUDOCODE_RE.search(text):
        return "algorithm"
    if CAPTION_RE.match(text):
        return "caption"
    if re.search(r"\b(?:Eq(?:uation)?\.?|where)\b", text, re.I) and any(token in text for token in ("=", "\\", "\u2211", "\u220f", "\u27e8")):
        return "equation_or_formula"
    return "paragraph"


def caption_object_kind(text: str) -> str | None:
    lowered = text.lower().strip()
    if lowered.startswith(("fig.", "fig ", "figure ")):
        return "figure"
    if lowered.startswith("table "):
        return "table"
    return None


def discover_caption_lines(page_text: str) -> list[str]:
    """Discover figure/table captions even when Poppler keeps them inside a larger text block."""
    lines = [clean_line(line) for line in page_text.splitlines()]
    captions: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not CAPTION_LINE_RE.match(line):
            index += 1
            continue
        parts = [line]
        cursor = index + 1
        while cursor < len(lines) and len(parts) < 6:
            candidate = lines[cursor]
            if not candidate or CAPTION_LINE_RE.match(candidate) or re.match(r"^(?:Appendix|[IVX]+\.|[A-Z]\.)\s", candidate):
                break
            if re.match(r"^[A-Z][A-Z\s-]{5,}$", candidate):
                break
            parts.append(candidate)
            if candidate.endswith("."):
                break
            cursor += 1
        captions.append(" ".join(parts))
        index = max(index + 1, cursor)
    return captions


def source_page_paths(reader_dir: Path, pdf_path: Path, page_count: int) -> list[dict[str, str | int]]:
    pdftocairo = require_executable("pdftocairo")
    output_dir = reader_dir / "assets" / "source_pages"
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / "render"
    run([pdftocairo, "-png", "-r", "144", str(pdf_path), str(prefix)])
    pages: list[dict[str, str | int]] = []
    for page_no in range(1, page_count + 1):
        candidates = [output_dir / f"render-{page_no}.png", output_dir / f"render-{page_no:02d}.png"]
        source = next((candidate for candidate in candidates if candidate.exists()), None)
        if source is None:
            raise RuntimeError(f"missing rendered page {page_no} after pdftocairo")
        target = output_dir / f"page-{page_no:02d}.png"
        if target.exists():
            target.unlink()
        source.replace(target)
        pages.append({
            "page": page_no,
            "source_page_image": target.relative_to(reader_dir).as_posix(),
            "sha256": sha256_file(target),
        })
    return pages


def extract_embedded_images(reader_dir: Path, pdf_path: Path) -> list[dict[str, str]]:
    pdfimages = require_executable("pdfimages")
    output_dir = reader_dir / "assets" / "image_objects"
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / "image"
    run([pdfimages, "-png", str(pdf_path), str(prefix)])
    return [
        {"path": image.relative_to(reader_dir).as_posix(), "sha256": sha256_file(image)}
        for image in sorted(output_dir.glob("*"))
        if image.is_file()
    ]


def create_source_map(pdf_path: Path, reader_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    reader = PdfReader(str(pdf_path))
    metadata = reader.metadata or {}
    page_count = len(reader.pages)
    pages = source_page_paths(reader_dir, pdf_path, page_count)
    reading_order_pages = extract_reading_order_pages(pdf_path, page_count)
    images = extract_embedded_images(reader_dir, pdf_path)
    raw_pages_dir = reader_dir / "raw" / "pages"
    blocks: list[dict[str, Any]] = []
    figures: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    algorithms: list[dict[str, Any]] = []
    captions = 0
    references = 0
    sequence = 0
    in_bibliography = False

    for page_no, text in enumerate(reading_order_pages, start=1):
        raw_path = raw_pages_dir / f"page-{page_no:02d}.txt"
        atomic_write_text(raw_path, text)
        # Some two-column PDFs omit a standalone References heading and the
        # block splitter may join the page number to the first citation.  Two
        # or more numbered entries on one page are sufficient source evidence
        # that the page is bibliography material; preserving it as ordinary
        # bilingual prose would violate the original-only reference contract.
        page_is_bibliography = bool(REFERENCE_HEADING_RE.search(text.strip())) or len(
            re.findall(r"(?m)^\s*\[\d+\]\s+", text)
        ) >= 2
        for paragraph in split_page_blocks(text):
            sequence += 1
            kind = classify_block(paragraph)
            block_id = f"S{sequence:03d}"
            if page_is_bibliography or REFERENCE_HEADING_RE.match(paragraph) or (in_bibliography and REFERENCE_ENTRY_RE.match(paragraph)):
                kind = "reference"
                references += 1
                block_id = f"R{references:03d}"
            if page_is_bibliography or REFERENCE_HEADING_RE.match(paragraph):
                in_bibliography = True
            if kind == "caption":
                captions += 1
                block_id = f"C{captions:03d}"
            block = {
                "id": block_id,
                "page": page_no,
                "type": kind,
                "order": sequence,
                "original_text": paragraph,
                "raw_page_path": raw_path.relative_to(reader_dir).as_posix(),
                "raw_page_sha256": sha256_file(raw_path),
                "source_page_image": pages[page_no - 1]["source_page_image"],
                "confidence": "extracted",
            }
            blocks.append(block)
            object_kind = caption_object_kind(paragraph) if kind == "caption" else None
            if object_kind == "figure":
                figures.append({
                    "id": f"F{len(figures) + 1:03d}",
                    "page": page_no,
                    "caption_id": block_id,
                    "caption_original": paragraph,
                    "source_page_image": pages[page_no - 1]["source_page_image"],
                    "status": "requires_object_asset",
                })
            elif object_kind == "table":
                tables.append({
                    "id": f"T{len(tables) + 1:03d}",
                    "page": page_no,
                    "caption_id": block_id,
                    "caption_original": paragraph,
                    "source_page_image": pages[page_no - 1]["source_page_image"],
                    "status": "requires_semantic_table_or_object_asset",
                })
            if kind == "algorithm":
                algorithms.append({
                    "id": f"A{len(algorithms) + 1:03d}",
                    "page": page_no,
                    "source_block_id": block_id,
                    "original_text": paragraph,
                    "status": "requires_structured_bilingual_steps",
                })

        known_captions = {str(row.get("caption_original") or "") for row in [*figures, *tables]}
        for caption in discover_caption_lines(text):
            if caption in known_captions:
                continue
            object_kind = caption_object_kind(caption)
            if object_kind == "figure":
                figures.append({
                    "id": f"F{len(figures) + 1:03d}",
                    "page": page_no,
                    "caption_id": "",
                    "caption_original": caption,
                    "source_page_image": pages[page_no - 1]["source_page_image"],
                    "status": "requires_object_asset",
                })
            elif object_kind == "table":
                tables.append({
                    "id": f"T{len(tables) + 1:03d}",
                    "page": page_no,
                    "caption_id": "",
                    "caption_original": caption,
                    "source_page_image": pages[page_no - 1]["source_page_image"],
                    "status": "requires_semantic_table_or_object_asset",
                })

    paper = {
        "title": str(getattr(metadata, "title", "") or pdf_path.stem).strip(),
        "authors": str(getattr(metadata, "author", "") or "").strip(),
        "source_type": "pdf",
        "source_path": str(pdf_path.resolve()),
        "page_count": page_count,
        "source_pdf_sha256": sha256_file(pdf_path),
        "extracted_at": utc_now(),
        "source_map_role": "immutable_raw_evidence",
    }
    source_map = {
        "version": 2,
        "paper": paper,
        "blocks": blocks,
        "pages": pages,
        "figures": figures,
        "tables": tables,
        "algorithms": algorithms,
        "assets": {"embedded_images": images},
        "object_inventory_contract": {
            "path": "reader_wiki/object_inventory.json",
            "role": "mutable derived object-asset and crop-provenance inventory",
            "source_map_remains_immutable": True,
        },
    }
    return source_map, pages


def create_bundle(pdf_path: Path, reader_dir: Path) -> dict[str, Any]:
    if reader_dir.exists():
        raise FileExistsError(f"reader directory already exists: {reader_dir}")
    reader_dir.mkdir(parents=True)
    try:
        source_map, pages = create_source_map(pdf_path, reader_dir)
        atomic_write_json(reader_dir / "source_map.json", source_map)
        manifest = {
            "version": 1,
            "created_at": utc_now(),
            "pdf": {"path": str(pdf_path.resolve()), "sha256": sha256_file(pdf_path)},
            "source_map": {"path": "source_map.json", "sha256": sha256_file(reader_dir / "source_map.json")},
            "source_pages": pages,
            "embedded_images": source_map["assets"]["embedded_images"],
            "status": "raw_evidence_ready_completion_required",
        }
        atomic_write_json(reader_dir / "raw_source_manifest.json", manifest)
        atomic_write_text(
            reader_dir / "translation_notes.md",
            "# Translation Notes\n\n"
            "Status: raw source evidence extracted and paper.md materialized. A direct Codex completion pass must "
            "replace every explicit marker with faithful Chinese, reconstructed LaTeX, and source-backed object "
            "cards before formal HTML generation.\n",
        )
        materialization = materialize_reader_markdown(reader_dir)
        return {
            "reader_dir": str(reader_dir),
            "pages": len(source_map["pages"]),
            "blocks": len(source_map["blocks"]),
            "figures": len(source_map["figures"]),
            "tables": len(source_map["tables"]),
            "algorithms": len(source_map["algorithms"]),
            "paper_md": str(reader_dir / "paper.md"),
            "status": materialization["status"],
        }
    except Exception:
        # The directory contains derived data only, but retaining it makes extraction failures inspectable.
        raise


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("reader_dir", type=Path)
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    pdf_path = args.pdf.expanduser().resolve()
    reader_dir = args.reader_dir.expanduser().resolve()
    if not pdf_path.is_file():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 2
    try:
        result = create_bundle(pdf_path, reader_dir)
    except Exception as exc:
        print(f"PDF extraction failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
