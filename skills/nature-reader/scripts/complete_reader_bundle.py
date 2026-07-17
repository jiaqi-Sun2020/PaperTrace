#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Initialize and validate v3 resumable completion state for a reader bundle.

It seeds source-bound completion records and writes progress/preflight state;
it never translates, synthesizes figures, crops screenshots, or promotes a
legacy paper.md or completion ledger into a formal HTML artifact.
"""

from __future__ import annotations

import argparse
from collections import Counter
import difflib
import hashlib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from audit_reader_text import audit_text
from preflight_reader_bundle import build_preflight_manifest, write_json as write_preflight_json


ROOT = Path(__file__).resolve().parents[3]
STATE_SCRIPTS = ROOT / "skills" / "reader-skill" / "scripts"
if str(STATE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(STATE_SCRIPTS))
from completion_state import (  # noqa: E402
    PIPELINE_VERSION,
    ensure_object_inventory,
    render_progress_html,
    seed_records,
    update_run_state,
)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


ANCHOR_RE = re.compile(r'(?m)^<a\s+id=["\']([^"\']+)["\']\s*>\s*</a>\s*$')
LABEL_RE = r'(?ms)^\*\*{label}:\*\*\s*'
IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
TABLE_SEP_RE = re.compile(r'^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$', re.M)
MATH_RE = re.compile(r'(\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$\$[\s\S]*?\$\$|(?<!\\)\$(?!\s)(?:\\.|[^$]){1,800}?(?<!\\)\$)')
ALGORITHM_RE = re.compile(r'\bAlgorithm\s+\d+\b', re.I)
ALGORITHM_LINE_RE = re.compile(r'^\s*\d+\s*:', re.M)
SOURCE_BLOCK_ID_RE = re.compile(r'\b(?:S|E|C|R|F|T|A)\d+\b')

PLACEHOLDER_RE = re.compile(
    r"待忠实翻译|未生成忠实翻译|translation-required|Draft reader|reading scaffold|not a polished full translation",
    re.I,
)
RAW_FORMULA_NOISE_RE = re.compile(r"QKT\s*|cid:|e鈭|Rn脳|RT 脳|P v鈭|�")
MOJIBAKE_RE = re.compile(r"(Ã|Â|ä¸|æ|å|ðŸ|锟|閿|閳|鑴|涓枃|娉ㄩ噴|绠楁硶|鍥炬敞)")
UNSUPPORTED_GENERIC_TERMS = (
    "neutral-atom",
    "neutral atom",
    "optical tweezer",
    "QAOA",
    "MaxCut",
    "C-Z",
    "gate scheduling",
)
DRAFT_NOTES_RE = re.compile(
    r"raw source evidence extracted|completion pass must create|completion required|"
    r"translation-required|block-note-required|status\s*:\s*(?:draft|incomplete|raw)",
    re.I,
)
MIN_ORIGINAL_SIMILARITY = 0.75
MIN_PAGE_TOKEN_RECALL = 0.97
FORMULA_SOURCE_TYPES = {"equation_or_formula", "formula"}
CONTENT_AUTHOR_ROLE = "current-session-primary-model"
EXTERNAL_TRANSLATION_BACKEND = "none"
REQUIRED_DIRECT_FIELDS = {"chinese_translation", "block_specific_notes", "latex_reconstruction"}
CONTENT_AUTHORSHIP_RE = re.compile(r"(?im)^Content authorship:\s*(\S+)\s*$")
EXTERNAL_BACKEND_RE = re.compile(r"(?im)^External translation backend:\s*(\S+)\s*$")
DIRECT_FIELDS_RE = re.compile(r"(?im)^Directly authored fields:\s*([^\r\n]+)\s*$")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(payload, encoding="utf-8")
    json.loads(tmp_path.read_text(encoding="utf-8"))
    tmp_path.replace(path)


def clean_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def source_original(row: dict[str, Any]) -> str:
    return str(row.get("original") or row.get("original_text") or row.get("text") or row.get("caption_original") or row.get("caption") or "")


def normalize_evidence_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"([A-Za-z])-\s+([A-Za-z])", r"\1\2", text)
    text = re.sub(r"\\\[|\\\]|\\\(|\\\)|\$\$|\$", " ", text)
    return re.sub(r"[^\w]+", "", text, flags=re.UNICODE).lower()


def evidence_similarity(authored: str, evidence: str) -> float:
    left = normalize_evidence_text(authored)
    right = normalize_evidence_text(evidence)
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return difflib.SequenceMatcher(None, left, right, autojunk=False).ratio()


def evidence_tokens(value: Any) -> list[str]:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    text = re.sub(r"([a-z])-[\r\n]+\s*([a-z])", r"\1\2", text)
    return re.findall(r"[a-z0-9]+|[\u0370-\u03ff]+|[\u4e00-\u9fff]+", text)


def token_recall(expected: str, observed: str) -> float:
    wanted = Counter(evidence_tokens(expected))
    if not wanted:
        return 1.0
    seen = Counter(evidence_tokens(observed))
    matched = sum(min(count, seen[token]) for token, count in wanted.items())
    return matched / sum(wanted.values())


def original_readability_errors(anchor: str, original: str, source_type: str) -> list[str]:
    errors: list[str] = []
    prose_only = MATH_RE.sub(" ", original)
    lines = [line.strip() for line in prose_only.splitlines() if line.strip()]
    short_lines = [line for line in lines if len(line) <= 3]
    isolated_numbers = [line for line in lines if re.fullmatch(r"\d{1,3}", line)]
    if len(short_lines) > max(3, int(len(lines) * 0.10)):
        errors.append(f"{anchor}: Original retains excessive short PDF extraction lines")
    if len(isolated_numbers) > 2:
        errors.append(f"{anchor}: Original retains isolated page/equation-number lines")
    if source_type in FORMULA_SOURCE_TYPES and not MATH_RE.search(original):
        errors.append(f"{anchor}: equation/formula source block lacks reconstructed LaTeX in Original")
    if "[U+" in original or any(ord(char) < 32 and char not in "\n\r\t" for char in original):
        errors.append(f"{anchor}: Original retains control-character extraction artifacts")
    return errors


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def split_segments(markdown: str) -> list[dict[str, str]]:
    matches = list(ANCHOR_RE.finditer(markdown))
    rows: list[dict[str, str]] = []
    if matches and matches[0].start() > 0:
        rows.append({"anchor": "", "markdown": markdown[: matches[0].start()]})
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown)
        rows.append({"anchor": match.group(1), "markdown": markdown[match.end():end].strip()})
    if not matches:
        rows.append({"anchor": "", "markdown": markdown})
    return rows


def extract_label(text: str, label: str, next_labels: tuple[str, ...]) -> tuple[str, str]:
    start = re.search(LABEL_RE.format(label=re.escape(label)), text)
    if not start:
        return "", text
    begin = start.end()
    candidates = []
    for next_label in next_labels:
        match = re.search(LABEL_RE.format(label=re.escape(next_label)), text[begin:])
        if match:
            candidates.append(begin + match.start())
    heading = re.search(r"(?m)^\s*#{1,6}\s+", text[begin:])
    if heading:
        candidates.append(begin + heading.start())
    end = min(candidates) if candidates else len(text)
    return text[begin:end].strip(), text[end:]


def source_rows_by_id(source_map: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for key in ("blocks", "figures", "tables", "algorithms"):
        for row in source_map.get(key, []) or []:
            if isinstance(row, dict):
                rid = str(row.get("id") or row.get("block_id") or "")
                if rid:
                    rows[rid] = row
    return rows


def source_evidence_hash(row: dict[str, Any]) -> str:
    evidence = json.dumps(
        {
            "id": row.get("id") or row.get("block_id"),
            "page": row.get("page"),
            "type": row.get("type"),
            "original": row.get("original") or row.get("original_text") or row.get("text") or row.get("caption_original") or row.get("caption") or "",
            "caption_id": row.get("caption_id"),
            "image_path": row.get("image_path"),
            "bbox": row.get("bbox"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(evidence.encode("utf-8", errors="replace")).hexdigest()


def has_label(segment: str, labels: tuple[str, ...]) -> bool:
    return any(re.search(LABEL_RE.format(label=re.escape(label)), segment) for label in labels)


def build_completion_ledger(reader_dir: Path) -> tuple[dict[str, Any], list[str]]:
    source_map_path = reader_dir / "source_map.json"
    paper_md_path = reader_dir / "paper.md"
    if not source_map_path.exists():
        raise FileNotFoundError(f"missing source_map.json: {source_map_path}")
    if not paper_md_path.exists():
        raise FileNotFoundError(f"missing paper.md: {paper_md_path}")

    source_map_hash_before = sha256_file(source_map_path)
    paper_hash = sha256_file(paper_md_path)
    source_map = read_json(source_map_path)
    source_rows = source_rows_by_id(source_map)
    expected_bilingual_ids = {
        str(row.get("id") or row.get("block_id") or "")
        for row in (source_map.get("blocks", []) or [])
        if isinstance(row, dict)
        and re.fullmatch(r"(?:S|E)\d+", str(row.get("id") or row.get("block_id") or ""))
        and source_original(row).strip()
    }
    markdown = paper_md_path.read_text(encoding="utf-8")
    integrity_issues = audit_text(markdown)
    if integrity_issues:
        raise ValueError("paper.md text integrity failed: " + "; ".join(integrity_issues))
    segments = split_segments(markdown)
    segments_by_anchor = {row["anchor"]: row["markdown"] for row in segments if row.get("anchor")}
    figure_ids = {str(row.get("id") or "") for row in source_map.get("figures", []) or [] if isinstance(row, dict)}
    table_ids = {str(row.get("id") or "") for row in source_map.get("tables", []) or [] if isinstance(row, dict)}
    algorithm_ids = {str(row.get("id") or "") for row in source_map.get("algorithms", []) or [] if isinstance(row, dict)}
    issues: list[str] = []
    tasks: list[dict[str, Any]] = []
    blocks: list[dict[str, Any]] = []
    figures_tables: list[dict[str, Any]] = []
    algorithms: list[dict[str, Any]] = []
    references: list[dict[str, Any]] = []
    formulas: list[dict[str, Any]] = []
    covered_bilingual_ids: set[str] = set()
    faithful_bilingual_ids: set[str] = set()
    rendered_figure_ids: set[str] = set()
    rendered_table_ids: set[str] = set()
    rendered_algorithm_ids: set[str] = set()
    seen_anchors: set[str] = set()

    notes_path = reader_dir / "translation_notes.md"
    notes_text = ""
    author_role = ""
    external_backend = ""
    directly_authored_fields: set[str] = set()
    if not notes_path.exists():
        issues.append("translation_notes.md is missing current-session content provenance")
    else:
        notes_text = notes_path.read_text(encoding="utf-8-sig", errors="replace")
        if DRAFT_NOTES_RE.search(notes_text):
            issues.append("translation_notes.md still declares draft/incomplete completion work")
        author_match = CONTENT_AUTHORSHIP_RE.search(notes_text)
        backend_match = EXTERNAL_BACKEND_RE.search(notes_text)
        fields_match = DIRECT_FIELDS_RE.search(notes_text)
        author_role = author_match.group(1).strip() if author_match else ""
        external_backend = backend_match.group(1).strip().lower() if backend_match else ""
        if fields_match:
            directly_authored_fields = {
                field.strip().lower() for field in fields_match.group(1).split(",") if field.strip()
            }
        if author_role != CONTENT_AUTHOR_ROLE:
            issues.append(
                "translation_notes.md must declare Content authorship: current-session-primary-model"
            )
        if external_backend != EXTERNAL_TRANSLATION_BACKEND:
            issues.append("translation_notes.md must declare External translation backend: none")
        missing_direct_fields = sorted(REQUIRED_DIRECT_FIELDS - directly_authored_fields)
        if missing_direct_fields:
            issues.append(
                "translation_notes.md directly authored fields are incomplete: "
                + ", ".join(missing_direct_fields)
            )

    # Extraction may insert line breaks or multiple spaces inside a source phrase.
    # Compare normalized evidence before rejecting a source-grounded term.
    raw_evidence: list[str] = [json.dumps(source_map, ensure_ascii=False).replace("\\n", " ")]
    for raw_page in sorted((reader_dir / "raw" / "pages").glob("page-*.txt")):
        raw_evidence.append(raw_page.read_text(encoding="utf-8", errors="replace"))
    source_text = clean_space(" ".join(raw_evidence)).lower()
    markdown_text = clean_space(markdown).lower()
    unsupported_found = [term for term in UNSUPPORTED_GENERIC_TERMS if term.lower() in markdown_text and term.lower() not in source_text]
    for term in unsupported_found:
        issues.append(f"unsupported generic term appears without source evidence: {term}")

    page_coverage: list[dict[str, Any]] = []
    blocks_by_page: dict[int, list[str]] = {}
    for source_block in source_map.get("blocks", []) or []:
        if not isinstance(source_block, dict):
            continue
        try:
            page_number = int(source_block.get("page") or 0)
        except (TypeError, ValueError):
            continue
        blocks_by_page.setdefault(page_number, []).append(source_original(source_block))
    for object_key in ("figures", "tables"):
        for source_object in source_map.get(object_key, []) or []:
            if not isinstance(source_object, dict):
                continue
            try:
                page_number = int(source_object.get("page") or 0)
            except (TypeError, ValueError):
                continue
            blocks_by_page.setdefault(page_number, []).append(
                str(source_object.get("caption_original") or source_object.get("caption") or "")
            )
    raw_pages_dir = reader_dir / "raw" / "pages"
    for raw_page in sorted(raw_pages_dir.glob("page-*.txt")):
        match = re.search(r"page-(\d+)", raw_page.stem)
        if not match:
            continue
        page_number = int(match.group(1))
        expected_page = raw_page.read_text(encoding="utf-8", errors="replace")
        observed_page = "\n".join(blocks_by_page.get(page_number, []))
        recall = token_recall(expected_page, observed_page)
        page_coverage.append({"page": page_number, "token_recall": round(recall, 6)})
        if recall < MIN_PAGE_TOKEN_RECALL:
            issues.append(
                f"p.{page_number}: source_map block coverage misses raw-page evidence "
                f"(token_recall={recall:.3f}, required>={MIN_PAGE_TOKEN_RECALL:.2f})"
            )

    for row in segments:
        anchor = row["anchor"]
        segment = row["markdown"]
        if not anchor:
            continue
        if anchor in seen_anchors:
            issues.append(f"{anchor}: duplicate Markdown anchor")
        seen_anchors.add(anchor)
        source_row = source_rows.get(anchor, {})
        source, rest = extract_label(segment, "Source", ("Original", "Reference list (original only)", "中文", "Notes", "注释"))
        reference_original, _ = extract_label(rest, "Reference list (original only)", ())
        original, rest = extract_label(rest, "Original", ("中文", "Notes", "注释"))
        zh, rest = extract_label(rest, "中文", ("Notes", "注释"))
        notes, _ = extract_label(rest, "注释", ("Notes",))
        notes_en, _ = extract_label(rest, "Notes", ())
        if not notes and notes_en:
            notes = notes_en

        source_type = str(source_row.get("type") or "").lower()
        if source_type == "reference":
            if not source:
                issues.append(f"{anchor}: reference block lacks Source")
            if not reference_original:
                issues.append(f"{anchor}: reference block must use Reference list (original only)")
            if has_label(segment, ("中文",)):
                issues.append(f"{anchor}: bibliography must not have a Chinese translation field")
            source_ids = SOURCE_BLOCK_ID_RE.findall(source)
            if source_ids != [anchor]:
                issues.append(f"{anchor}: Source must name exactly its own reference block ID")
            similarity = evidence_similarity(reference_original, source_original(source_row))
            if similarity < MIN_ORIGINAL_SIMILARITY:
                issues.append(f"{anchor}: reference original does not faithfully match immutable source evidence")
            references.append({
                "block_id": anchor,
                "source_anchor": clean_space(source),
                "original": reference_original,
                "source_evidence_hash": source_evidence_hash(source_row),
                "original_similarity": round(similarity, 6),
            })
            continue

        kind = "paragraph"
        if anchor in figure_ids or anchor.startswith("F"):
            kind = "figure"
        elif anchor in table_ids or anchor.startswith("T"):
            kind = "table"
        elif anchor in algorithm_ids or anchor.startswith("A") or ALGORITHM_RE.search(segment):
            kind = "algorithm"
        elif MATH_RE.search(segment) or str(source_row.get("type") or "").lower() in {"equation_or_formula", "formula"}:
            kind = "formula"

        if (original or zh or source) and kind not in {"algorithm", "figure", "table"}:
            if not source:
                issues.append(f"{anchor}: bilingual block lacks Source")
            if not original:
                issues.append(f"{anchor}: bilingual block lacks Original")
            if not zh:
                issues.append(f"{anchor}: bilingual block lacks 中文")
            if PLACEHOLDER_RE.search(zh):
                issues.append(f"{anchor}: placeholder/draft Chinese remains")
            if RAW_FORMULA_NOISE_RE.search(original + "\n" + zh):
                issues.append(f"{anchor}: raw formula noise remains")
            if MOJIBAKE_RE.search(zh + "\n" + notes):
                issues.append(f"{anchor}: mojibake marker remains in Chinese/notes")
            if not source_row:
                issues.append(f"{anchor}: bilingual block has no matching immutable source_map row")
            source_ids = SOURCE_BLOCK_ID_RE.findall(source)
            if source_ids != [anchor]:
                issues.append(f"{anchor}: Source must name exactly its own block ID; range/merged anchors are forbidden")
            evidence_original = source_original(source_row)
            similarity = evidence_similarity(original, evidence_original)
            source_type = str(source_row.get("type") or "").lower()
            issues.extend(original_readability_errors(anchor, original, source_type))
            if kind == "formula" and not MATH_RE.search(original):
                issues.append(f"{anchor}: math-bearing bilingual block lacks reconstructed LaTeX in Original")
            if anchor in expected_bilingual_ids:
                covered_bilingual_ids.add(anchor)
                if similarity < MIN_ORIGINAL_SIMILARITY:
                    issues.append(
                        f"{anchor}: Original does not faithfully match immutable source evidence "
                        f"(similarity={similarity:.3f}, required>={MIN_ORIGINAL_SIMILARITY:.2f})"
                    )
                else:
                    faithful_bilingual_ids.add(anchor)
            block = {
                "block_id": anchor,
                "source_anchor": clean_space(source),
                "source_page": source_row.get("page"),
                "block_type": kind,
                "original": original,
                "zh": zh,
                "notes": notes,
                "source_evidence_hash": source_evidence_hash(source_row) if source_row else "",
                "source_original_sha256": sha256_text(normalize_evidence_text(evidence_original)) if evidence_original else "",
                "reader_original_sha256": sha256_text(normalize_evidence_text(original)) if original else "",
                "original_similarity": round(similarity, 6),
            }
            blocks.append(block)
            original_formulas = [match.group(0) for match in MATH_RE.finditer(original)]
            zh_formulas = [match.group(0) for match in MATH_RE.finditer(zh)]
            found_formulas = [*original_formulas, *zh_formulas]
            if found_formulas:
                formulas.append({
                    "block_id": anchor,
                    "formulas": found_formulas,
                    "original_formulas": original_formulas,
                    "zh_formulas": zh_formulas,
                    "source_evidence_hash": block["source_evidence_hash"],
                })

        if kind in {"figure", "table"}:
            expected_object_ids = figure_ids if kind == "figure" else table_ids
            if anchor not in expected_object_ids:
                issues.append(f"{anchor}: {kind} card has no matching immutable source_map object")
            card_segment = segment
            caption_id = str(source_row.get("caption_id") or "")
            if caption_id and caption_id != anchor:
                card_segment += "\n" + segments_by_anchor.get(caption_id, "")
            image_paths = [path for _alt, path in IMAGE_RE.findall(card_segment)]
            has_table = bool(TABLE_SEP_RE.search(card_segment))
            caption_en = has_label(card_segment, ("Original caption",))
            caption_zh = has_label(card_segment, ("中文图注", "中文表注", "中文 caption", "中文算法", "涓枃鍥炬敞", "涓枃琛ㄦ敞"))
            uses_source_page = any("assets/source_pages/" in path.replace("\\", "/") for path in image_paths)
            missing_assets = [
                path for path in image_paths
                if not (reader_dir / path).exists() and not re.match(r"^[a-z]+:", path, re.I)
            ]
            if kind == "figure" and not image_paths:
                issues.append(f"{anchor}: figure lacks object image")
            if kind == "table" and not (has_table or image_paths):
                issues.append(f"{anchor}: table lacks semantic table or object image")
            if uses_source_page:
                issues.append(f"{anchor}: figure/table card uses full source page image")
            if not caption_en or not caption_zh:
                issues.append(f"{anchor}: figure/table card lacks bilingual caption")
            for path in missing_assets:
                issues.append(f"{anchor}: referenced asset is missing: {path}")
            figures_tables.append({
                "block_id": anchor,
                "kind": kind,
                "image_paths": image_paths,
                "has_semantic_table": has_table,
                "has_bilingual_caption": caption_en and caption_zh,
                "source_page": source_row.get("page"),
                "source_evidence_hash": source_evidence_hash(source_row) if source_row else "",
                "status": "ok" if not any(issue.startswith(f"{anchor}:") for issue in issues) else "error",
            })
            if kind == "figure":
                rendered_figure_ids.add(anchor)
            else:
                rendered_table_ids.add(anchor)

        if kind == "algorithm":
            if not source_row:
                issues.append(f"{anchor}: algorithm card has no matching immutable source_map row")
            tex_value, algorithm_rest = extract_label(
                segment, "Algorithm LaTeX", ("Compiled algorithm", "Compile manifest", "Reading note")
            )
            asset_value, algorithm_rest = extract_label(
                algorithm_rest, "Compiled algorithm", ("Compile manifest", "Reading note")
            )
            manifest_value, _ = extract_label(algorithm_rest, "Compile manifest", ("Reading note", "注释"))
            tex_rel = tex_value.strip().strip("`")
            asset_rel = asset_value.strip().strip("`")
            manifest_rel = manifest_value.strip().strip("`")
            tex_path = reader_dir / tex_rel
            asset_path = reader_dir / asset_rel
            manifest_path = reader_dir / manifest_rel
            manifest: dict[str, Any] = {}
            if manifest_path.is_file():
                try:
                    manifest = read_json(manifest_path)
                except Exception as exc:
                    issues.append(f"{anchor}: invalid Algorithm compile manifest: {exc}")
            source_numbers = [int(value) for value in re.findall(r"(?m)^\s*(\d+)\s*:", source_original(source_row))]
            expected_steps = max(source_numbers) if source_numbers else 0
            numbered_steps = int(manifest.get("numbered_states") or 0)
            valid = (
                source_row
                and tex_path.is_file()
                and asset_path.is_file()
                and bool(manifest)
                and manifest.get("contract") == "latex-compiled-algorithm-v1"
                and manifest.get("compile_status") == "pass"
                and manifest.get("tex_sha256") == sha256_file(tex_path)
                and manifest.get("svg_sha256") == sha256_file(asset_path)
                and expected_steps >= 2
                and numbered_steps == expected_steps
            )
            if any(label in segment for label in ("**Original algorithm:**", "**中文算法:**", "**Chinese algorithm:**")):
                issues.append(f"{anchor}: legacy translated Algorithm body is forbidden; translate source comments only")
                valid = False
            if not valid:
                issues.append(
                    f"{anchor}: Algorithm must preserve all {expected_steps or 'source'} numbered steps in hash-bound compiled LaTeX"
                )
            algorithms.append({
                "block_id": anchor,
                "representation": "latex_compiled_algorithm",
                "numbered_steps": numbered_steps,
                "source_numbered_steps": expected_steps,
                "translated_comments": int(manifest.get("translated_comments") or 0),
                "latex_source_path": tex_rel,
                "latex_source_sha256": manifest.get("tex_sha256", ""),
                "compiled_asset_path": asset_rel,
                "compiled_asset_sha256": manifest.get("svg_sha256", ""),
                "compile_manifest_path": manifest_rel,
                "compile_manifest_sha256": sha256_file(manifest_path) if manifest_path.is_file() else "",
                "compile_engine": manifest.get("engine", ""),
                "source_evidence_hash": source_evidence_hash(source_row) if source_row else "",
                "status": "ok" if valid else "error",
            })
            rendered_algorithm_ids.add(anchor)

    if not blocks:
        issues.append("paper.md contains no structured bilingual blocks")
    missing_bilingual_ids = sorted(expected_bilingual_ids - covered_bilingual_ids)
    unfaithful_bilingual_ids = sorted(covered_bilingual_ids - faithful_bilingual_ids)
    if missing_bilingual_ids:
        issues.append(
            f"source coverage incomplete: missing {len(missing_bilingual_ids)} bilingual blocks: "
            + ", ".join(missing_bilingual_ids[:20])
        )
    for object_id in sorted(figure_ids - rendered_figure_ids):
        issues.append(f"{object_id}: registered figure has no rendered completion card")
    for object_id in sorted(table_ids - rendered_table_ids):
        issues.append(f"{object_id}: registered table has no rendered completion card")
    for object_id in sorted(algorithm_ids - rendered_algorithm_ids):
        issues.append(f"{object_id}: registered algorithm/pseudocode has no rendered completion card")

    preflight_manifest, preflight_issues = build_preflight_manifest(reader_dir)
    preflight_path = reader_dir / "reader_wiki" / "preflight_manifest.json"
    write_preflight_json(preflight_path, preflight_manifest)
    issues.extend(f"preflight: {issue}" for issue in preflight_issues)

    for issue in issues:
        anchor = issue.split(":", 1)[0] if ":" in issue else ""
        tasks.append({
            "anchor": anchor,
            "issue": issue,
            "required_action": "Complete or correct paper.md from source evidence; rerun completion pass.",
        })

    source_map_hash_after = sha256_file(source_map_path)
    if source_map_hash_after != source_map_hash_before:
        issues.append("source_map.json changed during completion pass")

    ledger = {
        "version": 2,
        "generator": "skills/nature-reader/scripts/complete_reader_bundle.py",
        "generated_at": utc_now(),
        "reader_dir": ".",
        "status": "pass" if not issues else "fail",
        "source_evidence": {
            "source_map_path": "source_map.json",
            "source_map_sha256": source_map_hash_before,
            "source_map_sha256_after": source_map_hash_after,
            "source_map_immutable": source_map_hash_after == source_map_hash_before,
            "paper_md_path": "paper.md",
            "paper_md_sha256": paper_hash,
            "translation_notes_path": "translation_notes.md",
            "translation_notes_sha256": sha256_file(notes_path) if notes_path.exists() else "",
            "object_inventory_path": "reader_wiki/object_inventory.json",
            "object_inventory_sha256": sha256_file(reader_dir / "reader_wiki" / "object_inventory.json") if (reader_dir / "reader_wiki" / "object_inventory.json").exists() else "",
            "preflight_manifest_path": "reader_wiki/preflight_manifest.json",
            "preflight_manifest_sha256": sha256_file(preflight_path),
            "pdf_path": (source_map.get("paper") or {}).get("source_path", ""),
        },
        "content_provenance": {
            "author_role": author_role,
            "external_translation_backend": external_backend,
            "directly_authored_fields": sorted(directly_authored_fields),
        },
        "normalized_source": {
            "segments": segments,
            "bilingual_blocks": blocks,
            "formulas": formulas,
            "figures_tables": figures_tables,
            "algorithms": algorithms,
            "references": references,
        },
        "completion_tasks": tasks,
        "source_coverage": {
            "expected_bilingual_ids": sorted(expected_bilingual_ids),
            "covered_bilingual_ids": sorted(covered_bilingual_ids),
            "faithful_bilingual_ids": sorted(faithful_bilingual_ids),
            "missing_bilingual_ids": missing_bilingual_ids,
            "unfaithful_bilingual_ids": unfaithful_bilingual_ids,
            "coverage_ratio": round(len(covered_bilingual_ids) / len(expected_bilingual_ids), 6) if expected_bilingual_ids else 1.0,
            "faithful_ratio": round(len(faithful_bilingual_ids) / len(expected_bilingual_ids), 6) if expected_bilingual_ids else 1.0,
            "raw_page_token_coverage": page_coverage,
        },
        "counts": {
            "segments": len(segments),
            "bilingual_blocks": len(blocks),
            "formulas": len(formulas),
            "figures_tables": len(figures_tables),
            "algorithms": len(algorithms),
            "references": len(references),
            "issues": len(issues),
        },
    }
    return ledger, issues


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reader_dir")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    reader_dir = Path(args.reader_dir).expanduser().resolve()
    try:
        # v3 owns completion in independently validatable records.  This gate
        # never creates a translation, invents an object card, or elevates an
        # old monolithic completion_ledger.json into formal evidence.
        seed_records(reader_dir)
        ensure_object_inventory(reader_dir)
        preflight, preflight_issues = build_preflight_manifest(reader_dir)
        wiki = reader_dir / "reader_wiki"
        write_preflight_json(wiki / "preflight_manifest.json", preflight)
        state = update_run_state(
            reader_dir,
            last_failure_gate="object preflight" if preflight_issues else "completion records",
        )
        progress = render_progress_html(reader_dir)
    except Exception as exc:
        print(f"completion pass failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "status": state["status"],
        "pipeline_version": PIPELINE_VERSION,
        "pipeline_status": "ready_for_formal_render" if state["status"] == "pass" and preflight["status"] == "pass" else "completion_required",
        "final_deliverable": "reader_interactive.html",
        "next_required_step": "Complete only pending/invalid records, then run build_formal_reader_batch.py --resume.",
        "reader_dir": str(reader_dir),
        "completion_run_state": str(wiki / "completion_run_state.json"),
        "reader_progress": str(progress),
        "preflight": {"status": preflight["status"], "issues": preflight_issues},
    }, ensure_ascii=False, indent=2))
    # Pending work is an expected, resumable state rather than a fake success.
    return 0 if state["status"] == "pass" and preflight["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
