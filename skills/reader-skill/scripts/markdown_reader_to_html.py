#!/usr/bin/env python3
"""Convert a nature-reader paper.md bundle into a standalone bilingual HTML reader."""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import mimetypes
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from reader_wiki_compile import compile_reader_wiki

LEAN_HTML_SCRIPTS = Path(__file__).resolve().parents[2] / "utils" / "lean-html-skill" / "scripts"
if LEAN_HTML_SCRIPTS.exists():
    sys.path.insert(0, str(LEAN_HTML_SCRIPTS))
try:
    from reader_html_contract import validate_generated_reader_html
except Exception as exc:  # pragma: no cover - formal builds must not silently fork the contract
    raise RuntimeError(f"lean-html-skill reader_html_contract is required for formal reader builds: {exc}") from exc
try:
    from reader_theme import (
        reader_theme_boot_script,
        reader_theme_control,
        reader_theme_css,
        reader_theme_script,
    )
except Exception as exc:  # pragma: no cover - formal builds must use the shared shell/theme
    raise RuntimeError(f"lean-html-skill reader_theme is required for formal reader builds: {exc}") from exc


ANCHOR_RE = re.compile(r'<a\s+id=["\']([^"\']+)["\']\s*>\s*</a>', re.I)
IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
HEADING_RE = re.compile(r'^(#{1,6})\s+(.+?)\s*$')
TOP_ANCHOR_RE = re.compile(r'(?m)^<a\s+id=["\']((?!C\d+\b)[^"\']+)["\']\s*>\s*</a>\s*$')
MATH_SPAN_RE = re.compile(
    r'(\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$\$[\s\S]*?\$\$|(?<!\\)\$(?!\s)(?:\\.|[^$]){1,800}?(?<!\\)\$)'
)
DISPLAY_MATH_BLOCK_RE = re.compile(r'^\s*(\\\[[\s\S]*?\\\]|\$\$[\s\S]*?\$\$)\s*$')
DISPLAY_MATH_ANY_RE = re.compile(r'(\\\[[\s\S]*?\\\]|\$\$[\s\S]*?\$\$)')
ALGORITHM_RE = re.compile(r'\bAlgorithm\s+\d+\b', re.I)
ALGORITHM_LINE_RE = re.compile(r'^\s*(\d+)\s*:\s*(.*)$')
REFERENCE_LIST_LABEL = "Reference list (original only)"
DEFAULT_MATHJAX_URL = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"
KNOWN_STATUSES = {"known", "mastered"}
ANNOTATED_STATUSES = {"unknown", "learning", "unrated"}
BILINGUAL_PAIR_RE = re.compile(
    r'(?P<original_open><article\s+class="lang-panel\s+original"[^>]*>)'
    r'(?P<original_body>[\s\S]*?)(?P<original_close></article>)'
    r'(?P<between>[\s\S]*?)'
    r'(?P<translation_open><article\s+class="lang-panel\s+translation"[^>]*>)'
    r'(?P<translation_body>[\s\S]*?)(?P<translation_close></article>)',
    re.I,
)
DRAFT_TRANSLATION_MARKERS = (
    "中文译意",
    "非逐句精翻",
    "阅读脚手架",
    "待忠实翻译",
    "未生成忠实翻译",
    "translation aid",
    "reading scaffold",
    "terminology-guided reading",
    "not a polished full translation",
    "not complete sentence-by-sentence",
)
BAD_READER_NOTE_MARKERS = (
    "这一块用于定位原文、公式、图表或实验论证",
    "如果这里有不懂的术语、公式步骤或论文用法",
    "逻辑位置：本文主题是",
    "标注建议：如果这里有不懂",
)
FORMULA_NOISE_MARKERS = (
    "QKT √ d",
    "e−iHt",
    "Rn×d",
    "RT ×n×n",
    "P v∈V",
)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


@dataclass
class Token:
    kind: str
    text: str = ""
    level: int = 0
    anchor: str | None = None
    attrs: dict[str, str] = field(default_factory=dict)


def slugify(text: str, fallback: str) -> str:
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[^\w\u4e00-\u9fff-]+', '-', text, flags=re.U).strip('-').lower()
    return text or fallback


def read_input(input_path: Path) -> tuple[Path, Path]:
    if input_path.is_dir():
        md_path = input_path / "paper.md"
    else:
        md_path = input_path
    if not md_path.exists():
        raise FileNotFoundError(f"Cannot find paper.md at {md_path}")
    return md_path, md_path.parent


def split_tokens(markdown: str) -> list[Token]:
    tokens: list[Token] = []
    lines = markdown.splitlines()
    i = 0
    pending_anchor: str | None = None

    while i < len(lines):
        line = lines[i]
        anchor_match = ANCHOR_RE.fullmatch(line.strip())
        if anchor_match:
            pending_anchor = anchor_match.group(1)
            tokens.append(Token("anchor", anchor=pending_anchor))
            i += 1
            continue

        heading_match = HEADING_RE.match(line)
        if heading_match:
            tokens.append(
                Token(
                    "heading",
                    text=heading_match.group(2).strip(),
                    level=len(heading_match.group(1)),
                    anchor=pending_anchor,
                )
            )
            pending_anchor = None
            i += 1
            continue

        if line.startswith("|") and i + 1 < len(lines) and re.match(r'^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$', lines[i + 1]):
            table_lines = [line, lines[i + 1]]
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                table_lines.append(lines[i])
                i += 1
            tokens.append(Token("table", text="\n".join(table_lines), anchor=pending_anchor))
            pending_anchor = None
            continue

        if not line.strip():
            i += 1
            continue

        paragraph = [line]
        i += 1
        while i < len(lines):
            nxt = lines[i]
            if not nxt.strip():
                paragraph.append(nxt)
                i += 1
                if paragraph and paragraph[-1] == "":
                    break
                continue
            if ANCHOR_RE.fullmatch(nxt.strip()) or HEADING_RE.match(nxt):
                break
            if nxt.startswith("|") and i + 1 < len(lines) and re.match(r'^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$', lines[i + 1]):
                break
            paragraph.append(nxt)
            i += 1
        tokens.append(Token("paragraph", text="\n".join(paragraph).strip(), anchor=pending_anchor))
        pending_anchor = None

    return tokens


def strip_label(text: str, label: str) -> str:
    return re.sub(rf'^\*\*{re.escape(label)}:\*\*\s*', '', text.strip(), flags=re.I)


def starts_label(text: str, label: str) -> bool:
    return bool(re.match(rf'^\*\*{re.escape(label)}:\*\*', text.strip(), flags=re.I))


def validate_translation_contract(markdown: str, allow_draft_translation: bool = False) -> list[str]:
    issues: list[str] = []
    marker_lut = tuple(marker.lower() for marker in DRAFT_TRANSLATION_MARKERS)
    lines = markdown.splitlines()
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        for label in ("中文", "涓枃"):
            if starts_label(stripped, label):
                body = strip_label(stripped, label)
                lowered = body.lower()
                if any(marker in lowered for marker in marker_lut):
                    issues.append(f"line {idx}: Chinese column contains draft/paraphrase marker")
                break
    if issues and not allow_draft_translation:
        preview = "\n".join(f"- {issue}" for issue in issues[:12])
        if len(issues) > 12:
            preview += f"\n- ... {len(issues) - 12} more"
        raise ValueError(
            "Chinese translation contract failed. The `**中文:**` column must contain faithful translations, "
            "not interpretive summaries or reading scaffolds.\n"
            f"{preview}\n"
            "Regenerate `paper.md` with a real translation pass before final HTML generation, or use --allow-draft-translation for an explicitly named draft preview."
        )
    return issues


def load_source_map(base_dir: Path) -> dict:
    source_map = base_dir / "source_map.json"
    if not source_map.exists():
        return {}
    try:
        return json.loads(source_map.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"source_map.json is not valid JSON: {exc}") from exc


def markdown_block_for_anchor(markdown: str, block_id: str) -> str:
    anchor = f'<a id="{block_id}"></a>'
    start = markdown.find(anchor)
    if start < 0:
        return ""
    next_match = re.search(r'\n<a id="[^"]+"></a>', markdown[start + len(anchor):])
    if not next_match:
        return markdown[start:]
    return markdown[start:start + len(anchor) + next_match.start()]


def has_figure_or_table_card(markdown: str, kind: str) -> bool:
    if kind == "figure":
        return bool(IMAGE_RE.search(markdown)) and (
            "Original caption" in markdown
            or "中文图注" in markdown
            or re.search(r'^###\s+(Fig\.|Figure|图)\b', markdown, re.M)
        )
    if kind == "table":
        return (
            "| ---" in markdown
            or "Original table" in markdown
            or "中文表注" in markdown
            or re.search(r'^###\s+(Table|表)\b', markdown, re.M)
        )
    return False


def validate_reader_structure(markdown: str, base_dir: Path) -> list[str]:
    """Reject readers that are translated textually but still structurally incomplete."""
    issues: list[str] = []
    lowered = markdown.lower()

    for marker in BAD_READER_NOTE_MARKERS:
        if marker in markdown:
            issues.append(f"generic/template note remains: {marker}")

    for marker in FORMULA_NOISE_MARKERS:
        if marker.lower() in lowered:
            issues.append(f"formula extraction noise remains instead of LaTeX: {marker}")

    source_map = load_source_map(base_dir)
    figures = source_map.get("figures") or []
    tables = source_map.get("tables") or []
    blocks = source_map.get("blocks") or []

    if figures and not has_figure_or_table_card(markdown, "figure"):
        issues.append("source_map has figure blocks but paper.md has no figure card/image/caption translation")
    if tables and not has_figure_or_table_card(markdown, "table"):
        issues.append("source_map has table blocks but paper.md has no semantic table card/table translation")

    for block in blocks:
        if block.get("type") != "equation_or_formula":
            continue
        block_id = str(block.get("id") or "")
        if not block_id:
            continue
        md_block = markdown_block_for_anchor(markdown, block_id)
        if md_block and not re.search(r'(\\\[|\\\(|\$\$|(?<!\\)\$)', md_block):
            issues.append(f"{block_id}: equation/formula block lacks reconstructed LaTeX math")

    if issues:
        preview = "\n".join(f"- {issue}" for issue in issues[:12])
        if len(issues) > 12:
            preview += f"\n- ... {len(issues) - 12} more"
        raise ValueError(
            "Reader structure contract failed. Final reader_interactive.html requires real figure/table cards, "
            "LaTeX-readable formulas, and block-specific notes rather than template scaffolding.\n"
            f"{preview}\n"
            "Fix paper.md/source_map.json first, then regenerate reader_interactive.html."
        )
    return issues


def is_math_display_block(text: str) -> bool:
    return bool(DISPLAY_MATH_BLOCK_RE.match(text.strip()))


def render_math_display(text: str) -> str:
    return f'<div class="math-display">{html.escape(text.strip())}</div>'


def markdown_inline(text: str, base_dir: Path, embed_assets: bool, warnings: list[str]) -> str:
    protected_math: list[str] = []
    protected_links: list[str] = []

    def stash_link(match: re.Match[str]) -> str:
        label = html.escape(match.group(1), quote=False)
        href = html.escape(match.group(2), quote=True)
        protected_links.append(f'<a href="{href}" target="_blank" rel="noopener">{label}</a>')
        return f"@@LINK{len(protected_links) - 1}@@"

    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', stash_link, text)

    # Formal math components must come only from explicit, compiler-audited
    # LaTeX delimiters. Guessing math from underscores or superscripts can
    # create a formula chip on only one language side and break alignment.

    def stash_math(match: re.Match[str]) -> str:
        protected_math.append(f'<span class="math-inline">{html.escape(match.group(0))}</span>')
        return f"@@MATH{len(protected_math) - 1}@@"

    text = MATH_SPAN_RE.sub(stash_math, text)
    text = html.escape(text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    for idx, link_html in enumerate(protected_links):
        text = text.replace(f"@@LINK{idx}@@", link_html)
    for idx, math_html in enumerate(protected_math):
        text = text.replace(f"@@MATH{idx}@@", math_html)
    return text


def image_src(path_text: str, base_dir: Path, embed_assets: bool, warnings: list[str]) -> str:
    path_text = path_text.strip()
    if re.match(r'^(https?:|data:)', path_text):
        return path_text
    image_path = (base_dir / path_text).resolve()
    if not image_path.exists():
        warnings.append(f"Missing image asset: {path_text}")
        return path_text
    if not embed_assets:
        return path_text.replace("\\", "/")
    mime = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def markdown_blocks(text: str, base_dir: Path, embed_assets: bool, warnings: list[str]) -> str:
    text = text.strip()
    if not text:
        return ""

    def replace_image(match: re.Match[str]) -> str:
        alt = html.escape(match.group(1), quote=True)
        src = html.escape(image_src(match.group(2), base_dir, embed_assets, warnings), quote=True)
        return f'<img src="{src}" alt="{alt}">'

    text = IMAGE_RE.sub(replace_image, text)
    parts = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    rendered: list[str] = []
    for part in parts:
        anchor_match = ANCHOR_RE.fullmatch(part.strip())
        heading_match = HEADING_RE.match(part.strip())
        if anchor_match:
            rendered.append(f'<span id="{html.escape(anchor_match.group(1), quote=True)}"></span>')
        elif heading_match:
            level = min(max(len(heading_match.group(1)), 2), 4)
            rendered.append(f"<h{level}>{markdown_inline(heading_match.group(2), base_dir, embed_assets, warnings)}</h{level}>")
        elif part.startswith("|") and "\n|" in part:
            rendered.append(render_table(part))
        elif part.startswith("<img "):
            rendered.append(part)
        elif is_math_display_block(part):
            rendered.append(render_math_display(part))
        elif DISPLAY_MATH_ANY_RE.search(part):
            for chunk in DISPLAY_MATH_ANY_RE.split(part):
                chunk = chunk.strip()
                if not chunk:
                    continue
                if is_math_display_block(chunk):
                    rendered.append(render_math_display(chunk))
                else:
                    rendered.append(f"<p>{markdown_inline(chunk, base_dir, embed_assets, warnings).replace(chr(10), '<br>')}</p>")
        else:
            rendered.append(f"<p>{markdown_inline(part, base_dir, embed_assets, warnings).replace(chr(10), '<br>')}</p>")
    return "\n".join(rendered)


def render_table(markdown_table: str) -> str:
    rows = []
    for line in markdown_table.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    if len(rows) < 2:
        return f'<pre>{html.escape(markdown_table)}</pre>'
    header = rows[0]
    body = rows[2:]
    out = ['<div class="table-wrap"><table>']
    out.append("<thead><tr>" + "".join(f"<th>{html.escape(c)}</th>" for c in header) + "</tr></thead>")
    out.append("<tbody>")
    for row in body:
        out.append("<tr>" + "".join(f"<td>{markdown_inline(c, Path('.'), True, [])}</td>" for c in row) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


def collect_meta(base_dir: Path) -> dict:
    source_map = base_dir / "source_map.json"
    if not source_map.exists():
        return {}
    try:
        return json.loads(source_map.read_text(encoding="utf-8")).get("paper", {})
    except Exception:
        return {}


def find_agent_dir(base_dir: Path, explicit: str | None = None) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    for parent in [base_dir, *base_dir.parents]:
        candidate = parent / ".agents"
        if candidate.exists():
            return candidate
    return None


def load_profile(profile_path: Path | None) -> dict | None:
    if not profile_path or not profile_path.exists():
        return None
    return json.loads(profile_path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    json.loads(tmp_path.read_text(encoding="utf-8"))
    tmp_path.replace(path)


def write_artifact_manifest(base_dir: Path, output_path: Path, status: str, issues: list[str] | None = None) -> None:
    wiki = base_dir / "reader_wiki"
    manifest: dict[str, object] = {
        "version": 1,
        "generated_by": "skills/reader-skill/scripts/markdown_reader_to_html.py",
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).replace(microsecond=0).isoformat(),
        "formal_status": status,
        "issues": issues or [],
        "artifacts": {},
    }
    artifacts = manifest["artifacts"]
    assert isinstance(artifacts, dict)
    for label, path in (
        ("source_map", base_dir / "source_map.json"),
        ("completion_ledger", wiki / "completion_ledger.json"),
        ("original_normalization_ledger", wiki / "original_normalization_ledger.json"),
        ("concept_candidates", wiki / "concept_candidates.json"),
        ("reader_manifest", wiki / "reader_manifest.json"),
        ("structure_validation_report", wiki / "structure_validation_report.json"),
        ("normalized_reader", wiki / "normalized_reader.md"),
        ("html", output_path),
    ):
        if path.exists():
            artifacts[label] = {
                "path": path.relative_to(base_dir).as_posix(),
                "sha256": sha256_file(path),
            }
    atomic_write_json(wiki / "formal_artifact_manifest.json", manifest)


def extract_glossary(base_dir: Path) -> list[dict]:
    concept_ledger = base_dir / "reader_wiki" / "concept_ledger.json"
    if concept_ledger.exists():
        try:
            data = json.loads(concept_ledger.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        entries = data.get("concepts", []) if isinstance(data, dict) else []
        cleaned = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            term = str(item.get("canonical_name", "")).strip()
            if not term:
                continue
            aliases_zh = item.get("aliases_zh") if isinstance(item.get("aliases_zh"), list) else []
            source_anchors = item.get("source_anchors") if isinstance(item.get("source_anchors"), list) else []
            cleaned.append({
                "term": term,
                "translation": str(aliases_zh[0]).strip() if aliases_zh else "",
                "note": str(item.get("explanation_note", "")).strip(),
                "concept_id": str(item.get("concept_id", "")).strip(),
                "concept_type": str(item.get("concept_type", "term")).strip() or "term",
                "source_anchors": [str(anchor) for anchor in source_anchors if str(anchor).strip()],
                "aliases_en": [str(alias) for alias in item.get("aliases_en", []) or []],
                "aliases_zh": [str(alias) for alias in aliases_zh],
                "status": str(item.get("status", "unrated")).strip().lower() or "unrated",
            })
        if cleaned:
            return cleaned

    source_map = base_dir / "source_map.json"
    if not source_map.exists():
        return []
    try:
        data = json.loads(source_map.read_text(encoding="utf-8"))
    except Exception:
        return []
    glossary = data.get("glossary", [])
    if not isinstance(glossary, list):
        return []
    cleaned = []
    for item in glossary:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term", "")).strip()
        if not term:
            continue
        cleaned.append({
            "term": term,
            "translation": str(item.get("translation", "")).strip(),
            "note": str(item.get("note", "")).strip(),
            "concept_id": "",
            "concept_type": "term",
            "source_anchors": [],
            "aliases_en": [term],
            "aliases_zh": [str(item.get("translation", "")).strip()] if item.get("translation") else [],
            "status": "unrated",
        })
    return cleaned


def normalize_key(term: str) -> str:
    return re.sub(r'\s+', ' ', term.strip()).lower()


def usable_translation(value: object, fallback: object = "") -> str:
    text = str(value or "").strip()
    fallback_text = str(fallback or "").strip()
    if not text:
        return fallback_text
    compact = re.sub(r'\s+', '', text)
    if compact and set(compact) <= {"?"}:
        return fallback_text
    if "�" in text:
        return fallback_text
    return text


def profile_lookup(profile: dict) -> dict[str, tuple[str, dict]]:
    lookup: dict[str, tuple[str, dict]] = {}
    for term, info in profile.get("concepts", {}).items():
        if not isinstance(info, dict):
            continue
        lookup[normalize_key(term)] = (term, info)
        label = str(info.get("label", "")).strip()
        if label:
            lookup[normalize_key(label)] = (label, info)
        aliases = []
        aliases.extend(info.get("aliases", []) or [])
        aliases.extend(info.get("aliases_en", []) or [])
        aliases.extend(info.get("aliases_zh", []) or [])
        for alias in aliases:
            lookup[normalize_key(str(alias))] = (str(alias), info)
    return lookup


def concepts_for_annotation(profile: dict, glossary: list[dict]) -> list[dict]:
    lookup = profile_lookup(profile)
    concepts: list[dict] = []
    seen: set[str] = set()
    for item in glossary:
        key = normalize_key(item["term"])
        _matched_term, info = lookup.get(key, (item["term"], {"status": item.get("status", "unrated")}))
        term = item["term"]
        status = str(info.get("status") or item.get("status") or "unrated").lower()
        if status not in (ANNOTATED_STATUSES | KNOWN_STATUSES):
            status = "unrated"
        if normalize_key(term) in seen:
            continue
        seen.add(normalize_key(term))
        aliases_en = item.get("aliases_en") if isinstance(item.get("aliases_en"), list) else []
        aliases_zh = item.get("aliases_zh") if isinstance(item.get("aliases_zh"), list) else []
        source_anchors = item.get("source_anchors") if isinstance(item.get("source_anchors"), list) else []
        concepts.append({
            "term": term,
            "status": status,
            "translation": usable_translation(info.get("translation"), item.get("translation", "")),
            "explanation": info.get("ai_explanation") or item.get("note", ""),
            "note": info.get("user_note", ""),
            "concept_id": item.get("concept_id") or normalize_key(term),
            "concept_type": item.get("concept_type") or "term",
            "source_anchor": source_anchors[0] if source_anchors else "",
            "aliases_en": [str(alias).strip() for alias in aliases_en if str(alias).strip()],
            "aliases_zh": [str(alias).strip() for alias in aliases_zh if str(alias).strip()],
            "alias_zh": usable_translation(aliases_zh[0] if aliases_zh else "", item.get("translation", "")),
        })
    concepts.sort(
        key=lambda item: max(
            [len(item["term"])]
            + [len(alias) for alias in item.get("aliases_en", [])]
            + [len(alias) for alias in item.get("aliases_zh", [])]
        ),
        reverse=True,
    )
    return concepts


def concept_match_terms(concept: dict, language: str) -> list[str]:
    """Return the controlled vocabulary permitted in one language panel."""
    if language == "zh":
        candidates = concept.get("aliases_zh", [])
    else:
        candidates = [concept.get("term", ""), *concept.get("aliases_en", [])]
    terms: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        term = str(candidate).strip()
        key = term.casefold()
        if term and key not in seen:
            seen.add(key)
            terms.append(term)
    return terms


def concept_term_pattern(term: str) -> re.Pattern[str]:
    escaped = re.escape(html.escape(term))
    # Chinese aliases are commonly embedded without spaces. ASCII word
    # boundaries are useful for English but would suppress valid Han matches.
    if re.search(r"[\u3400-\u9fff]", term):
        return re.compile(f"({escaped})", re.I)
    return re.compile(r"(?<![\w-])(" + escaped + r")(?![\w-])", re.I)


def annotate_text_segment(text: str, concepts: list[dict], language: str = "en") -> str:
    pieces = MATH_SPAN_RE.split(text)
    for idx in range(0, len(pieces), 2):
        piece = pieces[idx]
        matches = []
        for order, concept in enumerate(concepts):
            for term in concept_match_terms(concept, language):
                for match in concept_term_pattern(term).finditer(piece):
                    matches.append((match.start(), match.end(), order, concept, match.group(1)))
        if matches:
            matches.sort(key=lambda item: (item[0], -(item[1] - item[0]), item[2]))
            selected = []
            covered_until = -1
            for start, end, _order, concept, matched_text in matches:
                if start < covered_until:
                    continue
                selected.append((start, end, concept, matched_text))
                covered_until = end

            rendered = []
            cursor = 0
            for start, end, concept, matched_text in selected:
                rendered.append(piece[cursor:start])
                label = html.escape(concept.get("translation") or concept.get("explanation") or concept["status"], quote=True)
                status = html.escape(concept["status"], quote=True)
                data_term = html.escape(concept["term"], quote=True)
                source_anchor = html.escape(str(concept.get("source_anchor", "")), quote=True)
                concept_type = html.escape(str(concept.get("concept_type", "term")), quote=True)
                alias_zh = html.escape(str(concept.get("alias_zh", "")), quote=True)
                concept_id = html.escape(str(concept.get("concept_id") or concept["term"]), quote=True)
                rendered.append(
                    f'<mark class="knowledge-gap {status}" data-concept="{data_term}" '
                    f'data-status="{status}" data-source-anchor="{source_anchor}" '
                    f'data-concept-type="{concept_type}" data-alias-zh="{alias_zh}" '
                    f'data-concept-id="{concept_id}" role="button" tabindex="0" title="{label}">{matched_text}</mark>'
                )
                cursor = end
            rendered.append(piece[cursor:])
            piece = "".join(rendered)
        pieces[idx] = piece
    return "".join(pieces)


def annotate_html_fragment(html_text: str, concepts: list[dict], language: str = "en") -> str:
    if not concepts:
        return html_text
    parts = re.split(r'(<[^>]+>)', html_text)
    for idx in range(0, len(parts), 2):
        parts[idx] = annotate_text_segment(parts[idx], concepts, language)
    return "".join(parts)


def annotate_html_text(html_text: str, concepts: list[dict]) -> str:
    if not concepts:
        return html_text

    def annotate_pair(match: re.Match[str]) -> str:
        original_body = annotate_html_fragment(match.group("original_body"), concepts, "en")
        original_ids = set(re.findall(r'data-concept-id="([^"]+)"', original_body, re.I))
        paired_concepts = [
            concept
            for concept in concepts
            if str(concept.get("concept_id") or concept.get("term")) in original_ids
        ]
        translation_body = annotate_html_fragment(
            match.group("translation_body"),
            paired_concepts,
            "zh",
        )
        return (
            match.group("original_open")
            + original_body
            + match.group("original_close")
            + match.group("between")
            + match.group("translation_open")
            + translation_body
            + match.group("translation_close")
        )

    return BILINGUAL_PAIR_RE.sub(annotate_pair, html_text)


def build_knowledge_panel(profile: dict | None, glossary: list[dict], concepts: list[dict], profile_path: Path | None) -> str:
    status_labels = {
        "unknown": "Needs explanation",
        "learning": "Learning",
        "known": "Known",
        "mastered": "Mastered",
        "unrated": "Unrated",
    }
    concept_type_labels = {
        "figure_element": "Figure element",
        "formula_variable": "Formula variable",
        "math_object": "Mathematical object",
        "method_component": "Method component",
        "metric": "Metric",
        "model_module": "Model module",
        "term": "Term",
    }
    rows = []
    status_counts = {status: 0 for status in ("unknown", "learning", "known", "mastered", "unrated")}
    unmatched_count = 0
    lookup = profile_lookup(profile or {})
    for item in glossary:
        term = item["term"]
        matched = lookup.get(normalize_key(term))
        if matched:
            _matched_term, info = matched
            status = str(info.get("status") or "unrated").lower()
            status_counts[status if status in status_counts else "unknown"] += 1
            status_label = status_labels.get(status, "Unrated")
        else:
            info = {}
            status = "unrated"
            status_label = "Not in personal profile"
            unmatched_count += 1
        translation = usable_translation(info.get("translation"), item.get("translation", ""))
        explanation = info.get("ai_explanation") or item.get("note", "")
        rows.append(
            "<tr>"
            f"<td>{html.escape(term)}</td>"
            f"<td><span class=\"status {html.escape(status, quote=True)}\">{html.escape(status_label)}</span></td>"
            f"<td>{html.escape(str(translation))}</td>"
            f"<td>{html.escape(concept_type_labels.get(str(item.get('concept_type', 'term')), 'Term'))}</td>"
            f"<td>{html.escape(str(explanation))}</td>"
            "</tr>"
        )
    if not rows:
        rows.append('<tr><td colspan="5">No glossary concepts detected for this reader.</td></tr>')
    if profile_path and ".agents" in profile_path.parts:
        profile_label = Path(*profile_path.parts[profile_path.parts.index(".agents"):]).as_posix()
    else:
        profile_label = profile_path.name if profile_path else "profile loaded"
    summary = " · ".join([
        f"Learning: {status_counts['learning']}",
        f"Known: {status_counts['known']}",
        f"Mastered: {status_counts['mastered']}",
        f"Needs explanation: {status_counts['unknown']}",
        f"Not in personal profile: {unmatched_count}",
    ])
    return f'''
<section class="knowledge-panel" id="personal-knowledge-boundary">
  <h2>Paper Concept Ledger / Personal Knowledge Boundary</h2>
  <p>The paper-specific concept ledger comes from <code>reader_wiki/concept_ledger.json</code>. A learning status is shown only for an exact match in the personal knowledge profile; all other rows mean only that the concept is not yet recorded in that profile.</p>
  <p class="knowledge-summary">{html.escape(summary)}</p>
  <p class="profile-path">Personal knowledge profile: {html.escape(profile_label)}</p>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Concept</th><th>Personal Status</th><th>Chinese Name</th><th>Type</th><th>Role in This Paper</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>
</section>'''.strip()


def load_compiled_paper_summary(base_dir: Path) -> dict:
    manifest_path = base_dir / "reader_wiki" / "reader_manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    summary = manifest.get("paper_summary")
    return summary if isinstance(summary, dict) else {}


def summary_source_links(anchors: object) -> str:
    if not isinstance(anchors, list):
        return ""
    links = []
    for anchor in anchors:
        value = str(anchor).strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", value):
            continue
        escaped = html.escape(value)
        links.append(f'<a class="summary-source" href="#{html.escape(value, quote=True)}">{escaped}</a>')
    return f'<span class="summary-sources" aria-label="Source anchors">{" ".join(links)}</span>' if links else ""


def build_paper_summary_panel(summary: dict) -> str:
    if not summary:
        return ""
    overview = summary.get("overview") if isinstance(summary.get("overview"), dict) else {}
    sections = (
        ("what_it_does", "What the Paper Does / 做了什么", "ul"),
        ("how_it_works", "How It Works / 怎么做的", "ol"),
        ("why_it_matters", "Why It Matters / 有什么意义", "ul"),
        ("evidence_and_limitations", "Evidence, Scope, and Limitations / 证据、范围与局限", "ul"),
    )
    rendered_sections = []
    for key, heading, list_tag in sections:
        items = summary.get(key) if isinstance(summary.get(key), list) else []
        rendered_items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            text_value = str(item.get("text") or "").strip()
            if not text_value:
                continue
            rendered_items.append(
                f'<li><span class="summary-text">{html.escape(text_value)}</span>'
                f'{summary_source_links(item.get("source_anchors"))}</li>'
            )
        if rendered_items:
            rendered_sections.append(
                f'<section class="paper-summary-section"><h3>{html.escape(heading)}</h3>'
                f'<{list_tag}>{"".join(rendered_items)}</{list_tag}></section>'
            )
    overview_text = html.escape(str(overview.get("text") or "").strip())
    return f'''
<section class="paper-summary" id="paper-summary">
  <h2>Paper Summary / 论文总结</h2>
  <div class="paper-summary-overview">
    <p>{overview_text}</p>
    {summary_source_links(overview.get("source_anchors"))}
  </div>
  {''.join(rendered_sections)}
</section>'''.strip()


def build_feedback_ui(title: str, base_dir: Path, concepts: list[dict], enabled: bool) -> str:
    if not enabled:
        return ""
    wiki = base_dir / "reader_wiki"
    provenance = {}
    for label, path in (
        ("source_map", base_dir / "source_map.json"),
        ("completion_ledger", wiki / "completion_ledger.json"),
        ("reader_manifest", wiki / "reader_manifest.json"),
        ("structure_validation_report", wiki / "structure_validation_report.json"),
    ):
        if path.exists():
            provenance[label] = {"path": str(path), "sha256": sha256_file(path)}
    metadata = {
        "reader_feedback_version": 2,
        "paper_title": title,
        "reader_path": str(base_dir),
        "bundle_provenance": provenance,
        "feedback_capabilities": ["concept_status", "freeform_annotation", "source_excerpt"],
        "concept_count": len(concepts),
        "items": []
    }
    metadata_json = json.dumps(metadata, ensure_ascii=False).replace("</", "<\\/")
    return f'''
<button type="button" class="feedback-opener" id="openFreeFeedback">Annotate / 自由标注</button>
<aside class="feedback-dock" id="feedbackDock" hidden>
  <h2>Concept Feedback / 自由标注</h2>
  <div class="selected-concept" id="feedbackConcept">No concept selected</div>
  <label class="field-label" for="feedbackCustomConcept">Concept or phrase</label>
  <input id="feedbackCustomConcept" type="text" placeholder="Type a concept, phrase, or selected text">
  <div class="status-buttons" aria-label="Concept status">
    <button type="button" data-status="mastered">mastered</button>
    <button type="button" data-status="known">known</button>
    <button type="button" data-status="learning">learning</button>
    <button type="button" data-status="unknown">unknown</button>
    <button type="button" data-status="unrated">unrated</button>
  </div>
  <label><input type="checkbox" id="needsExplanation"> needs explanation</label>
  <label class="field-label" for="feedbackConfusionType">Question type</label>
  <select id="feedbackConfusionType">
    <option value="">unspecified</option>
    <option value="term_definition">term definition</option>
    <option value="paper_usage">paper-specific usage</option>
    <option value="math_step">math derivation or formula</option>
    <option value="algorithm_step">algorithm step</option>
    <option value="assumption">assumption or condition</option>
    <option value="evidence">evidence or experiment</option>
    <option value="relation">relation to another concept</option>
    <option value="other">other</option>
  </select>
  <textarea id="feedbackQuestion" placeholder="Write your exact question for Codex. Example: I know 1-RDM generally, but I do not see why it is enough here."></textarea>
  <textarea id="feedbackNote" placeholder="Optional note about your current understanding. Example: I know the term, but not this paper's usage."></textarea>
  <label class="field-label" for="feedbackExplanationStyle">Preferred explanation</label>
  <select id="feedbackExplanationStyle">
    <option value="">Codex chooses</option>
    <option value="first_principles">first principles</option>
    <option value="paper_context">connect to this paper</option>
    <option value="math_steps">show math steps</option>
    <option value="analogy">use an analogy</option>
    <option value="example">give a concrete example</option>
  </select>
  <label class="field-label" for="feedbackContext">Source context / selected text</label>
  <textarea id="feedbackContext" placeholder="Paste or capture the sentence/paragraph that confused you."></textarea>
  <div class="feedback-actions">
    <button type="button" class="primary" id="saveFeedback">Save mark</button>
    <button type="button" id="useSelectedText">Use selected text</button>
    <button type="button" id="deleteFeedback">Delete current</button>
    <button type="button" id="downloadFeedback">Download feedback JSON</button>
    <button type="button" id="copyFeedback">Copy feedback for Codex</button>
    <button type="button" id="closeFeedback">Close</button>
  </div>
  <div class="feedback-summary" id="feedbackSummary">No saved feedback yet.</div>
  <textarea id="feedbackExportFallback" class="feedback-export-fallback" readonly hidden aria-label="Feedback JSON export fallback"></textarea>
  <details class="feedback-list-wrap" id="feedbackListWrap">
    <summary id="feedbackListSummary">Saved annotations (0)</summary>
    <div class="feedback-list" id="feedbackList" aria-live="polite"></div>
  </details>
</aside>
<script type="application/json" id="readerFeedbackSeed">__READER_FEEDBACK_SEED__</script>
<script>
(function () {{
  const seed = JSON.parse(document.getElementById('readerFeedbackSeed').textContent);
  const feedback = new Map();
  const dock = document.getElementById('feedbackDock');
  const conceptLabel = document.getElementById('feedbackConcept');
  const conceptInput = document.getElementById('feedbackCustomConcept');
  const question = document.getElementById('feedbackQuestion');
  const note = document.getElementById('feedbackNote');
  const context = document.getElementById('feedbackContext');
  const confusionType = document.getElementById('feedbackConfusionType');
  const explanationStyle = document.getElementById('feedbackExplanationStyle');
  const needsExplanation = document.getElementById('needsExplanation');
  const summary = document.getElementById('feedbackSummary');
  const statusButtons = Array.from(document.querySelectorAll('.status-buttons button'));
  const opener = document.getElementById('openFreeFeedback');
  let currentConcept = null;
  let currentBlock = null;
  let currentKind = 'concept';
  let currentSourceExcerpt = '';
  let currentSelectedText = '';
  let currentKey = null;
  let currentSelectionMeta = {{}};
  let currentConceptMeta = {{}};
  let lastSelection = {{
    text: '',
    blockId: '',
    excerpt: '',
    selected_language: '',
    bilingual_block_id: '',
    original_context: '',
    translation_context: ''
  }};

  function closestBlockId(el) {{
    const block = el.closest('.bilingual-block[id], .prose[id], .figure-card[id], .label-card[id], .md-table[id], section[id], article[id], [id]');
    return block ? block.id : '';
  }}

  function closestBlock(el) {{
    return el ? el.closest('.bilingual-block, .prose, .figure-card, .label-card, .md-table, section, article') : null;
  }}

  function cleanExcerpt(text, limit) {{
    return (text || '').replace(/\\s+/g, ' ').trim().slice(0, limit || 1600);
  }}

  function blockExcerpt(el) {{
    const block = closestBlock(el);
    return block ? cleanExcerpt(block.innerText, 1600) : '';
  }}

  function contextForElement(el) {{
    const element = el && el.nodeType === Node.ELEMENT_NODE ? el : el ? el.parentElement : null;
    if (!element) return {{
      blockId: '',
      excerpt: '',
      selected_language: '',
      bilingual_block_id: '',
      original_context: '',
      translation_context: ''
    }};
    const panel = element.closest('.lang-panel');
    const bilingual = element.closest('.bilingual-block');
    let selectedLanguage = '';
    if (panel && panel.classList.contains('original')) selectedLanguage = 'original';
    if (panel && panel.classList.contains('translation')) selectedLanguage = 'translation';
    const originalPanel = bilingual ? bilingual.querySelector('.lang-panel.original') : null;
    const translationPanel = bilingual ? bilingual.querySelector('.lang-panel.translation') : null;
    return {{
      blockId: closestBlockId(element),
      excerpt: blockExcerpt(element),
      selected_language: selectedLanguage,
      bilingual_block_id: bilingual ? bilingual.id : '',
      original_context: originalPanel ? cleanExcerpt(originalPanel.innerText, 2200) : '',
      translation_context: translationPanel ? cleanExcerpt(translationPanel.innerText, 2200) : ''
    }};
  }}

  function selectionInfo() {{
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return {{ text: '', blockId: '', excerpt: '' }};
    const text = cleanExcerpt(selection.toString(), 1600);
    const node = selection.anchorNode;
    const meta = contextForElement(node);
    return {{ text, ...meta }};
  }}

  function rememberSelection() {{
    const selected = selectionInfo();
    if (selected.text) lastSelection = selected;
    return selected.text ? selected : lastSelection;
  }}

  function setStatus(status) {{
    statusButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.status === status));
  }}

  function getStatus() {{
    const active = statusButtons.find(btn => btn.classList.contains('active'));
    return active ? active.dataset.status : 'unrated';
  }}

  function payload() {{
    return {{
      ...seed,
      exported_at: new Date().toISOString(),
      items: Array.from(feedback.values())
    }};
  }}

  function refreshSummary() {{
    const count = feedback.size;
    summary.textContent = count ? `${{count}} feedback item(s) saved.` : 'No saved feedback yet.';
    refreshFeedbackList();
  }}

  function feedbackKey(concept, blockId, kind) {{
    return `${{kind || 'concept'}}::${{concept || 'free annotation'}}::${{blockId || ''}}`;
  }}

  function keyMatches(el, key) {{
    return el && el.dataset && el.dataset.feedbackKey === key;
  }}

  function blockById(blockId) {{
    return blockId ? document.getElementById(blockId) : null;
  }}

  function removeVisualFeedback(key) {{
    document.querySelectorAll('[data-feedback-key]').forEach(el => {{
      if (!keyMatches(el, key)) return;
      if (el.classList.contains('saved-free-annotation')) {{
        const textNode = document.createTextNode(el.textContent || '');
        el.replaceWith(textNode);
      }} else {{
        el.remove();
      }}
    }});
  }}

  function highlightSelectedText(key, item) {{
    const selectedText = (item.selected_text || '').trim();
    const block = blockById(item.block_id);
    if (!block || selectedText.length < 2) return false;
    const walker = document.createTreeWalker(block, NodeFilter.SHOW_TEXT, {{
      acceptNode(node) {{
        const parent = node.parentElement;
        if (!parent) return NodeFilter.FILTER_REJECT;
        if (parent.closest('script, style, textarea, pre, code, .math-inline, .math-display, mark, .saved-feedback-tray')) return NodeFilter.FILTER_REJECT;
        return node.nodeValue && node.nodeValue.includes(selectedText) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
      }}
    }});
    const node = walker.nextNode();
    if (!node) return false;
    const idx = node.nodeValue.indexOf(selectedText);
    if (idx < 0) return false;
    const before = document.createTextNode(node.nodeValue.slice(0, idx));
    const marked = document.createElement('mark');
    marked.className = 'saved-free-annotation';
    marked.dataset.feedbackKey = key;
    marked.title = 'Saved annotation';
    marked.textContent = selectedText;
    const after = document.createTextNode(node.nodeValue.slice(idx + selectedText.length));
    node.replaceWith(before, marked, after);
    return true;
  }}

  function addBlockMarker(key, item) {{
    const block = blockById(item.block_id);
    if (!block) return;
    const existing = Array.from(block.querySelectorAll('.saved-feedback-badge')).find(el => keyMatches(el, key));
    if (existing) return;
    let tray = Array.from(block.children).find(el => el.classList && el.classList.contains('saved-feedback-tray'));
    if (!tray) {{
      tray = document.createElement('div');
      tray.className = 'saved-feedback-tray';
      block.prepend(tray);
    }}
    const badge = document.createElement('button');
    badge.type = 'button';
    badge.className = 'saved-feedback-badge';
    badge.dataset.feedbackKey = key;
    badge.textContent = `已标注：${{(item.concept || item.selected_text || 'free annotation').slice(0, 32)}}`;
    badge.addEventListener('click', () => openSavedFeedback(key));
    tray.appendChild(badge);
  }}

  function showVisualFeedback(key, item) {{
    if (item.annotation_kind === 'freeform') highlightSelectedText(key, item);
    addBlockMarker(key, item);
  }}

  function deleteFeedbackItem(key) {{
    if (!key || !feedback.has(key)) return;
    feedback.delete(key);
    removeVisualFeedback(key);
    if (currentKey === key) {{
      currentKey = null;
      currentConcept = '';
      currentBlock = '';
      currentKind = 'freeform';
      currentSourceExcerpt = '';
      currentSelectedText = '';
      currentSelectionMeta = {{}};
      currentConceptMeta = {{}};
      conceptLabel.textContent = 'No concept selected';
      conceptInput.value = '';
      question.value = '';
      note.value = '';
      context.value = '';
      confusionType.value = '';
      explanationStyle.value = '';
      needsExplanation.checked = false;
      setStatus('unrated');
    }}
    refreshSummary();
  }}

  function openSavedFeedback(key) {{
    const existing = feedback.get(key);
    if (!existing) return;
    currentKey = key;
    currentConcept = existing.concept || '';
    currentBlock = existing.block_id || '';
    currentKind = existing.annotation_kind || 'freeform';
    currentSourceExcerpt = existing.source_excerpt || '';
    currentSelectedText = existing.selected_text || '';
    currentSelectionMeta = {{
      selected_language: existing.selected_language || '',
      bilingual_block_id: existing.bilingual_block_id || '',
      original_context: existing.original_context || '',
      translation_context: existing.translation_context || ''
    }};
    currentConceptMeta = {{
      source_anchor: existing.source_anchor || '',
      concept_type: existing.concept_type || '',
      alias_zh: existing.alias_zh || '',
      concept_id: existing.concept_id || ''
    }};
    openPanel(existing);
    const block = blockById(currentBlock);
    if (block) block.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
  }}

  function refreshFeedbackList() {{
    const list = document.getElementById('feedbackList');
    const listSummary = document.getElementById('feedbackListSummary');
    if (!list) return;
    if (listSummary) listSummary.textContent = `Saved annotations (${{feedback.size}})`;
    list.replaceChildren();
    if (!feedback.size) {{
      const empty = document.createElement('p');
      empty.className = 'feedback-empty';
      empty.textContent = 'No saved annotations.';
      list.appendChild(empty);
      return;
    }}
    feedback.forEach((item, key) => {{
      const row = document.createElement('div');
      row.className = 'feedback-row';
      const label = document.createElement('button');
      label.type = 'button';
      label.className = 'feedback-row-label';
      label.textContent = `${{item.status || 'unrated'}} · ${{item.concept || item.selected_text || 'free annotation'}}`;
      label.addEventListener('click', () => openSavedFeedback(key));
      const meta = document.createElement('span');
      meta.className = 'feedback-row-meta';
      meta.textContent = [item.block_id, item.selected_language].filter(Boolean).join(' · ');
      const del = document.createElement('button');
      del.type = 'button';
      del.className = 'feedback-row-delete';
      del.textContent = 'Delete';
      del.addEventListener('click', () => deleteFeedbackItem(key));
      row.append(label, meta, del);
      list.appendChild(row);
    }});
  }}

  function openPanel(existing) {{
    conceptInput.value = existing.concept || '';
    question.value = existing.user_question || '';
    note.value = existing.note || '';
    context.value = existing.source_excerpt || existing.selected_text || '';
    confusionType.value = existing.confusion_type || '';
    explanationStyle.value = existing.explanation_style || '';
    needsExplanation.checked = !!existing.needs_explanation;
    setStatus(existing.status || 'unrated');
    const blockLabel = currentBlock ? `  ·  ${{currentBlock}}` : '';
    conceptLabel.textContent = (existing.concept || 'Free annotation') + blockLabel;
    dock.hidden = false;
    conceptInput.focus();
  }}

  function openFor(mark) {{
    currentConcept = mark.dataset.concept;
    currentBlock = closestBlockId(mark);
    currentKind = 'concept';
    currentSelectionMeta = contextForElement(mark);
    currentConceptMeta = {{
      source_anchor: mark.dataset.sourceAnchor || '',
      concept_type: mark.dataset.conceptType || '',
      alias_zh: mark.dataset.aliasZh || '',
      concept_id: mark.dataset.conceptId || ''
    }};
    currentSourceExcerpt = currentSelectionMeta.excerpt || blockExcerpt(mark);
    currentSelectedText = '';
    const key = feedbackKey(currentConcept, currentBlock, currentKind);
    currentKey = key;
    const existing = feedback.get(key) || {{
      concept: currentConcept,
      status: mark.dataset.status || 'unrated',
      note: '',
      user_question: '',
      confusion_type: '',
      explanation_style: '',
      needs_explanation: false,
      block_id: currentBlock,
      annotation_kind: currentKind,
      source_excerpt: currentSourceExcerpt,
      selected_text: '',
      selected_language: currentSelectionMeta.selected_language || '',
      bilingual_block_id: currentSelectionMeta.bilingual_block_id || '',
      original_context: currentSelectionMeta.original_context || '',
      translation_context: currentSelectionMeta.translation_context || '',
      source_anchor: currentConceptMeta.source_anchor || currentSelectionMeta.bilingual_block_id || currentBlock || '',
      concept_type: currentConceptMeta.concept_type || 'term',
      alias_zh: currentConceptMeta.alias_zh || '',
      concept_id: currentConceptMeta.concept_id || ''
    }};
    openPanel(feedback.get(key) || existing);
  }}

  function openFree() {{
    const selected = rememberSelection();
    currentConcept = selected.text ? selected.text.slice(0, 120) : '';
    currentBlock = selected.blockId || '';
    currentKind = 'freeform';
    currentSourceExcerpt = selected.excerpt || selected.text || '';
    currentSelectedText = selected.text || '';
    currentSelectionMeta = selected;
    currentConceptMeta = {{
      source_anchor: selected.bilingual_block_id || selected.blockId || '',
      concept_type: 'freeform',
      alias_zh: '',
      concept_id: ''
    }};
    const key = feedbackKey(currentConcept || currentSelectedText, currentBlock, currentKind);
    currentKey = key;
    const existing = feedback.get(key) || {{
      concept: currentConcept,
      status: 'unrated',
      note: '',
      user_question: '',
      confusion_type: '',
      explanation_style: '',
      needs_explanation: true,
      block_id: currentBlock,
      annotation_kind: currentKind,
      source_excerpt: currentSourceExcerpt,
      selected_text: currentSelectedText,
      selected_language: selected.selected_language || '',
      bilingual_block_id: selected.bilingual_block_id || '',
      original_context: selected.original_context || '',
      translation_context: selected.translation_context || '',
      source_anchor: currentConceptMeta.source_anchor || '',
      concept_type: currentConceptMeta.concept_type || 'freeform',
      alias_zh: '',
      concept_id: ''
    }};
    openPanel(existing);
  }}

  function closePanel() {{
    dock.hidden = true;
  }}

  function saveCurrent(options) {{
    const shouldClose = !options || options.close !== false;
    const concept = conceptInput.value.trim() || currentConcept || currentSelectedText || 'free annotation';
    const key = feedbackKey(concept, currentBlock, currentKind);
    if (currentKey && currentKey !== key && feedback.has(currentKey)) {{
      feedback.delete(currentKey);
      removeVisualFeedback(currentKey);
    }}
    currentKey = key;
    removeVisualFeedback(key);
    const item = {{
      feedback_id: key,
      concept: concept,
      status: getStatus(),
      note: note.value.trim(),
      user_question: question.value.trim(),
      confusion_type: confusionType.value,
      explanation_style: explanationStyle.value,
      needs_explanation: needsExplanation.checked,
      block_id: currentBlock || '',
      annotation_kind: currentKind,
      source_excerpt: context.value.trim() || currentSourceExcerpt || '',
      selected_text: currentSelectedText || '',
      selected_language: currentSelectionMeta.selected_language || '',
      bilingual_block_id: currentSelectionMeta.bilingual_block_id || '',
      original_context: currentSelectionMeta.original_context || '',
      translation_context: currentSelectionMeta.translation_context || '',
      source_anchor: currentConceptMeta.source_anchor || currentSelectionMeta.bilingual_block_id || currentBlock || '',
      concept_type: currentConceptMeta.concept_type || (currentKind === 'concept' ? 'term' : 'freeform'),
      alias_zh: currentConceptMeta.alias_zh || '',
      concept_id: currentConceptMeta.concept_id || ''
    }};
    feedback.set(key, item);
    showVisualFeedback(key, item);
    document.querySelectorAll('[data-concept]').forEach(el => {{
      if (currentKind !== 'concept' || el.dataset.concept !== currentConcept) return;
      el.dataset.status = getStatus();
      el.classList.remove('mastered', 'known', 'learning', 'unknown', 'unrated');
      el.classList.add(getStatus());
    }});
    refreshSummary();
    if (shouldClose) closePanel();
  }}

  function downloadFeedback() {{
    const blob = new Blob([JSON.stringify(payload(), null, 2)], {{ type: 'application/json;charset=utf-8' }});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'reader_feedback.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }}

  function showExportFallback(text, message) {{
    const fallback = document.getElementById('feedbackExportFallback');
    fallback.value = text;
    fallback.hidden = false;
    summary.textContent = message || 'Feedback JSON is ready below; select and copy it.';
    fallback.focus();
    fallback.select();
  }}

  async function copyFeedback() {{
    const text = JSON.stringify(payload(), null, 2);
    showExportFallback(text, 'Feedback JSON is ready below and will also be copied when clipboard access is available.');
    try {{
      await navigator.clipboard.writeText(text);
      summary.textContent = 'Feedback copied for Codex.';
    }} catch (err) {{
      showExportFallback(text, 'Clipboard access failed. Feedback JSON is ready below; select and copy it.');
    }}
  }}

  document.addEventListener('selectionchange', rememberSelection);
  opener.addEventListener('pointerdown', event => {{
    event.preventDefault();
    rememberSelection();
    openFree();
  }});
  opener.addEventListener('click', event => {{
    event.preventDefault();
    if (dock.hidden) openFree();
  }});
  document.querySelectorAll('.knowledge-gap').forEach(mark => {{
    mark.addEventListener('click', () => openFor(mark));
    mark.addEventListener('keydown', event => {{
      if (event.key === 'Enter' || event.key === ' ') {{
        event.preventDefault();
        openFor(mark);
      }}
    }});
  }});
  statusButtons.forEach(btn => btn.addEventListener('click', () => setStatus(btn.dataset.status)));
  document.getElementById('useSelectedText').addEventListener('click', () => {{
    const selected = rememberSelection();
    if (selected.text) {{
      currentSelectedText = selected.text;
      currentBlock = selected.blockId || currentBlock;
      currentSourceExcerpt = selected.excerpt || selected.text;
      currentSelectionMeta = selected;
      currentConceptMeta.source_anchor = selected.bilingual_block_id || selected.blockId || currentConceptMeta.source_anchor || '';
      context.value = selected.text;
      if (!conceptInput.value.trim()) conceptInput.value = selected.text.slice(0, 120);
    }}
  }});
  document.getElementById('saveFeedback').addEventListener('click', saveCurrent);
  document.getElementById('deleteFeedback').addEventListener('click', () => deleteFeedbackItem(currentKey));
  document.getElementById('downloadFeedback').addEventListener('click', () => {{ saveCurrent({{ close: false }}); downloadFeedback(); }});
  document.getElementById('copyFeedback').addEventListener('click', () => {{ saveCurrent({{ close: false }}); copyFeedback(); }});
  document.getElementById('closeFeedback').addEventListener('click', closePanel);
  document.addEventListener('keydown', event => {{
    if (event.key === 'Escape') closePanel();
  }});
  document.addEventListener('pointerdown', event => {{
    if (dock.hidden) return;
    const target = event.target;
    if (!target || !(target instanceof Element)) return;
    if (dock.contains(target)) return;
    if (target.closest('.knowledge-gap, #openFreeFeedback, .saved-feedback-badge, .feedback-row-label')) return;
    closePanel();
  }});
  refreshSummary();
}}());
</script>'''.replace("__READER_FEEDBACK_SEED__", metadata_json).strip()


def split_top_segments(markdown: str) -> list[tuple[str | None, str]]:
    matches = list(TOP_ANCHOR_RE.finditer(markdown))
    if not matches:
        return [(None, markdown)]
    segments: list[tuple[str | None, str]] = []
    if matches[0].start() > 0:
        segments.append((None, markdown[: matches[0].start()]))
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown)
        segments.append((match.group(1), markdown[match.end() : end]))
    return segments


def extract_label_block(text: str, label: str, next_labels: tuple[str, ...]) -> tuple[str, str]:
    start = re.search(rf'(?ms)^\*\*{re.escape(label)}:\*\*\s*', text)
    if not start:
        return "", text
    content_start = start.end()
    next_positions = []
    for next_label in next_labels:
        match = re.search(rf'(?ms)^\*\*{re.escape(next_label)}:\*\*\s*', text[content_start:])
        if match:
            next_positions.append(content_start + match.start())
    # Explicit labels and anchors delimit canonical fields. A heading inside a
    # field is content, never permission to close a language panel early.
    # Formal compilation rejects field-local headings, but this containment
    # rule also keeps diagnostic inputs from producing escaped DOM content.
    anchor = re.search(r'(?m)^<a\s+id=["\'][^"\']+["\']\s*>\s*</a>\s*$', text[content_start:])
    if anchor:
        next_positions.append(content_start + anchor.start())
    content_end = min(next_positions) if next_positions else len(text)
    return clean_reader_field(text[content_start:content_end]), text[content_end:]


def clean_reader_field(text: object) -> str:
    value = str(text or "")
    value = "".join(ch for ch in value if ord(ch) >= 32 or ch in "\n\r\t")
    value = re.sub(r"([A-Za-z])-\s+([A-Za-z])", r"\1\2", value)
    return value.strip()


def source_page_number(source_text: object) -> int | None:
    match = re.search(r"\bp\.\s*(\d+)\b", str(source_text or ""), re.I)
    if not match:
        return None
    page = int(match.group(1))
    return page if page > 0 else None


def source_page_attribute(source_text: object) -> str:
    page = source_page_number(source_text)
    return f' data-source-page="{page}"' if page else ""


def collect_source_page_manifest(base_dir: Path) -> list[dict]:
    source_map = load_source_map(base_dir)
    pages: list[dict] = []
    for row in source_map.get("pages") or []:
        if not isinstance(row, dict):
            continue
        try:
            page = int(row.get("page"))
        except (TypeError, ValueError):
            continue
        relative = str(row.get("source_page_image") or "").replace("\\", "/")
        if page < 1 or not re.fullmatch(r"assets/source_pages/[A-Za-z0-9._-]+\.(?:png|jpe?g|webp)", relative, re.I):
            continue
        asset = (base_dir / relative).resolve()
        source_root = (base_dir / "assets" / "source_pages").resolve()
        try:
            asset.relative_to(source_root)
        except ValueError:
            continue
        if not asset.is_file():
            continue
        pages.append({"page": page, "src": relative, "sha256": str(row.get("sha256") or "")})
    pages.sort(key=lambda item: item["page"])
    return pages


def build_source_page_viewer(source_pages: list[dict]) -> str:
    if not source_pages:
        return ""
    first = source_pages[0]
    return f'''
<section class="source-page-viewer" id="sourcePageViewer" aria-label="Original paper page viewer">
  <div class="source-page-viewer-head">
    <h2>Original Paper</h2>
    <span id="sourcePageCounter">Page {first['page']} / {len(source_pages)}</span>
  </div>
  <a id="sourcePageOpen" class="source-page-open" href="{html.escape(first['src'], quote=True)}" target="_blank" rel="noopener" title="Open current source page at full size">
    <img id="sourcePageImage" src="{html.escape(first['src'], quote=True)}" alt="Original paper page {first['page']}" loading="eager">
  </a>
  <div class="source-page-actions" aria-label="Source page navigation">
    <button type="button" id="sourcePagePrevious">Previous</button>
    <button type="button" id="sourcePageNext">Next</button>
  </div>
</section>'''.strip()


def build_reader_view_controls(has_source_pages: bool) -> str:
    source_button = (
        '<button type="button" id="toggleSourcePages" aria-pressed="false" aria-expanded="true" '
        'aria-controls="sourcePageViewer">Hide Source Pages</button>'
        if has_source_pages else ""
    )
    return f'''
<div class="reader-view-controls" role="group" aria-label="Reader view controls">
  <button type="button" id="toggleOriginal" aria-pressed="false" aria-expanded="true" aria-controls="readerDocument">Hide Original</button>
  {source_button}
</div>'''.strip()


def reader_view_script(title: str, source_pages: list[dict]) -> str:
    page_json = json.dumps(source_pages, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    storage_suffix = hashlib.sha1(title.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f'''
<script id="readerSourcePages" type="application/json">{page_json}</script>
<script>
(() => {{
  const originalButton = document.getElementById('toggleOriginal');
  const sourceButton = document.getElementById('toggleSourcePages');
  const sourceViewer = document.getElementById('sourcePageViewer');
  const sourceImage = document.getElementById('sourcePageImage');
  const sourceOpen = document.getElementById('sourcePageOpen');
  const sourceCounter = document.getElementById('sourcePageCounter');
  const previousButton = document.getElementById('sourcePagePrevious');
  const nextButton = document.getElementById('sourcePageNext');
  const sourceData = document.getElementById('readerSourcePages');
  const pages = sourceData ? JSON.parse(sourceData.textContent || '[]') : [];
  const pageByNumber = new Map(pages.map((item, index) => [Number(item.page), {{...item, index}}]));
  const storageKey = 'paper.reader.view.{storage_suffix}';
  let state = {{ originalCollapsed: false, sourcePagesCollapsed: false, currentPage: pages.length ? Number(pages[0].page) : null }};

  try {{
    const stored = JSON.parse(localStorage.getItem(storageKey) || 'null');
    if (stored && typeof stored === 'object') state = {{...state, ...stored}};
    else if (window.matchMedia('(max-width: 860px)').matches) state.sourcePagesCollapsed = true;
  }} catch (_error) {{
    if (window.matchMedia('(max-width: 860px)').matches) state.sourcePagesCollapsed = true;
  }}

  function persist() {{
    try {{ localStorage.setItem(storageKey, JSON.stringify(state)); }} catch (_error) {{}}
  }}

  function updatePage(pageNumber, shouldPersist = true) {{
    const page = pageByNumber.get(Number(pageNumber));
    if (!page || !sourceImage || !sourceOpen || !sourceCounter) return;
    state.currentPage = Number(page.page);
    sourceImage.src = page.src;
    sourceImage.alt = `Original paper page ${{page.page}}`;
    sourceOpen.href = page.src;
    sourceCounter.textContent = `Page ${{page.page}} / ${{pages.length}}`;
    if (previousButton) previousButton.disabled = page.index <= 0;
    if (nextButton) nextButton.disabled = page.index >= pages.length - 1;
    if (shouldPersist) persist();
  }}

  function applyState() {{
    document.body.classList.toggle('original-collapsed', Boolean(state.originalCollapsed));
    document.body.classList.toggle('source-pages-collapsed', Boolean(state.sourcePagesCollapsed));
    if (originalButton) {{
      originalButton.setAttribute('aria-pressed', String(Boolean(state.originalCollapsed)));
      originalButton.setAttribute('aria-expanded', String(!state.originalCollapsed));
      originalButton.textContent = state.originalCollapsed ? 'Show Original' : 'Hide Original';
    }}
    if (sourceButton) {{
      sourceButton.setAttribute('aria-pressed', String(Boolean(state.sourcePagesCollapsed)));
      sourceButton.setAttribute('aria-expanded', String(!state.sourcePagesCollapsed));
      sourceButton.textContent = state.sourcePagesCollapsed ? 'Show Source Pages' : 'Hide Source Pages';
    }}
    if (sourceViewer) sourceViewer.setAttribute('aria-hidden', String(Boolean(state.sourcePagesCollapsed)));
    updatePage(state.currentPage, false);
  }}

  originalButton?.addEventListener('click', () => {{
    state.originalCollapsed = !state.originalCollapsed;
    applyState();
    persist();
  }});
  sourceButton?.addEventListener('click', () => {{
    state.sourcePagesCollapsed = !state.sourcePagesCollapsed;
    applyState();
    persist();
  }});
  previousButton?.addEventListener('click', () => {{
    const current = pageByNumber.get(Number(state.currentPage));
    if (current && current.index > 0) updatePage(pages[current.index - 1].page);
  }});
  nextButton?.addEventListener('click', () => {{
    const current = pageByNumber.get(Number(state.currentPage));
    if (current && current.index < pages.length - 1) updatePage(pages[current.index + 1].page);
  }});

  document.addEventListener('click', event => {{
    const sourceBlock = event.target instanceof Element ? event.target.closest('[data-source-page]') : null;
    if (sourceBlock) updatePage(sourceBlock.dataset.sourcePage);
  }});

  const sourceBlocks = [...document.querySelectorAll('[data-source-page]')];
  if ('IntersectionObserver' in window && sourceBlocks.length) {{
    const visible = new Map();
    const observer = new IntersectionObserver(entries => {{
      entries.forEach(entry => {{
        if (entry.isIntersecting) visible.set(entry.target, entry.intersectionRatio);
        else visible.delete(entry.target);
      }});
      const current = [...visible.entries()].sort((a, b) => b[1] - a[1])[0];
      if (current) updatePage(current[0].dataset.sourcePage, false);
    }}, {{ rootMargin: '-15% 0px -55% 0px', threshold: [0.05, 0.25, 0.5, 0.75] }});
    sourceBlocks.forEach(block => observer.observe(block));
  }}

  applyState();
}})();
</script>'''.strip()


def parse_bilingual_segment(segment: str) -> tuple[str, str, str, str] | None:
    source, rest = extract_label_block(segment, "Source", ("Original",))
    original, rest = extract_label_block(rest, "Original", ("中文", "注释", "Notes"))
    chinese, rest = extract_label_block(rest, "中文", ("注释", "Notes"))
    notes = ""
    if rest.strip():
        notes, rest = extract_label_block(rest, "注释", ("Notes",))
        if not notes:
            notes, rest = extract_label_block(rest, "Notes", ())
    if source and original and chinese:
        return source, original, chinese, notes
    return None


def render_bilingual_segment(anchor: str | None, segment: str, base_dir: Path, embed_assets: bool, warnings: list[str]) -> str | None:
    parsed = parse_bilingual_segment(segment)
    if not parsed:
        return None
    source, original, chinese, notes = parsed
    block_id = anchor or (source.split()[-1] if source else "source-block")
    notes_html = ""
    section_class = "bilingual-block"
    if notes:
        section_class += " has-notes"
        notes_html = f'''
    <article class="lang-panel reader-notes">
    <h3>知识点与阅读提示</h3>
    {markdown_blocks(notes, base_dir, embed_assets, warnings)}
    </article>'''
    return f'''
<section class="{section_class}" id="{html.escape(block_id, quote=True)}"{source_page_attribute(source)}>
  <div class="block-source"><span>Source</span> {markdown_inline(source, base_dir, embed_assets, warnings)}</div>
  <div class="pair-grid">
    <article class="lang-panel original"><h3>Original</h3>{markdown_blocks(original, base_dir, embed_assets, warnings)}</article>
    <article class="lang-panel translation"><h3>中文</h3>{markdown_blocks(chinese, base_dir, embed_assets, warnings)}</article>
    {notes_html}
  </div>
</section>'''.strip()


def render_reference_segment(anchor: str | None, segment: str, base_dir: Path, embed_assets: bool, warnings: list[str]) -> str | None:
    """Render bibliography evidence as one original-only panel, never as a translation pair."""
    source, rest = extract_label_block(segment, "Source", (REFERENCE_LIST_LABEL, "Original"))
    references, _ = extract_label_block(rest, REFERENCE_LIST_LABEL, ())
    if not source or not references:
        return None
    block_id = anchor or (source.split()[-1] if source else "reference")
    return f'''
<section class="reference-block" id="{html.escape(block_id, quote=True)}"{source_page_attribute(source)}>
  <div class="block-source"><span>Source</span> {markdown_inline(source, base_dir, embed_assets, warnings)}</div>
  <article class="reference-panel"><h3>References · Original</h3>{markdown_blocks(references, base_dir, embed_assets, warnings)}</article>
</section>'''.strip()


def parse_algorithm_segment(segment: str) -> dict[str, str] | None:
    if not ALGORITHM_RE.search(segment):
        return None
    title_match = re.search(r'(?m)^#{1,6}\s+(.+?)\s*$', segment)
    title = title_match.group(1).strip() if title_match else "Algorithm"
    placed, _ = extract_label_block(segment, "Placed near", ("Source", "Original algorithm", "中文算法", "Chinese algorithm", "Reading note"))
    source, _ = extract_label_block(segment, "Source", ("Original algorithm", "中文算法", "Chinese algorithm", "Reading note"))
    original, _ = extract_label_block(segment, "Original algorithm", ("中文算法", "Chinese algorithm", "Reading note"))
    chinese, _ = extract_label_block(segment, "中文算法", ("Reading note",))
    if not chinese:
        chinese, _ = extract_label_block(segment, "Chinese algorithm", ("Reading note",))
    note, _ = extract_label_block(segment, "Reading note", ())
    if original and chinese:
        return {"title": title, "placed": placed, "source": source, "original": original, "chinese": chinese, "note": note}
    return None


def render_algorithm_steps(text: str, base_dir: Path, embed_assets: bool, warnings: list[str]) -> str:
    rows = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```"):
            continue
        match = ALGORITHM_LINE_RE.match(line)
        if match:
            rows.append(
                "<li>"
                f"<span class=\"alg-line-no\">{html.escape(match.group(1))}</span>"
                f"<span class=\"alg-line-text\">{markdown_inline(match.group(2), base_dir, embed_assets, warnings)}</span>"
                "</li>"
            )
        else:
            rows.append(f"<li class=\"alg-comment\"><span class=\"alg-line-text\">{markdown_inline(line, base_dir, embed_assets, warnings)}</span></li>")
    return '<ol class="algorithm-lines">' + "".join(rows) + "</ol>"


def render_algorithm_card(anchor: str | None, segment: str, base_dir: Path, embed_assets: bool, warnings: list[str]) -> str | None:
    parsed = parse_algorithm_segment(segment)
    if not parsed:
        return None
    block_id = anchor or slugify(parsed["title"], "algorithm")
    meta = " · ".join(item for item in (parsed.get("placed"), parsed.get("source")) if item)
    note_html = f'<aside class="algorithm-note">{markdown_blocks(parsed["note"], base_dir, embed_assets, warnings)}</aside>' if parsed.get("note") else ""
    return f'''
<section class="algorithm-card" id="{html.escape(block_id, quote=True)}"{source_page_attribute(parsed.get('source') or parsed.get('placed'))}>
  <h3>{markdown_inline(parsed["title"], base_dir, embed_assets, warnings)}</h3>
  {f'<div class="block-source"><span>Source</span> {markdown_inline(meta, base_dir, embed_assets, warnings)}</div>' if meta else ''}
  <div class="pair-grid">
    <article class="lang-panel original"><h3>Original Algorithm</h3>{render_algorithm_steps(parsed["original"], base_dir, embed_assets, warnings)}</article>
    <article class="lang-panel translation"><h3>中文算法</h3>{render_algorithm_steps(parsed["chinese"], base_dir, embed_assets, warnings)}</article>
    {note_html}
  </div>
</section>'''.strip()


def render_document(markdown: str, base_dir: Path, embed_assets: bool, warnings: list[str]) -> tuple[str, list[tuple[int, str, str]]]:
    html_parts: list[str] = []
    toc: list[tuple[int, str, str]] = []

    for anchor, segment in split_top_segments(markdown):
        if not segment.strip():
            continue

        algorithm = render_algorithm_card(anchor, segment, base_dir, embed_assets, warnings)
        if algorithm:
            html_parts.append(algorithm)
            continue

        reference = render_reference_segment(anchor, segment, base_dir, embed_assets, warnings)
        if reference:
            html_parts.append(reference)
            continue

        bilingual = render_bilingual_segment(anchor, segment, base_dir, embed_assets, warnings)
        if bilingual:
            html_parts.append(bilingual)
            continue

        heading_match = HEADING_RE.search(segment.strip().splitlines()[0] if segment.strip().splitlines() else "")
        is_figure_or_table = bool(anchor and re.match(r'^[FT]\d+', anchor)) or bool(IMAGE_RE.search(segment))
        if is_figure_or_table:
            block_id = anchor or f"figure-{len(html_parts) + 1}"
            html_parts.append(
                f'<figure class="figure-card" id="{html.escape(block_id, quote=True)}"'
                f'{source_page_attribute(segment)}>{markdown_blocks(segment, base_dir, embed_assets, warnings)}</figure>'
            )
            continue

        body, local_toc = render_tokens(split_tokens(segment), base_dir, embed_assets, warnings)
        for level, hid, text in local_toc:
            toc.append((level, hid, text))
        if anchor and body and f'id="{html.escape(anchor, quote=True)}"' not in body:
            body = f'<span id="{html.escape(anchor, quote=True)}"></span>\n{body}'
        html_parts.append(body)

        if heading_match and anchor:
            toc.append((len(heading_match.group(1)), anchor, heading_match.group(2)))

    return "\n".join(part for part in html_parts if part.strip()), toc


def render_tokens(tokens: list[Token], base_dir: Path, embed_assets: bool, warnings: list[str]) -> tuple[str, list[tuple[int, str, str]]]:
    html_parts: list[str] = []
    toc: list[tuple[int, str, str]] = []
    i = 0
    last_anchor: str | None = None

    while i < len(tokens):
        token = tokens[i]

        if token.kind == "anchor":
            last_anchor = token.anchor
            i += 1
            continue

        anchor = token.anchor or last_anchor
        last_anchor = None

        if token.kind == "heading":
            level = min(max(token.level, 1), 4)
            hid = anchor or slugify(token.text, f"section-{len(toc) + 1}")
            toc.append((level, hid, re.sub(r'<[^>]+>', '', token.text)))
            html_parts.append(f'<section class="section" id="{html.escape(hid, quote=True)}">')
            html_parts.append(f'<h{level}>{markdown_inline(token.text, base_dir, embed_assets, warnings)}</h{level}>')
            html_parts.append("</section>")
            i += 1
            continue

        if token.kind == "table":
            block_id = anchor or f"table-{i}"
            html_parts.append(f'<section class="md-table" id="{html.escape(block_id, quote=True)}">{render_table(token.text)}</section>')
            i += 1
            continue

        if token.kind != "paragraph":
            i += 1
            continue

        text = token.text
        if starts_label(text, "Source") and i + 2 < len(tokens) and starts_label(tokens[i + 1].text, "Original") and starts_label(tokens[i + 2].text, "中文"):
            source = strip_label(text, "Source")
            original = strip_label(tokens[i + 1].text, "Original")
            chinese = strip_label(tokens[i + 2].text, "中文")
            notes = ""
            consumed = 3
            if i + 3 < len(tokens) and starts_label(tokens[i + 3].text, "注释"):
                notes = strip_label(tokens[i + 3].text, "注释")
                consumed = 4
            block_id = (anchor or source.split()[-1]) if source else f"block-{i}"
            notes_html = ""
            section_class = "bilingual-block"
            if notes:
                section_class += " has-notes"
                notes_html = f'''
    <article class="lang-panel reader-notes">
    <h3>知识点与阅读提示</h3>
    {markdown_blocks(notes, base_dir, embed_assets, warnings)}
    </article>'''
            html_parts.append(
                f'''
<section class="{section_class}" id="{html.escape(block_id, quote=True)}">
  <div class="block-source"><span>Source</span> {markdown_inline(source, base_dir, embed_assets, warnings)}</div>
  <div class="pair-grid">
    <article class="lang-panel original"><h3>Original</h3>{markdown_blocks(original, base_dir, embed_assets, warnings)}</article>
    <article class="lang-panel translation"><h3>中文</h3>{markdown_blocks(chinese, base_dir, embed_assets, warnings)}</article>
    {notes_html}
  </div>
</section>'''.strip()
            )
            i += consumed
            continue

        if IMAGE_RE.search(text):
            block_id = anchor or f"figure-{i}"
            html_parts.append(f'<figure class="figure-card" id="{html.escape(block_id, quote=True)}">{markdown_blocks(text, base_dir, embed_assets, warnings)}</figure>')
            i += 1
            continue

        label_match = re.match(r'^\*\*([^:*]+):\*\*\s*(.*)', text, flags=re.S)
        if label_match:
            label = label_match.group(1)
            body = label_match.group(2)
            class_name = slugify(label, "note")
            html_parts.append(
                f'<aside class="label-card {class_name}"' + (f' id="{html.escape(anchor, quote=True)}"' if anchor else "") + ">"
                f'<strong>{html.escape(label)}</strong>{markdown_blocks(body, base_dir, embed_assets, warnings)}</aside>'
            )
            i += 1
            continue

        html_parts.append(
            f'<section class="prose"' + (f' id="{html.escape(anchor, quote=True)}"' if anchor else "") + f'>{markdown_blocks(text, base_dir, embed_assets, warnings)}</section>'
        )
        i += 1

    return "\n".join(html_parts), toc


def css() -> str:
    return reader_theme_css() + """
:root {
  --bg: var(--reader-bg);
  --paper: var(--reader-card-bg);
  --ink: var(--reader-text);
  --muted: var(--reader-muted);
  --line: var(--reader-border);
  --accent: var(--reader-link);
  --accent-soft: var(--reader-accent-soft);
  --cn: var(--reader-cn);
  --warn: var(--reader-warn);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: Arial, "Noto Sans SC", "Microsoft YaHei", sans-serif;
  color: var(--ink);
  background: var(--bg);
  line-height: 1.62;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.site-header {
  background: var(--paper);
  border-bottom: 1px solid var(--line);
  padding: 28px max(24px, calc((100vw - 1480px) / 2)) 22px;
}
.site-header h1 { margin: 0 0 10px; font-size: clamp(1.6rem, 3vw, 2.6rem); line-height: 1.15; letter-spacing: 0; }
.meta-row { display: flex; flex-wrap: wrap; gap: 8px; color: var(--muted); font-size: .95rem; }
.badge { border: 1px solid var(--line); background: var(--paper); border-radius: 999px; padding: 4px 10px; }
.layout {
  display: grid;
  grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 24px;
  max-width: 1760px;
  margin: 0 auto;
  padding: 24px;
}
.reader-sidebar {
  position: sticky;
  top: 16px;
  align-self: start;
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-height: calc(100vh - 32px);
  min-width: 0;
}
.toc {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
  flex: 1 1 auto;
  min-height: 120px;
  overflow: auto;
}
.toc h2 { margin: 0 0 10px; font-size: 1rem; }
.toc a { display: block; padding: 6px 0; color: var(--ink); font-size: .92rem; }
.toc .level-3 { padding-left: 12px; }
.toc .level-4 { padding-left: 24px; }
.reader-view-controls { display: inline-flex; flex-wrap: wrap; gap: 8px; margin-left: auto; }
.reader-view-controls button, .source-page-actions button {
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--reader-panel-bg);
  color: var(--ink);
  padding: 6px 9px;
  font: inherit;
  cursor: pointer;
}
.reader-view-controls button:hover, .source-page-actions button:hover { border-color: var(--accent); }
.reader-view-controls button[aria-pressed="true"] { background: var(--accent-soft); border-color: var(--accent); }
.source-page-viewer {
  flex: 0 1 auto;
  min-height: 0;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
}
.source-page-viewer-head { display: flex; align-items: baseline; justify-content: space-between; gap: 10px; margin-bottom: 8px; }
.source-page-viewer-head h2 { margin: 0; font-size: 1rem; letter-spacing: 0; }
.source-page-viewer-head span { color: var(--muted); font-size: .82rem; white-space: nowrap; }
.source-page-open {
  display: block;
  max-height: min(52vh, 660px);
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--reader-math-bg);
}
.source-page-open img { display: block; width: 100%; height: auto; margin: 0; }
.source-page-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }
.source-page-actions button:disabled { opacity: .45; cursor: not-allowed; }
body.source-pages-collapsed .source-page-viewer { display: none; }
body.source-pages-collapsed .layout { grid-template-columns: minmax(190px, 260px) minmax(0, 1fr); max-width: 1600px; }
body.original-collapsed .bilingual-block .lang-panel.original,
body.original-collapsed .algorithm-card .lang-panel.original { display: none; }
body.original-collapsed .bilingual-block .pair-grid,
body.original-collapsed .algorithm-card .pair-grid { grid-template-columns: minmax(0, 1fr); }
body.original-collapsed .bilingual-block.has-notes .pair-grid {
  grid-template-columns: minmax(0, 1fr) minmax(260px, .85fr);
}
main { min-width: 0; }
.section, .prose, .md-table, .bilingual-block, .reference-block, .figure-card, .label-card, .algorithm-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 8px;
  margin: 0 0 16px;
  padding: 18px;
}
.section h1, .section h2, .section h3, .section h4 { margin: 0; letter-spacing: 0; }
.block-source {
  color: var(--muted);
  font-size: .9rem;
  margin-bottom: 12px;
}
.block-source span {
  color: var(--accent);
  font-weight: 700;
  margin-right: 6px;
}
.pair-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 14px;
}
.bilingual-block.has-notes .pair-grid {
  grid-template-columns: minmax(0, 1.05fr) minmax(0, .95fr) minmax(260px, .85fr);
}
.lang-panel {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
  background: var(--reader-panel-bg);
  min-width: 0;
}
.lang-panel h3 {
  margin: 0 0 8px;
  font-size: .92rem;
  color: var(--muted);
  letter-spacing: 0;
}
.translation h3 { color: var(--cn); }
.reader-notes {
  background: var(--reader-note-bg);
  border-color: var(--reader-note-border);
}
.reader-notes h3 { color: var(--reader-warn); }
.reader-notes ul, .reader-notes ol { margin-top: 8px; padding-left: 20px; }
.reader-notes li { margin: 0 0 6px; }
.lang-panel p, .label-card p, .prose p { margin: 0 0 10px; }
.lang-panel p:last-child, .label-card p:last-child, .prose p:last-child { margin-bottom: 0; }
.reference-panel { padding: 16px 18px; border: 1px solid var(--border); border-radius: 12px; background: var(--card); }
.reference-panel h3 { margin: 0 0 10px; font-size: .92rem; letter-spacing: .03em; color: var(--muted); }
.math-display {
  overflow-x: auto;
  background: var(--reader-math-bg);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
  margin: 10px 0;
  font-family: "Cambria Math", "Times New Roman", serif;
}
.math-inline {
  font-family: "Cambria Math", "Times New Roman", serif;
}
.math-display mjx-container {
  margin: 0 !important;
}
.figure-card img {
  display: block;
  max-width: 100%;
  width: auto;
  height: auto;
  object-fit: contain;
  margin: 8px auto 14px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--reader-math-bg);
}
.figure-card {
  overflow: visible;
}
.figure-card .table-wrap {
  overflow-x: auto;
  overflow-y: visible;
}
.algorithm-card h3 {
  margin: 0 0 10px;
  letter-spacing: 0;
}
.algorithm-lines {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 6px;
  font-family: "Cascadia Mono", Consolas, "Courier New", monospace;
  font-size: .92rem;
}
.algorithm-lines li {
  display: grid;
  grid-template-columns: 3.2em minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  border-bottom: 1px solid #eef2f7;
  padding: 4px 0;
}
.alg-line-no {
  color: var(--muted);
  text-align: right;
  user-select: none;
}
.alg-comment {
  color: var(--muted);
}
.algorithm-note {
  border: 1px solid var(--reader-note-border);
  border-radius: 8px;
  background: var(--reader-note-bg);
  color: var(--ink);
  padding: 14px;
}
.label-card strong {
  display: inline-block;
  color: var(--accent);
  margin-right: 8px;
}
.reading-note strong, .中文图注 strong { color: var(--cn); }
.knowledge-panel {
  background: var(--reader-note-bg);
  color: var(--ink);
  border: 1px solid var(--reader-note-border);
  border-radius: 8px;
  margin: 0 0 16px;
  padding: 18px;
}
.knowledge-panel h2 { margin: 0 0 8px; letter-spacing: 0; }
.paper-summary {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 8px;
  margin: 0 0 16px;
  padding: 20px;
}
.paper-summary h2 { margin: 0 0 12px; letter-spacing: 0; }
.paper-summary-overview {
  border-left: 4px solid var(--accent);
  background: var(--reader-note-bg);
  border-radius: 0 8px 8px 0;
  padding: 14px 16px;
  margin-bottom: 18px;
}
.paper-summary-overview p { margin: 0 0 10px; }
.paper-summary-section { margin-top: 18px; }
.paper-summary-section h3 { margin: 0 0 8px; font-size: 1.05rem; letter-spacing: 0; }
.paper-summary-section ul, .paper-summary-section ol { margin: 0; padding-left: 24px; }
.paper-summary-section li { margin: 0 0 10px; }
.summary-sources { display: inline-flex; flex-wrap: wrap; gap: 5px; margin-left: 8px; vertical-align: middle; }
.summary-source {
  display: inline-block;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--accent-soft);
  padding: 1px 7px;
  font-size: .78rem;
  line-height: 1.5;
}
.profile-path { color: var(--muted); font-size: .9rem; }
.status {
  display: inline-block;
  border-radius: 999px;
  padding: 2px 8px;
  border: 1px solid var(--line);
  font-size: .85rem;
}
.status.unknown, .knowledge-gap.unknown { background: var(--reader-status-unknown-bg); border-color: var(--reader-status-unknown-border); }
.status.learning, .knowledge-gap.learning { background: var(--reader-status-learning-bg); border-color: var(--reader-status-learning-border); }
.status.unrated, .knowledge-gap.unrated { background: var(--reader-status-unrated-bg); border-color: var(--reader-status-unrated-border); }
.knowledge-gap {
  color: var(--reader-highlight-text);
  border-radius: 4px;
  padding: 0 2px;
  border-bottom: 2px solid currentColor;
  cursor: pointer;
}
.knowledge-gap:focus {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.saved-free-annotation {
  background: var(--reader-status-saved-bg);
  color: var(--reader-status-saved-text);
  border-bottom: 2px solid var(--reader-status-saved-border);
  border-radius: 4px;
  padding: 0 2px;
}
.saved-feedback-tray {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 0 0 10px;
}
.saved-feedback-badge {
  border: 1px solid var(--reader-status-saved-border);
  border-radius: 999px;
  background: var(--reader-status-saved-bg);
  color: var(--reader-status-saved-text);
  padding: 3px 8px;
  font-size: .82rem;
  cursor: pointer;
}
.saved-feedback-badge:hover {
  border-color: var(--reader-status-saved-border);
}
.feedback-dock {
  position: fixed;
  right: 18px;
  bottom: 18px;
  width: min(420px, calc(100vw - 28px));
  max-height: calc(100vh - 36px);
  overflow: auto;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: 0 18px 50px rgba(23, 32, 51, .18);
  padding: 14px;
  z-index: 20;
}
.feedback-dock[hidden] { display: none; }
.feedback-opener {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 19;
  border: 1px solid var(--accent);
  border-radius: 8px;
  background: var(--accent);
  color: var(--reader-primary-text);
  padding: 9px 12px;
  box-shadow: 0 12px 28px rgba(31, 111, 235, .2);
  cursor: pointer;
}
.feedback-dock h2 {
  margin: 0 0 8px;
  font-size: 1rem;
  letter-spacing: 0;
}
.feedback-dock .selected-concept {
  font-weight: 700;
  margin-bottom: 8px;
}
.field-label {
  display: block;
  margin: 8px 0 4px;
  color: var(--muted);
  font-size: .88rem;
  font-weight: 700;
}
.feedback-dock input[type="text"], .feedback-dock select {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--reader-panel-bg);
  color: var(--ink);
  padding: 7px 8px;
  font: inherit;
}
.status-buttons {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 6px;
  margin: 10px 0;
}
.status-buttons button, .feedback-actions button {
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--reader-panel-bg);
  color: var(--ink);
  padding: 7px 8px;
  cursor: pointer;
}
.status-buttons button.active {
  background: var(--accent);
  color: var(--reader-primary-text);
  border-color: var(--accent);
}
.feedback-dock textarea {
  width: 100%;
  min-height: 72px;
  resize: vertical;
  border: 1px solid var(--line);
  background: var(--reader-panel-bg);
  color: var(--ink);
  border-radius: 6px;
  padding: 8px;
  font: inherit;
}
.feedback-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.feedback-actions .primary {
  background: var(--accent);
  color: var(--reader-primary-text);
  border-color: var(--accent);
}
.feedback-summary {
  color: var(--muted);
  font-size: .9rem;
  margin-top: 8px;
}
.feedback-export-fallback {
  width: 100%;
  min-height: 140px;
  margin-top: 8px;
  font-family: "Cascadia Mono", Consolas, "Courier New", monospace;
  font-size: .82rem;
}
.feedback-list-wrap {
  border-top: 1px solid var(--line);
  margin-top: 10px;
  padding-top: 8px;
}
.feedback-list-wrap summary {
  font-weight: 700;
  font-size: .9rem;
  cursor: pointer;
  color: var(--ink);
  list-style-position: inside;
}
.feedback-list {
  max-height: 180px;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-right: 4px;
  margin-top: 6px;
}
.feedback-empty {
  color: var(--muted);
  font-size: .88rem;
  margin: 0;
}
.feedback-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 6px;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 6px;
  margin-top: 6px;
  background: var(--reader-panel-bg);
}
.feedback-row-label {
  border: 0;
  background: transparent;
  color: var(--ink);
  padding: 0;
  text-align: left;
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.feedback-row-meta {
  color: var(--muted);
  font-size: .78rem;
  white-space: nowrap;
}
.feedback-row-delete {
  border: 1px solid var(--reader-danger-border);
  border-radius: 6px;
  background: var(--reader-danger-bg);
  color: var(--reader-danger-text);
  padding: 4px 6px;
  cursor: pointer;
}
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: .95rem; }
th, td { border-bottom: 1px solid var(--line); padding: 9px 10px; text-align: left; vertical-align: top; letter-spacing: 0; }
th { background: var(--accent-soft); font-weight: 700; }
code {
  background: var(--reader-code-bg);
  color: var(--ink);
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 0 3px;
}
.footer {
  max-width: 1480px;
  margin: 0 auto 28px;
  padding: 0 24px;
  color: var(--muted);
  font-size: .9rem;
}
@media (max-width: 860px) {
  .layout { display: block; padding: 14px; }
  .reader-sidebar { position: static; display: block; max-height: none; margin-bottom: 14px; }
  .source-page-viewer { margin-bottom: 14px; }
  .source-page-open { max-height: 60vh; }
  .toc { max-height: none; }
  .pair-grid, .bilingual-block.has-notes .pair-grid { grid-template-columns: 1fr; }
  body.original-collapsed .bilingual-block.has-notes .pair-grid { grid-template-columns: 1fr; }
  .site-header { padding: 22px 14px; }
  .reader-view-controls { width: 100%; margin-left: 0; }
}
@media print {
  body { background: #fff; }
  .site-header, .section, .prose, .md-table, .bilingual-block, .reference-block, .figure-card, .label-card, .algorithm-card { border-color: #c8ced8; box-shadow: none; }
  .layout { display: block; max-width: none; padding: 0; }
  .reader-sidebar { position: static; display: block; max-height: none; }
  .toc { max-height: none; break-after: page; }
  .source-page-viewer, .reader-view-controls { display: none !important; }
  body.original-collapsed .bilingual-block .lang-panel.original,
  body.original-collapsed .algorithm-card .lang-panel.original { display: block !important; }
  body.original-collapsed .pair-grid,
  body.original-collapsed .algorithm-card .pair-grid { grid-template-columns: 1fr 1fr !important; }
  body.original-collapsed .bilingual-block.has-notes .pair-grid { grid-template-columns: 1.05fr .95fr minmax(260px, .85fr) !important; }
  .bilingual-block, .figure-card, .md-table { break-inside: avoid; }
  .feedback-dock, .feedback-opener { display: none !important; }
  a { color: inherit; text-decoration: none; }
  @page { size: A4; margin: 16mm 14mm; }
}
"""


def math_support(math_renderer: str, mathjax_url: str) -> str:
    if math_renderer == "none":
        return ""
    escaped_url = html.escape(mathjax_url, quote=True)
    return """
  <script>
    window.MathJax = {
      tex: {
        inlineMath: [['\\\\(', '\\\\)'], ['$', '$']],
        displayMath: [['\\\\[', '\\\\]'], ['$$', '$$']],
        processEscapes: true,
        tags: 'ams'
      },
      options: {
        skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code']
      },
      startup: {
        ready: function () {
          MathJax.startup.defaultReady();
          document.documentElement.classList.add('math-ready');
        }
      }
    };
  </script>
  <script async id="MathJax-script" src="__MATHJAX_URL__"></script>
""".replace("__MATHJAX_URL__", escaped_url).strip()


def build_html(
    title: str,
    body_html: str,
    toc: list[tuple[int, str, str]],
    meta: dict,
    base_dir: Path,
    source_pages: list[dict] | None = None,
    summary_panel: str = "",
    knowledge_panel: str = "",
    profile_path: Path | None = None,
    feedback_ui: str = "",
    math_renderer: str = "mathjax",
    mathjax_url: str = DEFAULT_MATHJAX_URL,
) -> str:
    source_pages = source_pages or []
    toc_rows = list(toc[:80])
    if knowledge_panel:
        toc_rows.insert(0, (2, "personal-knowledge-boundary", "Paper Concept Ledger / Personal Knowledge Boundary"))
    if summary_panel:
        toc_rows.insert(0, (2, "paper-summary", "Paper Summary / 论文总结"))
    toc_links = "\n".join(
        f'<a class="level-{level}" href="#{html.escape(anchor, quote=True)}">{html.escape(text)}</a>'
        for level, anchor, text in toc_rows
    )
    companion_links = []
    for name in ("source_map.json", "translation_notes.md"):
        if (base_dir / name).exists():
            companion_links.append(f'<span class="badge"><a href="{name}">{name}</a></span>')
    if profile_path:
        companion_links.append(f'<span class="badge"><a href="#personal-knowledge-boundary">learner profile</a></span>')
    companions = "\n".join(companion_links)
    author_text = ", ".join(meta.get("authors", [])) if isinstance(meta.get("authors"), list) else meta.get("authors", "")
    source_type = meta.get("source_type") or meta.get("source_format") or "nature-reader Markdown"
    source_page_viewer = build_source_page_viewer(source_pages)
    view_controls = build_reader_view_controls(bool(source_pages))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  {reader_theme_boot_script()}
  <style>{css()}</style>
  {math_support(math_renderer, mathjax_url)}
</head>
<body>
  <header class="site-header">
    <h1>{html.escape(title)}</h1>
    <div class="meta-row">
      <span class="badge">Chinese-English reader</span>
      <span class="badge">{html.escape(source_type)}</span>
      {f'<span class="badge">{html.escape(author_text)}</span>' if author_text else ''}
      {companions}
      {reader_theme_control()}
      {view_controls}
    </div>
  </header>
  <div class="layout">
    <aside class="reader-sidebar" aria-label="Reader sidebar">
      {source_page_viewer}
      <nav class="toc" aria-label="Table of contents">
        <h2>Contents</h2>
        {toc_links or '<p>No headings detected.</p>'}
      </nav>
    </aside>
    <main>
      <article id="readerDocument">
        {summary_panel}
        {knowledge_panel}
        {body_html}
      </article>
    </main>
  </div>
  {feedback_ui}
  {reader_theme_script()}
  {reader_view_script(title, source_pages)}
  <footer class="footer">Generated from a nature-reader Markdown bundle. Source anchors are preserved for traceability.</footer>
</body>
</html>
"""


def validate_generated_html(html_text: str, concepts: list[dict], math_renderer: str) -> list[str]:
    return validate_generated_reader_html(html_text, concepts, math_renderer)
    issues: list[str] = []
    if math_renderer == "mathjax" and 'id="MathJax-script"' not in html_text:
        issues.append("MathJax script is missing")
    if "feedbackDock" in html_text:
        if "function closePanel()" not in html_text:
            issues.append("feedback UI closePanel handler is missing")
        save_match = re.search(r"function saveCurrent\(\) \{([\s\S]*?)\n  \}", html_text)
        if not save_match or "closePanel();" not in save_match.group(1):
            issues.append("Save mark does not close the annotate panel")
    required_attrs = ("data-concept=", "data-concept-id=", "data-status=", "data-source-anchor=", "data-concept-type=", "data-alias-zh=", "title=")
    mark_count = len(re.findall(r'<mark\s+class="knowledge-gap\b', html_text))
    if concepts and mark_count == 0:
        issues.append("concept ledger exists but HTML contains no knowledge marks")
    for mark in re.findall(r'<mark\s+class="knowledge-gap\b[^>]*>', html_text):
        for attr in required_attrs:
            if attr not in mark:
                issues.append(f"knowledge mark missing {attr.rstrip('=')}: {mark[:160]}")
                break
    for note in re.findall(r'<article class="lang-panel reader-notes">([\s\S]*?)</article>', html_text, re.I):
        if re.search(r"<\s*/?\s*(h1|h2|section|script|style)\b", note, re.I):
            issues.append("reader-notes contains structural HTML pollution")
        if re.search(r"Source Page Index|source page index|assets/source_pages", note, re.I):
            issues.append("reader-notes contains source page/index pollution")
    return issues


def infer_title(markdown: str, meta: dict, override: str | None) -> str:
    if override:
        return override
    if meta.get("title"):
        return str(meta["title"])
    for line in markdown.splitlines():
        match = re.match(r'^#\s+(.+)', line)
        if match:
            return re.sub(r'<[^>]+>', '', match.group(1)).strip()
    return "Chinese-English Paper Reader"


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Path to paper.md or a nature-reader output directory")
    parser.add_argument("--output", "-o", help="Output HTML path. Defaults to reader_interactive.html beside paper.md")
    parser.add_argument("--title", help="Override HTML title")
    parser.add_argument("--no-embed-assets", action="store_true", help="Keep image links instead of embedding local assets")
    parser.add_argument("--agent-dir", help="Project .agents directory. Defaults to the nearest parent .agents directory")
    parser.add_argument("--profile", help="Path to learner knowledge_profile.json")
    parser.add_argument("--no-knowledge-annotations", action="store_true", help="Disable personal knowledge highlighting even if a profile exists")
    parser.add_argument("--no-feedback-ui", action="store_true", help="Disable clickable concept feedback controls")
    parser.add_argument("--math-renderer", choices=("mathjax", "none"), default="mathjax", help="Render TeX formulas with MathJax, or keep TeX source with none")
    parser.add_argument("--mathjax-url", default=DEFAULT_MATHJAX_URL, help="MathJax script URL or local path used when --math-renderer mathjax")
    parser.add_argument("--allow-draft-translation", action="store_true", help="Allow draft/paraphrase Chinese columns; output should be named as a draft preview")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    input_path = Path(args.input).expanduser().resolve()
    md_path, base_dir = read_input(input_path)
    markdown = md_path.read_text(encoding="utf-8")
    warnings: list[str] = []
    output_path = Path(args.output).expanduser().resolve() if args.output else base_dir / "reader_interactive.html"

    forbidden_flags: list[str] = []
    if args.allow_draft_translation:
        forbidden_flags.append("--allow-draft-translation")
    if args.no_feedback_ui:
        forbidden_flags.append("--no-feedback-ui")
    if args.no_knowledge_annotations:
        forbidden_flags.append("--no-knowledge-annotations")
    if args.math_renderer == "none":
        forbidden_flags.append("--math-renderer none")
    if forbidden_flags:
        issues = ["formal reader_interactive.html builds reject downgrade flags: " + ", ".join(forbidden_flags)]
        write_artifact_manifest(base_dir, output_path, "stale_or_failed", issues)
        print(issues[0], file=sys.stderr)
        return 2

    agent_dir = find_agent_dir(base_dir, args.agent_dir)
    profile_path = Path(args.profile).expanduser().resolve() if args.profile else None
    if profile_path is None and agent_dir is not None:
        profile_path = agent_dir / "reader-learner" / "knowledge_profile.json"

    try:
        compile_result = compile_reader_wiki(
            base_dir,
            strict=True,
            profile_path=profile_path if profile_path and profile_path.exists() else None,
        )
    except ValueError as exc:
        write_artifact_manifest(base_dir, output_path, "stale_or_failed", [str(exc)])
        print(f"reader-wiki validation failed:\n{exc}", file=sys.stderr)
        return 2
    normalized_reader = Path(compile_result.get("wiki_dir", base_dir / "reader_wiki")) / "normalized_reader.md"
    if normalized_reader.exists():
        markdown = normalized_reader.read_text(encoding="utf-8")

    try:
        draft_translation_issues = validate_translation_contract(markdown, False)
        structure_issues = validate_reader_structure(markdown, base_dir)
    except ValueError as exc:
        write_artifact_manifest(base_dir, output_path, "stale_or_failed", [str(exc)])
        print(str(exc), file=sys.stderr)
        return 2
    warnings.extend(draft_translation_issues)
    warnings.extend(structure_issues)

    meta = collect_meta(base_dir)
    title = infer_title(markdown, meta, args.title)
    glossary = extract_glossary(base_dir)

    profile = load_profile(profile_path)

    concepts = concepts_for_annotation(profile or {}, glossary)
    source_pages = collect_source_page_manifest(base_dir)
    body_html, toc = render_document(markdown, base_dir, not args.no_embed_assets, warnings)
    body_html = annotate_html_text(body_html, concepts)
    summary_panel = build_paper_summary_panel(load_compiled_paper_summary(base_dir))
    knowledge_panel = build_knowledge_panel(profile or {}, glossary, concepts, profile_path)
    feedback_ui = build_feedback_ui(title, base_dir, concepts, True)
    output_name = output_path.name.lower()
    if output_name != "reader_interactive.html":
        write_artifact_manifest(base_dir, output_path, "stale_or_failed", ["Final reader output must be named reader_interactive.html"])
        print(
            "Final reader output must be named reader_interactive.html. "
            "Complete translation and structure first instead of creating draft/preview HTML.",
            file=sys.stderr,
        )
        return 2
    html_output = build_html(
        title=title,
        body_html=body_html,
        toc=toc,
        meta=meta,
        base_dir=base_dir,
        source_pages=source_pages,
        summary_panel=summary_panel,
        knowledge_panel=knowledge_panel,
        profile_path=profile_path if profile else None,
        feedback_ui=feedback_ui,
        math_renderer=args.math_renderer,
        mathjax_url=args.mathjax_url,
    )
    html_issues = validate_generated_html(html_output, concepts, args.math_renderer)
    if html_issues:
        write_artifact_manifest(base_dir, output_path, "stale_or_failed", html_issues[:50])
        print(
            "Generated HTML contract failed. reader_interactive.html was not written.\n"
            + "\n".join(f"- {issue}" for issue in html_issues[:20]),
            file=sys.stderr,
        )
        return 2
    atomic_write_text(output_path, html_output)
    write_artifact_manifest(base_dir, output_path, "html_contract_pass_pending_adversarial_audit", [])

    original_count = markdown.count("**Original:**")
    chinese_count = markdown.count("**中文:**")
    if original_count != chinese_count:
        warnings.append(f"Original/中文 block count mismatch: {original_count} vs {chinese_count}")

    print(f"Wrote {output_path}")
    print(f"Bilingual blocks detected: {min(original_count, chinese_count)}")
    if warnings:
        print("Warnings:")
        warning_limit = 20
        for warning in warnings[:warning_limit]:
            print(f"- {warning}")
        if len(warnings) > warning_limit:
            print(f"- ... {len(warnings) - warning_limit} more warnings")
    if profile_path and profile:
        print(f"Learner profile: {profile_path}")
    print(f"Knowledge annotations: {len(concepts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
