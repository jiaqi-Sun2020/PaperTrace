#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adversarial audit for a v3 ``reader_interactive.html`` artifact.

The audit deliberately treats the completion records and immutable source map
as the source of truth.  A legacy paper.md, completion ledger, or prior HTML
can never prove a current formal reader.
"""

from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
LEAN_HTML_SCRIPTS = Path(__file__).resolve().parents[2] / "utils" / "lean-html-skill" / "scripts"
if str(LEAN_HTML_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(LEAN_HTML_SCRIPTS))

from completion_state import (  # noqa: E402
    PIPELINE_VERSION,
    atomic_write_json,
    canonical_path,
    expected_records,
    load_all_records,
    read_json,
    records_dir,
    run_state_path,
    sha256_file,
    validate_record,
)
from formula_contract import atomic_formula_issues, bilingual_math_issues  # noqa: E402
from reader_html_contract import validate_generated_reader_html  # noqa: E402


REQUIRED_MARK_ATTRS = (
    "data-concept", "data-concept-id", "data-status", "data-source-anchor", "data-concept-type", "data-alias-zh", "title",
)
MATH_RE = re.compile(r'(\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$\$[\s\S]*?\$\$|(?<!\\)\$(?!\s)(?:\\.|[^$]){1,800}?(?<!\\)\$)')


def fail(message: str, issues: list[str]) -> None:
    issues.append(message)


def html_math_signatures(panel_html: str) -> list[str]:
    signatures: list[str] = []
    pattern = re.compile(
        r'<(?P<tag>div|span) class="(?P<class>math-display|math-inline)">(?P<body>[\s\S]*?)</(?P=tag)>',
        re.I,
    )
    for match in pattern.finditer(panel_html):
        body = re.sub(r"\s+", "", unescape(match.group("body")))
        if body.startswith("$$") and body.endswith("$$"):
            body = body[2:-2]
        elif (body.startswith("\\[") and body.endswith("\\]")) or (body.startswith("\\(") and body.endswith("\\)")):
            body = body[2:-2]
        elif body.startswith("$") and body.endswith("$"):
            body = body[1:-1]
        kind = "display" if match.group("class").lower() == "math-display" else "inline"
        signatures.append(f"{kind}:{body}")
    return signatures


def knowledge_marks(panel_html: str) -> list[tuple[str, str]]:
    """Return ``(concept_id, visible_text)`` for rendered concept marks."""
    marks: list[tuple[str, str]] = []
    for match in re.finditer(r'<mark\s+([^>]*)>([\s\S]*?)</mark>', panel_html, re.I):
        concept_id_match = re.search(r'data-concept-id="([^"]+)"', match.group(1), re.I)
        if not concept_id_match:
            continue
        visible_text = unescape(re.sub(r"<[^>]+>", "", match.group(2))).strip()
        marks.append((unescape(concept_id_match.group(1)), visible_text))
    return marks


def css_block(html_text: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", html_text, re.I)
    return match.group(1) if match else ""


def all_css(html_text: str) -> str:
    return "\n".join(re.findall(r"<style[^>]*>([\s\S]*?)</style>", html_text, re.I))


def css_rule(css_text: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css_text, re.I)
    return match.group(1) if match else ""


def parse_css_vars(block: str) -> dict[str, str]:
    return {name: value.lower() for name, value in re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-f]{3,6})\s*;", block, re.I)}


def hex_to_rgb(value: str) -> tuple[float, float, float] | None:
    value = value.strip().lower()
    if not re.fullmatch(r"#[0-9a-f]{3}|#[0-9a-f]{6}", value):
        return None
    if len(value) == 4:
        value = "#" + "".join(ch * 2 for ch in value[1:])
    return tuple(int(value[index:index + 2], 16) / 255 for index in (1, 3, 5))


def contrast_ratio(foreground: str, background: str) -> float:
    fg, bg = hex_to_rgb(foreground), hex_to_rgb(background)
    if fg is None or bg is None:
        return 0.0

    def luminance(rgb: tuple[float, float, float]) -> float:
        channels = [value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4 for value in rgb]
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    light, dark = max(luminance(fg), luminance(bg)), min(luminance(fg), luminance(bg))
    return (light + 0.05) / (dark + 0.05)


def validate_dark_theme_readability(html_text: str, issues: list[str]) -> dict[str, float]:
    values = parse_css_vars(css_rule(all_css(html_text), ':root[data-theme="dark"]'))
    measured: dict[str, float] = {}
    for label, fg, bg in (
        ("body", "--reader-text", "--reader-bg"),
        ("card", "--reader-text", "--reader-card-bg"),
        ("math", "--reader-text", "--reader-math-bg"),
        ("link", "--reader-link", "--reader-bg"),
    ):
        if fg not in values or bg not in values:
            fail(f"dark theme variable missing: {fg} or {bg}", issues)
            continue
        ratio = contrast_ratio(values[fg], values[bg])
        measured[label] = round(ratio, 2)
        if ratio < 4.5:
            fail(f"dark {label} contrast below 4.5:1", issues)
    return measured


def write_formal_manifest(reader_dir: Path, status: str, issues: list[str], summary: dict[str, Any]) -> None:
    wiki = reader_dir / "reader_wiki"
    artifacts: dict[str, dict[str, str]] = {}
    for label, path in (
        ("source_map", reader_dir / "source_map.json"),
        ("completion_run_state", run_state_path(reader_dir)),
        ("canonical_reader", canonical_path(reader_dir)),
        ("object_inventory", wiki / "object_inventory.json"),
        ("preflight_manifest", wiki / "preflight_manifest.json"),
        ("reader_manifest", wiki / "reader_manifest.json"),
        ("paper_summary", wiki / "paper_summary.json"),
        ("structure_validation_report", wiki / "structure_validation_report.json"),
        ("html", reader_dir / "reader_interactive.html"),
    ):
        if path.exists():
            artifacts[label] = {"path": path.relative_to(reader_dir).as_posix(), "sha256": sha256_file(path)}
    atomic_write_json(wiki / "formal_artifact_manifest.json", {
        "version": 3,
        "pipeline_version": PIPELINE_VERSION,
        "formal_status": status,
        "audit_version": 4,
        "audited_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "summary": summary,
        "issues": issues,
        "completion_blocks": {"path": "reader_wiki/completion_blocks", "count": summary.get("completion_records", 0)},
        "artifacts": artifacts,
    })


def required_file(path: Path, issues: list[str]) -> bool:
    if path.is_file():
        return True
    fail(f"missing required artifact: {path.name}", issues)
    return False


def audit(reader_dir: Path) -> tuple[list[str], dict[str, Any]]:
    reader_dir = reader_dir.resolve()
    wiki = reader_dir / "reader_wiki"
    issues: list[str] = []
    for path in (
        reader_dir / "source_map.json", reader_dir / "reader_interactive.html", run_state_path(reader_dir),
        canonical_path(reader_dir), wiki / "object_inventory.json", wiki / "preflight_manifest.json",
        wiki / "reader_manifest.json", wiki / "structure_validation_report.json",
    ):
        required_file(path, issues)
    if issues:
        return issues, {"adversarial_status": "fail", "completion_records": 0}

    source_map = read_json(reader_dir / "source_map.json")
    run_state = read_json(run_state_path(reader_dir))
    preflight = read_json(wiki / "preflight_manifest.json")
    manifest = read_json(wiki / "reader_manifest.json")
    report = read_json(wiki / "structure_validation_report.json")
    canonical = canonical_path(reader_dir).read_text(encoding="utf-8")
    html_text = (reader_dir / "reader_interactive.html").read_text(encoding="utf-8")
    source_hash = sha256_file(reader_dir / "source_map.json")
    paper_meta = source_map.get("paper") or {}
    is_fixture = "fixture" in json.dumps(paper_meta, ensure_ascii=False).lower()
    full_paper = not is_fixture and (
        int(paper_meta.get("page_count") or 0) >= 4
        or paper_meta.get("source_type") == "pdf"
        or str(paper_meta.get("source_path") or "").lower().endswith(".pdf")
    )

    if run_state.get("pipeline_version") != PIPELINE_VERSION or run_state.get("status") != "pass":
        fail("v3 completion_run_state.json is not a pass for this pipeline version", issues)
    if run_state.get("source_map_sha256") != source_hash:
        fail("completion run state is stale against immutable source_map.json", issues)
    if preflight.get("status") != "pass" or (preflight.get("source_map") or {}).get("sha256") != source_hash:
        fail("object preflight is missing, stale, or failed", issues)
    if report.get("status") != "pass":
        fail("reader-wiki structure validation is not pass", issues)

    source_of_truth = manifest.get("source_of_truth") if isinstance(manifest.get("source_of_truth"), dict) else {}
    expected_sources = {
        "canonical_reader": "reader_wiki/canonical_reader.md",
        "source_map": "source_map.json",
        "completion_run_state": "reader_wiki/completion_run_state.json",
        "completion_blocks": "reader_wiki/completion_blocks",
        "object_inventory": "reader_wiki/object_inventory.json",
        "preflight_manifest": "reader_wiki/preflight_manifest.json",
    }
    for key, value in expected_sources.items():
        if source_of_truth.get(key) != value:
            fail(f"reader_manifest source of truth is wrong for {key}", issues)
    if source_of_truth.get("source_map_sha256") != source_hash:
        fail("reader_manifest source map hash is stale", issues)
    if source_of_truth.get("canonical_reader_sha256") != sha256_file(canonical_path(reader_dir)):
        fail("reader_manifest canonical reader hash is stale", issues)
    summary_path = wiki / "paper_summary.json"
    if full_paper:
        if not summary_path.is_file():
            fail("full formal reader lacks reader_wiki/paper_summary.json", issues)
        else:
            if source_of_truth.get("paper_summary") != "reader_wiki/paper_summary.json":
                fail("reader_manifest source of truth omits paper_summary.json", issues)
            if source_of_truth.get("paper_summary_sha256") != sha256_file(summary_path):
                fail("reader_manifest paper summary hash is stale", issues)

    expected = {record["stable_id"]: record for record in expected_records(source_map)}
    try:
        records = {record["stable_id"]: record for record in load_all_records(reader_dir)}
    except (ValueError, json.JSONDecodeError) as exc:
        fail(f"completion record schema/JSON failure: {exc}", issues)
        records = {}
    exact_math_alignment_ids = {
        str(record.get("source_anchor") or "")
        for record in records.values()
        if (
            (record.get("object_metadata") or {}).get("bilingual_math_contract") == "exact-v1"
            or (record.get("object_metadata") or {}).get("source_math_inventory_required")
        )
    }
    if not records_dir(reader_dir).is_dir():
        fail("completion_blocks directory is missing", issues)
    if set(records) != set(expected):
        fail("completion records do not exactly cover immutable source blocks and objects", issues)
    for stable_id, baseline in expected.items():
        record = records.get(stable_id)
        if not record:
            continue
        for message in validate_record(record):
            fail(f"{stable_id}: {message}", issues)
        if record.get("status") != "pass":
            fail(f"{stable_id}: completion record is not pass", issues)
        if record.get("source_evidence_hash") != baseline["source_evidence_hash"]:
            fail(f"{stable_id}: source evidence hash is stale", issues)
        if record.get("source_pdf_sha256") != baseline["source_pdf_sha256"]:
            fail(f"{stable_id}: source PDF hash is stale", issues)

    figures = [record for record in records.values() if record.get("record_kind") == "figure"]
    tables = [record for record in records.values() if record.get("record_kind") == "table"]
    algorithms = [record for record in records.values() if record.get("record_kind") == "algorithm"]
    formulas = [record for record in records.values() if record.get("record_kind") == "formula"]
    references = [record for record in records.values() if record.get("record_kind") == "reference"]
    algorithm_source_ids = {
        str((record.get("object_metadata") or {}).get("source_block_id") or "")
        for record in algorithms
        if str((record.get("object_metadata") or {}).get("source_block_id") or "")
    }
    for record in figures:
        meta = record["object_metadata"]
        asset = reader_dir / str(meta.get("asset_path") or "")
        if not asset.is_file() or sha256_file(asset) != meta.get("asset_sha256"):
            fail(f"{record['stable_id']}: figure asset is absent or hash-mismatched", issues)
        if "assets/source_pages/" in str(meta.get("asset_path") or "").replace("\\", "/"):
            fail(f"{record['stable_id']}: full source page used as a figure", issues)
    for record in tables:
        meta = record["object_metadata"]
        if meta.get("representation") == "tight_crop" and not (reader_dir / str(meta.get("asset_path") or "")).is_file():
            fail(f"{record['stable_id']}: tight-crop table asset is absent", issues)
    for record in algorithms:
        meta = record["object_metadata"]
        latex_path = reader_dir / str(meta.get("latex_source_path") or "")
        svg_path = reader_dir / str(meta.get("compiled_asset_path") or "")
        manifest_path = reader_dir / str(meta.get("compile_manifest_path") or "")
        for label, path, expected_hash in (
            ("LaTeX source", latex_path, meta.get("latex_source_sha256")),
            ("compiled SVG", svg_path, meta.get("compiled_asset_sha256")),
            ("compile manifest", manifest_path, meta.get("compile_manifest_sha256")),
        ):
            if not path.is_file() or sha256_file(path) != expected_hash:
                fail(f"{record['stable_id']}: {label} is absent or hash-mismatched", issues)
        if manifest_path.is_file():
            algorithm_manifest = read_json(manifest_path)
            if algorithm_manifest.get("contract") != "latex-compiled-algorithm-v1" or algorithm_manifest.get("status") != "pass":
                fail(f"{record['stable_id']}: compile manifest does not prove a passing algorithm build", issues)
            if int(algorithm_manifest.get("numbered_states") or 0) != int(meta.get("numbered_steps") or 0):
                fail(f"{record['stable_id']}: compiled/source algorithm line counts disagree", issues)
        if latex_path.is_file():
            latex = latex_path.read_text(encoding="utf-8")
            without_comments = re.sub(r"\\Comment\{[^{}]*\}", "", latex)
            if re.search(r"[\u3400-\u9fff]", without_comments):
                fail(f"{record['stable_id']}: Chinese appears outside algorithm comments", issues)
    for record in formulas:
        if not MATH_RE.search(str(record.get("original") or "")):
            fail(f"{record['stable_id']}: Original formula is not verifiable LaTeX", issues)
    for record in records.values():
        if record.get("record_kind") != "block":
            continue
        for field, label in (("original", "Original"), ("zh", "Chinese")):
            for message in atomic_formula_issues(str(record.get(field) or ""), field=label):
                fail(f"{record['stable_id']}: {message}", issues)
        if (
            (record.get("object_metadata") or {}).get("bilingual_math_contract") == "exact-v1"
            or (record.get("object_metadata") or {}).get("source_math_inventory_required")
        ):
            for message in bilingual_math_issues(
                str(record.get("original") or ""),
                str(record.get("zh") or ""),
                block_id=str(record.get("stable_id") or "block"),
            ):
                fail(message, issues)

    zh_label = "\u4e2d\u6587"
    segments = {anchor: segment for anchor, segment in re.findall(r'(?ms)<a id="([^"]+)"></a>(.*?)(?=\n<a id="|\Z)', canonical)}
    for record in references:
        segment = segments.get(record["source_anchor"], "")
        if "**Reference list (original only):**" not in segment or f"**{zh_label}:**" in segment:
            fail(f"{record['stable_id']}: bibliography is not original-only", issues)
    if references and len(re.findall(r'<section class="reference-block"(?:\s|>)', html_text, re.I)) < len(references):
        fail("not all reference records render as single-column reference blocks", issues)
    for reference_html in re.findall(r'<section class="reference-block"[\s\S]*?</section>', html_text, re.I):
        if 'class="lang-panel translation"' in reference_html:
            fail("reference block contains a translated column", issues)
            break

    if not html_text.lstrip().lower().startswith("<!doctype html>"):
        fail("HTML is not a standalone doctype document", issues)
    if "INCOMPLETE / NOT FORMAL" in html_text:
        fail("progress HTML content leaked into formal HTML", issues)
    if 'id="MathJax-script"' not in html_text:
        fail("MathJax script is missing", issues)
    for message in validate_generated_reader_html(html_text, [], "mathjax"):
        fail(f"generated HTML contract: {message}", issues)
    if len(re.findall(r'<figure class="figure-card"', html_text, re.I)) < len(figures):
        fail("not all figure records rendered as figure cards", issues)
    if len(re.findall(r'<section class="algorithm-card"', html_text, re.I)) < len(algorithms):
        fail("not all algorithm records rendered as algorithm cards", issues)
    compiled_algorithm_cards = re.findall(
        r'<section class="algorithm-card"[^>]*data-algorithm-contract="latex-compiled-algorithm-v1"[\s\S]*?</section>',
        html_text,
        re.I,
    )
    if len(compiled_algorithm_cards) != len(algorithms):
        fail("algorithm cards do not exactly implement the compiled-LaTeX contract", issues)
    for card in compiled_algorithm_cards:
        if not re.search(
            r'<img\b[^>]+class="algorithm-render"[^>]+src="(?:[^"]+\.svg|data:image/svg\+xml[^"]*)"',
            card,
            re.I,
        ):
            fail("compiled algorithm card lacks an SVG render", issues)
        if 'class="lang-panel translation"' in card or "中文算法" in card:
            fail("compiled algorithm card contains a translated algorithm body", issues)
    if formulas and 'class="math-display"' not in html_text:
        fail("formula records exist but no display math was rendered", issues)
    concepts_path = wiki / "concept_ledger.json"
    concepts = read_json(concepts_path) if concepts_path.exists() else {}
    concepts_by_id = {
        str(item.get("concept_id")): item
        for item in concepts.get("concepts") or []
        if item.get("concept_id")
    }
    bilingual_sections = re.findall(
        r'<section class="bilingual-block[^>]*" id="([^"]+)"[^>]*>([\s\S]*?)</section>',
        html_text,
        re.I,
    )
    expected_bilingual_count = sum(
        1
        for record in records.values()
        if record.get("record_kind") == "block"
        and re.fullmatch(r"(?:S|E)\d+", str(record.get("source_anchor") or ""))
        and str(record.get("source_anchor") or "") not in algorithm_source_ids
    )
    if len(bilingual_sections) != expected_bilingual_count:
        fail(
            f"rendered bilingual block count is {len(bilingual_sections)}; expected {expected_bilingual_count}",
            issues,
        )
    original_concept_marks = 0
    chinese_concept_marks = 0
    concept_aligned_blocks = 0
    for block_id, section_html in bilingual_sections:
        original_match = re.search(r'<article class="lang-panel original">([\s\S]*?)</article>', section_html, re.I)
        translation_match = re.search(r'<article class="lang-panel translation">([\s\S]*?)</article>', section_html, re.I)
        if not original_match or not translation_match:
            fail(f"{block_id}: bilingual DOM lacks one contained Original/Chinese panel", issues)
            continue
        original_math = html_math_signatures(original_match.group(1))
        translation_math = html_math_signatures(translation_match.group(1))
        if block_id in exact_math_alignment_ids and original_math != translation_math:
            fail(
                f"{block_id}: rendered Original/Chinese formula components are not one-to-one aligned "
                f"(Original={original_math}, Chinese={translation_math})",
                issues,
            )
        original_marks = knowledge_marks(original_match.group(1))
        chinese_marks = knowledge_marks(translation_match.group(1))
        original_concept_marks += len(original_marks)
        chinese_concept_marks += len(chinese_marks)
        original_ids = {concept_id for concept_id, _text in original_marks}
        chinese_ids = {concept_id for concept_id, _text in chinese_marks}
        if original_ids != chinese_ids:
            fail(
                f"{block_id}: rendered Original/Chinese concept IDs are not aligned "
                f"(Original={sorted(original_ids)}, Chinese={sorted(chinese_ids)})",
                issues,
            )
        else:
            concept_aligned_blocks += 1
        for concept_id, visible_text in chinese_marks:
            concept = concepts_by_id.get(concept_id, {})
            aliases_zh = {str(alias).strip().casefold() for alias in concept.get("aliases_zh") or [] if str(alias).strip()}
            if visible_text.casefold() not in aliases_zh:
                fail(
                    f"{block_id}: Chinese concept mark {concept_id!r} uses uncontrolled text {visible_text!r}",
                    issues,
                )
    if algorithms and 'class="alg-line-no"' in html_text:
        fail("legacy line-list algorithm rendering remains in formal HTML", issues)
    if re.search(r'<figure\s+class="figure-card"[\s\S]*?assets/source_pages/[\s\S]*?</figure>', html_text, re.I):
        fail("HTML figure card directly uses a full source-page image", issues)
    figure_css = css_block(html_text, ".figure-card img")
    if re.search(r"object-fit\s*:\s*cover|height\s*:\s*(?!\s*auto\b)[^;]+", figure_css, re.I):
        fail("figure-card CSS can crop or fix-height source object imagery", issues)

    for token in ("function closePanel()", "downloadFeedback", "copyFeedback", "readerFeedbackSeed", 'id="readerThemeSelect"', "paper.reader.theme"):
        if token not in html_text:
            fail(f"formal interaction contract is missing: {token}", issues)
    marks = re.findall(r'<mark\s+class="knowledge-gap\b[^>]*>', html_text)
    if full_paper and (len(concepts.get("concepts") or []) < 30 or not marks):
        fail("full formal reader lacks grounded concepts or rendered knowledge marks", issues)
    for mark in marks:
        for attr in REQUIRED_MARK_ATTRS:
            if f"{attr}=" not in mark:
                fail(f"knowledge mark is missing {attr}", issues)
                break
    knowledge_panel_match = re.search(
        r'<section class="knowledge-panel" id="personal-knowledge-boundary">([\s\S]*?)</section>',
        html_text,
        re.I,
    )
    if not knowledge_panel_match:
        fail("Paper Concept Ledger / Personal Knowledge Boundary panel is missing", issues)
    else:
        knowledge_panel = knowledge_panel_match.group(1)
        required_panel_text = (
            "Paper Concept Ledger / Personal Knowledge Boundary",
            "Concept",
            "Personal Status",
            "Chinese Name",
            "Type",
            "Role in This Paper",
            "Personal knowledge profile:",
        )
        for token in required_panel_text:
            if token not in knowledge_panel:
                fail(f"knowledge panel is missing required English interface text: {token}", issues)
        for enum_token in (
            "figure_element",
            "formula_variable",
            "math_object",
            "method_component",
            "model_module",
        ):
            if re.search(rf">\s*{re.escape(enum_token)}\s*<", knowledge_panel):
                fail(f"knowledge panel exposes internal concept type enum: {enum_token}", issues)

    manifest_summary = manifest.get("paper_summary") if isinstance(manifest.get("paper_summary"), dict) else {}
    summary_items = 0
    if full_paper:
        for token in (
            'class="paper-summary" id="paper-summary"',
            "Paper Summary / 论文总结",
            "What the Paper Does / 做了什么",
            "How It Works / 怎么做的",
            "Why It Matters / 有什么意义",
            "Evidence, Scope, and Limitations / 证据、范围与局限",
        ):
            if token not in html_text:
                fail(f"formal reader summary is missing required rendered section: {token}", issues)
        valid_source_anchors = {record.get("source_anchor") for record in records.values() if record.get("source_anchor")}
        entries = []
        if isinstance(manifest_summary.get("overview"), dict):
            entries.append(manifest_summary["overview"])
        for key in ("what_it_does", "how_it_works", "why_it_matters", "evidence_and_limitations"):
            entries.extend(item for item in (manifest_summary.get(key) or []) if isinstance(item, dict))
        summary_items = len(entries)
        for index, entry in enumerate(entries, start=1):
            source_text = str(entry.get("text") or "").strip()
            rendered_components = [
                html.escape(component.strip())
                for component in MATH_RE.split(source_text)
                if component.strip()
            ]
            if not rendered_components or any(component not in html_text for component in rendered_components):
                fail(f"paper summary entry {index} is absent from rendered HTML", issues)
            for anchor in entry.get("source_anchors") or []:
                anchor_text = str(anchor)
                if anchor_text not in valid_source_anchors:
                    fail(f"paper summary entry {index} cites unknown completion anchor {anchor_text!r}", issues)
                if f'href="#{html.escape(anchor_text, quote=True)}"' not in html_text:
                    fail(f"paper summary entry {index} lacks rendered source link for {anchor_text}", issues)

    source_pages = source_map.get("pages") if isinstance(source_map.get("pages"), list) else []
    rendered_source_pages = []
    source_data_match = re.search(
        r'<script id="readerSourcePages" type="application/json">([\s\S]*?)</script>',
        html_text,
        re.I,
    )
    if source_data_match:
        try:
            rendered_source_pages = json.loads(source_data_match.group(1).replace("<\\/", "</"))
        except json.JSONDecodeError:
            fail("readerSourcePages contains invalid JSON", issues)
    if full_paper:
        if not source_pages or len(rendered_source_pages) != len(source_pages):
            fail("source-page viewer does not expose every immutable PDF page", issues)
        expected_page_map: dict[int, str] = {}
        for row in source_pages:
            try:
                page = int(row.get("page"))
            except (AttributeError, TypeError, ValueError):
                fail("source_map.pages contains an invalid page row", issues)
                continue
            relative = str(row.get("source_page_image") or "").replace("\\", "/")
            if not re.fullmatch(r"assets/source_pages/[A-Za-z0-9._-]+\.(?:png|jpe?g|webp)", relative, re.I):
                fail(f"source page {page} uses unsafe/noncanonical path {relative!r}", issues)
                continue
            asset = reader_dir / relative
            if not asset.is_file() or sha256_file(asset) != str(row.get("sha256") or ""):
                fail(f"source page {page} asset is missing or hash-mismatched", issues)
            expected_page_map[page] = relative
        actual_page_map = {
            int(row.get("page")): str(row.get("src") or "")
            for row in rendered_source_pages
            if isinstance(row, dict) and str(row.get("page") or "").isdigit()
        }
        if actual_page_map != expected_page_map:
            fail("rendered source-page map differs from immutable source_map.pages", issues)
        for token in (
            'id="sourcePageViewer"',
            'id="sourcePageImage"',
            'id="sourcePagePrevious"',
            'id="sourcePageNext"',
            'id="toggleSourcePages"',
            'aria-controls="sourcePageViewer"',
        ):
            if token not in html_text:
                fail(f"source-page viewer contract is missing: {token}", issues)
        for record in records.values():
            if record.get("record_kind") != "block":
                continue
            if not re.fullmatch(r"(?:S|E)\d+", str(record.get("source_anchor") or "")):
                continue
            if str(record.get("source_anchor") or "") in algorithm_source_ids:
                continue
            anchor = re.escape(str(record.get("source_anchor") or ""))
            page = int(record.get("source_page") or 0)
            if not re.search(
                rf'<section class="bilingual-block[^"]*" id="{anchor}" data-source-page="{page}">',
                html_text,
                re.I,
            ):
                fail(f"{record.get('source_anchor')}: rendered block lacks source-page synchronization metadata", issues)

    for token in (
        'id="toggleOriginal"',
        'aria-controls="readerDocument"',
        "original-collapsed",
        "Hide Original",
        "Show Original",
        'id="toggleContents"',
        'id="sourcePaneResizer"',
        'id="contentsPaneResizer"',
        'role="separator"',
        "toc-collapsed",
        "Show Contents",
        "Hide Contents",
        "paper.reader.view.",
    ):
        if token not in html_text:
            fail(f"reader collapse-control contract is missing: {token}", issues)
    control_ids = ("toggleOriginal", "toggleContents")
    if full_paper:
        control_ids += ("toggleSourcePages", "sourcePaneToggle", "contentsPaneToggle")
    for control_id in control_ids:
        if not re.search(rf'id="{control_id}"[^>]*aria-pressed="false"[^>]*aria-expanded="true"', html_text):
            fail(f"{control_id} lacks initial ARIA toggle state", issues)
    if full_paper and not re.search(
        r'<div class="layout has-source-pages">\s*'
        r'<aside class="reader-sidebar"[^>]*>[\s\S]*?id="sourcePageViewer"[\s\S]*?</aside>\s*'
        r'<main>[\s\S]*?</main>\s*'
        r'<nav class="toc"',
        html_text,
        re.I,
    ):
        fail("reader is not ordered as left source-page viewer, center article, right Contents", issues)
    if full_paper and not re.search(
        r'--source-pane-width:\s*clamp\([\s\S]*?\.layout\.has-source-pages\s*\{'
        r'[\s\S]*?grid-template-columns:[^;]*var\(--source-pane-width\)',
        html_text,
        re.I,
    ):
        fail("wide reader layout does not reserve an enlarged responsive source-page column", issues)
    if full_paper and not re.search(
        r'id="sourcePaneResizer"[^>]*role="separator"[^>]*tabindex="0"[\s\S]*?'
        r'id="contentsPaneResizer"[^>]*role="separator"[^>]*tabindex="0"',
        html_text,
        re.I,
    ):
        fail("reader panes do not expose keyboard-accessible resize separators", issues)
    for token in (
        "document.body.classList.add('feedback-open')",
        "document.body.classList.remove('feedback-open')",
        "body.feedback-open .layout",
        "padding-right: calc(var(--feedback-dock-width) + 32px)",
        "body.feedback-open .layout { padding-bottom:",
    ):
        if token not in html_text:
            fail(f"docked annotation non-overlay contract is missing: {token}", issues)
    if full_paper and "body.source-pages-collapsed .source-page-viewer { display: none; }" not in html_text:
        fail("source-page collapse CSS can hide more than the page viewer or is missing", issues)
    if not re.search(
        r"@media print[\s\S]*?body\.original-collapsed[\s\S]*?display:\s*block\s*!important[\s\S]*?</style>",
        html_text,
        re.I,
    ):
        fail("print CSS does not force collapsed Original panels visible", issues)
    dark = validate_dark_theme_readability(html_text, issues)
    math_inline = [unescape(match) for match in re.findall(r'<span class="math-inline">([\s\S]*?)</span>', html_text)]
    if any(re.fullmatch(r"\$[A-Za-z]{3,}\$", value) for value in math_inline):
        fail("plain English word wrapped as inline math", issues)

    summary = {
        "adversarial_status": "fail" if issues else "pass",
        "completion_records": len(records),
        "figures": len(figures),
        "tables": len(tables),
        "algorithms": len(algorithms),
        "formulas": len(formulas),
        "references": len(references),
        "marks": len(marks),
        "original_concept_marks": original_concept_marks,
        "chinese_concept_marks": chinese_concept_marks,
        "concept_aligned_blocks": concept_aligned_blocks,
        "paper_summary_items": summary_items,
        "source_pages": len(rendered_source_pages),
        "math_display": len(re.findall(r'class="math-display"', html_text)),
        "dark_min_contrast": min(dark.values()) if dark else "missing",
    }
    return issues, summary


def main(argv: list[str]) -> int:
    no_write = "--no-write" in argv[1:]
    positional = [arg for arg in argv[1:] if arg != "--no-write"]
    if len(positional) != 1:
        print("Usage: adversarial_html_audit.py [--no-write] <reader-dir>", file=sys.stderr)
        return 2
    reader_dir = Path(positional[0]).expanduser().resolve()
    try:
        issues, summary = audit(reader_dir)
    except Exception as exc:
        issues, summary = [f"audit runtime failure: {exc}"], {"adversarial_status": "fail", "completion_records": 0}
    if not no_write:
        write_formal_manifest(reader_dir, "pass" if not issues else "audit_failed", issues, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if issues:
        print("Adversarial audit failed:", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1
    print("Adversarial HTML audit passed" + (" (read-only; manifest not updated)." if no_write else "."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
