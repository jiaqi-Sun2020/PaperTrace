#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compile a reader bundle into llm-wiki style ledgers before HTML generation."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from completion_state import PIPELINE_VERSION, canonical_path, load_all_records, read_json as read_completion_json, reader_is_formal_ready, run_state_path
from formula_contract import atomic_formula_issues, canonical_math_signature


ANCHOR_RE = re.compile(r'(?m)^<a\s+id=["\']([^"\']+)["\']\s*>\s*</a>\s*$')
HEADING_RE = re.compile(r'(?m)^(#{1,6})\s+(.+?)\s*$')
LABEL_RE_TEMPLATE = r'(?ms)^\*\*{label}:\*\*\s*'
DISPLAY_MATH_RE = re.compile(r'(\\\[[\s\S]*?\\\]|\$\$[\s\S]*?\$\$)')
ANY_MATH_RE = re.compile(r'(\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$\$[\s\S]*?\$\$|(?<!\\)\$(?!\s)(?:\\.|[^$]){1,800}?(?<!\\)\$)')
IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
TABLE_SEP_RE = re.compile(r'^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$', re.M)
ALGORITHM_RE = re.compile(r'\bAlgorithm\s+\d+\b', re.I)
ALGORITHM_LINE_RE = re.compile(r'^\s*\d+\s*:', re.M)

VALID_STATUSES = {"unrated", "unknown", "learning", "known", "mastered"}
VALID_CONCEPT_TYPES = {
    "model_module", "math_object", "formula_variable", "method_component",
    "figure_element", "metric", "baseline", "ablation", "claim",
    "contribution", "term",
}
MATH_NOISE = (
    "QKT √ d",
    "QKT",
    "e−iHt",
    "e−iHθt",
    "Rn×d",
    "Rn×n",
    "RT ×n×n",
    "RB×T ×N×N",
    "P v∈V",
    "cid:",
)
PLACEHOLDER_MARKERS = (
    "待忠实翻译",
    "中文译意",
    "非逐句精翻",
    "reading scaffold",
    "translation aid",
    "not a polished full translation",
)
NOTE_POLLUTION_PATTERNS = (
    r"<\s*/?\s*(h1|h2|section|script|style)\b",
    r"Source Page Index",
    r"页面来源",
    r"JOURNAL OF .*CLASS FILES",
    r"Authors?:",
    r"基金|National Natural Science Foundation",
    r"^\s*#{1,6}\s+",
    r"\\begin\{document\}",
)
MOJIBAKE_PATTERNS = ("Ã", "Â", "ä¸", "æ", "å", "ðŸ", "�")
STOP_CONCEPT_FRAGMENTS = (
    "journal of",
    "source page index",
    "authors",
    "manuscript received",
    "national natural science foundation",
    "html",
)
GENERIC_CONCEPT_NOISE = {"and", "amplitude", "coherent", "fig", "figure", "table", "ii", "iii", "iv"}

SUMMARY_SECTION_MIN_ITEMS = {
    "what_it_does": 2,
    "how_it_works": 3,
    "why_it_matters": 2,
    "evidence_and_limitations": 1,
}
SUMMARY_PLACEHOLDER_MARKERS = (
    "summary-required",
    "todo",
    "tbd",
    "待总结",
    "待补充",
    "占位",
)

DIRTY_TEXT_MARKERS = MOJIBAKE_PATTERNS + ("�", "锟", "鈭", "脳", "涓枃", "闃呰")

SEED_CONCEPTS: list[tuple[str, str, str, str]] = [
    ("continuous-time quantum walk", "term", "连续时间量子行走", "Hamiltonian 直接生成图上的连续时间动力学演化。"),
    ("CTQW", "term", "连续时间量子行走", "continuous-time quantum walk 的缩写。"),
    ("Hamiltonian", "math_object", "Hamiltonian / 哈密顿量", "控制 CTQW 演化的算符或矩阵。"),
    ("learnable Hamiltonian", "method_component", "可学习 Hamiltonian", "把图拓扑和节点特征纳入可训练动力学。"),
    ("Laplacian matrix", "math_object", "Laplacian 矩阵", "常用的图结构 Hamiltonian 来源。"),
    ("adjacency matrix", "math_object", "邻接矩阵", "表示图边连接关系。"),
    ("Schrödinger equation", "formula_variable", "Schrödinger 方程", "量子态时间演化方程。"),
    ("unitary evolution", "math_object", "酉演化", "由指数算符 e^{-iHt} 生成的保持范数演化。"),
    ("propagation probability", "formula_variable", "传播概率", "测量 CTQW 后得到的节点概率。"),
    ("probability amplitude", "formula_variable", "概率振幅", "量子态在基态上的复系数。"),
    ("Graph Transformer", "model_module", "Graph Transformer", "用于全局注意力消息传递的图模型。"),
    ("self-attention", "method_component", "自注意力", "Transformer 中的成对相似度建模机制。"),
    ("structural bias", "method_component", "结构偏置", "注入注意力 logits 的图结构先验。"),
    ("QWE", "model_module", "Quantum Walk Encoder", "生成 CTQW 时间演化张量。"),
    ("Quantum Walk Encoder", "model_module", "量子行走编码器", "生成 CTQW 时间演化张量。"),
    ("QWGT", "model_module", "Quantum Walk-Graph Transformer", "把最终传播概率作为注意力结构偏置。"),
    ("QWGR", "model_module", "Quantum Walk-Graph Recurrent", "用循环网络建模 CTQW 时间序列。"),
    ("BiGRU", "model_module", "双向 GRU", "双向门控循环单元。"),
    ("temporal evolution tensor", "math_object", "时间演化张量", "P∈R^{T×n×n}，记录多时间步传播概率。"),
    ("final-time probability matrix", "math_object", "最终时刻概率矩阵", "P_T，用作静态结构偏置。"),
    ("graph classification", "term", "图分类", "将整张图映射到类别标签。"),
    ("graph representation learning", "term", "图表示学习", "学习节点或图级向量表示。"),
    ("graph neural network", "baseline", "图神经网络", "基于消息传递的图学习模型。"),
    ("GNN", "baseline", "图神经网络", "graph neural network 的缩写。"),
    ("graph kernel", "baseline", "图核", "通过核函数度量图相似性。"),
    ("R-convolution graph kernel", "baseline", "R-convolution 图核", "基于子结构分解的图核框架。"),
    ("Graphlet kernel", "baseline", "Graphlet 核", "图核基线之一。"),
    ("Weisfeiler-Lehman subtree kernel", "baseline", "WL 子树核", "图核基线之一。"),
    ("random walk graph kernel", "baseline", "随机行走图核", "基于随机行走匹配的图核。"),
    ("Quantum Jensen-Shannon Kernel", "baseline", "量子 Jensen-Shannon 核", "基于 CTQW 的信息论图核。"),
    ("Graphormer", "baseline", "Graphormer", "图 Transformer 基线。"),
    ("GraphGPS", "baseline", "GraphGPS", "结合消息传递和全局注意力的图模型。"),
    ("GRIT", "baseline", "GRIT", "带图归纳偏置的 Transformer 基线。"),
    ("GIN", "baseline", "GIN", "Graph Isomorphism Network。"),
    ("GCN", "baseline", "GCN", "Graph Convolutional Network。"),
    ("GraphSAGE", "baseline", "GraphSAGE", "归纳式邻居采样 GNN。"),
    ("RWGNN", "baseline", "RWGNN", "Random Walk Graph Neural Network。"),
    ("ablation study", "ablation", "消融实验", "移除模块以衡量贡献。"),
    ("w/o QWGT", "ablation", "去除 QWGT", "消融设置。"),
    ("w/o QWGR", "ablation", "去除 QWGR", "消融设置。"),
    ("MUTAG", "metric", "MUTAG", "图分类基准数据集。"),
    ("PTC(MR)", "metric", "PTC(MR)", "图分类基准数据集。"),
    ("PROTEINS", "metric", "PROTEINS", "图分类基准数据集。"),
    ("DD", "metric", "DD", "图分类基准数据集。"),
    ("IMDB-B", "metric", "IMDB-B", "社交网络图分类数据集。"),
    ("IMDB-M", "metric", "IMDB-M", "社交网络图分类数据集。"),
    ("accuracy", "metric", "准确率", "图分类实验指标。"),
    ("time steps", "formula_variable", "时间步", "CTQW 演化时间粒度 T。"),
    ("network depth", "formula_variable", "网络深度", "CTQWformer 层数 L。"),
    ("global mean pooling", "method_component", "全局平均池化", "将节点表示汇聚为图级表示。"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def slug(text: str) -> str:
    ascii_text = text.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^A-Za-z0-9]+", "-", ascii_text).strip("-").lower()
    if value:
        return value[:96]
    return "concept-" + hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:12]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    json.loads(tmp_path.read_text(encoding="utf-8"))
    tmp_path.replace(path)


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_completion_ledger(reader_dir: Path, source_map_path: Path) -> tuple[dict[str, Any], list[str]]:
    ledger_path = reader_dir / "reader_wiki" / "completion_ledger.json"
    if not ledger_path.exists():
        return {}, [f"missing completion ledger: {ledger_path}"]
    ledger = read_json(ledger_path)
    errors: list[str] = []
    if ledger.get("status") != "pass":
        errors.append("completion_ledger.json is not pass")
    evidence = ledger.get("source_evidence") or {}
    expected_hash = str(evidence.get("source_map_sha256") or "")
    actual_hash = sha256_file(source_map_path)
    if expected_hash and expected_hash != actual_hash:
        errors.append("source_map.json hash differs from completion_ledger.json; rerun completion pass")
    expected_paper_hash = str(evidence.get("paper_md_sha256") or "")
    if not expected_paper_hash or expected_paper_hash != sha256_file(reader_dir / "paper.md"):
        errors.append("paper.md hash differs from completion_ledger.json; rerun completion pass")
    if evidence.get("source_map_immutable") is not True:
        errors.append("completion ledger does not certify immutable source_map.json")
    for key, expected_rel in (
        ("source_map_path", "source_map.json"),
        ("paper_md_path", "paper.md"),
        ("translation_notes_path", "translation_notes.md"),
    ):
        recorded = str(evidence.get(key) or "")
        if not recorded or Path(recorded).is_absolute() or Path(recorded).as_posix() != expected_rel:
            errors.append(f"completion ledger {key} must be bundle-relative {expected_rel!r}")
    notes_path = reader_dir / "translation_notes.md"
    expected_notes_hash = str(evidence.get("translation_notes_sha256") or "")
    if not notes_path.exists() or not expected_notes_hash or expected_notes_hash != sha256_file(notes_path):
        errors.append("translation_notes.md hash differs from completion_ledger.json; rerun completion pass")
    for key, expected_rel in (
        ("object_inventory_path", "reader_wiki/object_inventory.json"),
        ("preflight_manifest_path", "reader_wiki/preflight_manifest.json"),
    ):
        recorded = str(evidence.get(key) or "")
        if not recorded or Path(recorded).is_absolute() or Path(recorded).as_posix() != expected_rel:
            errors.append(f"completion ledger {key} must be bundle-relative {expected_rel!r}")
    object_inventory_path = reader_dir / "reader_wiki" / "object_inventory.json"
    expected_inventory_hash = str(evidence.get("object_inventory_sha256") or "")
    if not object_inventory_path.exists() or not expected_inventory_hash or expected_inventory_hash != sha256_file(object_inventory_path):
        errors.append("object_inventory.json hash differs from completion_ledger.json; rerun completion pass")
    preflight_path = reader_dir / "reader_wiki" / "preflight_manifest.json"
    expected_preflight_hash = str(evidence.get("preflight_manifest_sha256") or "")
    if not preflight_path.exists() or not expected_preflight_hash or expected_preflight_hash != sha256_file(preflight_path):
        errors.append("preflight_manifest.json hash differs from completion_ledger.json; rerun completion pass")
    else:
        preflight = read_json(preflight_path)
        if preflight.get("status") != "pass":
            errors.append("preflight_manifest.json is not pass")
        if str((preflight.get("source_map") or {}).get("sha256") or "") != actual_hash:
            errors.append("preflight_manifest.json is stale against source_map.json")
        if str((preflight.get("paper_md") or {}).get("sha256") or "") != sha256_file(reader_dir / "paper.md"):
            errors.append("preflight_manifest.json is stale against paper.md")
    provenance = ledger.get("content_provenance") if isinstance(ledger.get("content_provenance"), dict) else {}
    if provenance.get("author_role") != "current-session-primary-model":
        errors.append("completion ledger lacks current-session-primary-model content authorship")
    if provenance.get("external_translation_backend") != "none":
        errors.append("completion ledger must certify external_translation_backend: none")
    required_direct_fields = {"chinese_translation", "block_specific_notes", "latex_reconstruction"}
    if not required_direct_fields.issubset(set(provenance.get("directly_authored_fields") or [])):
        errors.append("completion ledger directly_authored_fields are incomplete")
    coverage = ledger.get("source_coverage") if isinstance(ledger.get("source_coverage"), dict) else {}
    if not coverage:
        errors.append("completion ledger lacks source_coverage evidence")
    else:
        if coverage.get("missing_bilingual_ids"):
            errors.append("completion ledger reports missing source blocks")
        if coverage.get("unfaithful_bilingual_ids"):
            errors.append("completion ledger reports unfaithful Original blocks")
        if float(coverage.get("coverage_ratio") or 0) != 1.0 or float(coverage.get("faithful_ratio") or 0) != 1.0:
            errors.append("completion ledger does not certify 100% faithful source coverage")
        source_map = read_json(source_map_path)
        expected_from_source = {
            str(row.get("id") or row.get("block_id") or "")
            for row in (source_map.get("blocks") or [])
            if isinstance(row, dict)
            and re.fullmatch(r"(?:S|E)\d+", str(row.get("id") or row.get("block_id") or ""))
            and str(row.get("original") or row.get("original_text") or row.get("text") or "").strip()
        }
        if set(coverage.get("expected_bilingual_ids") or []) != expected_from_source:
            errors.append("completion source_coverage expected IDs differ from immutable source_map")
        completed_blocks = (ledger.get("normalized_source") or {}).get("bilingual_blocks") or []
        completed_by_id = {str(row.get("block_id") or ""): row for row in completed_blocks if isinstance(row, dict)}
        for block_id in sorted(expected_from_source):
            row = completed_by_id.get(block_id) or {}
            if not row.get("source_evidence_hash"):
                errors.append(f"completion block {block_id} lacks source evidence hash")
            if float(row.get("original_similarity") or 0) < 0.75:
                errors.append(f"completion block {block_id} lacks faithful Original evidence")
        object_rows = (ledger.get("normalized_source") or {}).get("figures_tables") or []
        for row in object_rows:
            if isinstance(row, dict) and not row.get("source_evidence_hash"):
                errors.append(f"completion object {row.get('block_id')} lacks source evidence hash")
        algorithm_rows = (ledger.get("normalized_source") or {}).get("algorithms") or []
        for row in algorithm_rows:
            if not isinstance(row, dict) or not row.get("source_evidence_hash") or float(row.get("original_similarity") or 0) < 0.75:
                errors.append(f"completion algorithm {row.get('block_id') if isinstance(row, dict) else '?'} lacks faithful source binding")
    return ledger, errors


def clean_space(text: Any) -> str:
    value = html.unescape(str(text or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"([A-Za-z])-\s+([A-Za-z])", r"\1\2", value)
    value = re.sub(r"[\u200b-\u200f\u202a-\u202e]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def clean_reader_field(text: Any) -> str:
    value = str(text or "")
    value = "".join(ch for ch in value if ord(ch) >= 32 or ch in "\n\r\t")
    value = re.sub(r"([A-Za-z])-\s+([A-Za-z])", r"\1\2", value)
    return value.strip()


def source_anchor_ids(source_map: dict[str, Any], blocks: list[dict[str, Any]]) -> set[str]:
    anchors = {str(block.get("source_anchor") or block.get("block_id") or "") for block in blocks}
    for value in source_map.values():
        if not isinstance(value, list):
            continue
        for row in value:
            if not isinstance(row, dict):
                continue
            anchor = str(row.get("id") or row.get("block_id") or row.get("source_anchor") or "").strip()
            if anchor:
                anchors.add(anchor)
    return {anchor for anchor in anchors if anchor}


def load_authored_paper_summary(
    reader_dir: Path,
    source_map: dict[str, Any],
    blocks: list[dict[str, Any]],
    *,
    required: bool,
) -> tuple[dict[str, Any], list[str]]:
    """Load the model-authored, source-anchored paper summary contract."""
    path = reader_dir / "reader_wiki" / "paper_summary.json"
    if not path.exists():
        return {}, ["full-paper reader lacks completion-authored reader_wiki/paper_summary.json"] if required else []
    summary = read_json(path)
    errors: list[str] = []
    if summary.get("schema_version") != 1:
        errors.append("paper_summary.json schema_version must be 1")
    if summary.get("language") != "zh-CN":
        errors.append("paper_summary.json language must be zh-CN")

    valid_anchors = source_anchor_ids(source_map, blocks)

    def validate_entry(entry: Any, label: str, minimum_chars: int) -> None:
        if not isinstance(entry, dict):
            errors.append(f"paper summary {label} must be an object")
            return
        text = clean_space(entry.get("text"))
        if len(text) < minimum_chars:
            errors.append(f"paper summary {label} is too short for a detailed, non-template explanation")
        lowered = text.casefold()
        if any(marker in lowered for marker in SUMMARY_PLACEHOLDER_MARKERS):
            errors.append(f"paper summary {label} contains a placeholder/template marker")
        if text and not re.search(r"[\u3400-\u9fff]", text):
            errors.append(f"paper summary {label} must contain Chinese explanatory prose")
        if re.search(r"(?:[A-Za-z]:\\|file://|\.\.[/\\])", text, re.I):
            errors.append(f"paper summary {label} contains an unsafe local path")
        anchors = entry.get("source_anchors")
        if not isinstance(anchors, list) or not anchors:
            errors.append(f"paper summary {label} lacks source_anchors")
            return
        for anchor in anchors:
            anchor_text = str(anchor).strip()
            if anchor_text not in valid_anchors:
                errors.append(f"paper summary {label} cites unknown source anchor {anchor_text!r}")

    validate_entry(summary.get("overview"), "overview", 80)
    for section, minimum_items in SUMMARY_SECTION_MIN_ITEMS.items():
        items = summary.get(section)
        if not isinstance(items, list) or len(items) < minimum_items:
            errors.append(f"paper summary {section} requires at least {minimum_items} source-grounded items")
            continue
        for index, entry in enumerate(items, start=1):
            validate_entry(entry, f"{section}[{index}]", 18)
    return summary, errors


def validate_source_page_assets(reader_dir: Path, source_map: dict[str, Any], *, required: bool) -> list[str]:
    errors: list[str] = []
    pages = source_map.get("pages")
    if not isinstance(pages, list) or not pages:
        return ["full PDF reader lacks source_map.pages source-page evidence"] if required else []
    expected_count = int((source_map.get("paper") or {}).get("page_count") or 0)
    if required and expected_count and len(pages) != expected_count:
        errors.append(f"source page asset count is {len(pages)}; expected {expected_count}")
    seen_pages: set[int] = set()
    for row in pages:
        if not isinstance(row, dict):
            errors.append("source_map.pages contains a non-object entry")
            continue
        try:
            page = int(row.get("page"))
        except (TypeError, ValueError):
            errors.append("source page entry lacks a positive integer page")
            continue
        if page < 1 or page in seen_pages:
            errors.append(f"source page number is invalid or duplicated: {page}")
        seen_pages.add(page)
        relative = str(row.get("source_page_image") or "").replace("\\", "/")
        if not re.fullmatch(r"assets/source_pages/[A-Za-z0-9._-]+\.(?:png|jpe?g|webp)", relative, re.I):
            errors.append(f"source page {page} has unsafe/noncanonical image path: {relative!r}")
            continue
        asset = (reader_dir / relative).resolve()
        source_root = (reader_dir / "assets" / "source_pages").resolve()
        try:
            asset.relative_to(source_root)
        except ValueError:
            errors.append(f"source page {page} escapes assets/source_pages")
            continue
        if not asset.is_file():
            errors.append(f"source page {page} image is missing: {relative}")
            continue
        expected_hash = str(row.get("sha256") or "")
        if not expected_hash or expected_hash != sha256_file(asset):
            errors.append(f"source page {page} image hash is missing or stale")
    if required and expected_count and seen_pages != set(range(1, expected_count + 1)):
        errors.append("source page numbers do not form the complete contiguous PDF page range")
    return errors


def clean_optional_ledger_text(text: Any) -> str:
    value = clean_space(text)
    if not value:
        return ""
    compact = re.sub(r"\s+", "", value)
    if compact and set(compact) <= {"?"}:
        return ""
    if any(marker in value for marker in DIRTY_TEXT_MARKERS):
        return ""
    if any(ord(ch) < 32 and ch not in "\n\r\t" for ch in value):
        return ""
    return value


def split_segments(markdown: str) -> list[tuple[str | None, str]]:
    matches = list(ANCHOR_RE.finditer(markdown))
    if not matches:
        return [(None, markdown)]
    segments: list[tuple[str | None, str]] = []
    if matches[0].start() > 0:
        segments.append((None, markdown[: matches[0].start()]))
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown)
        segments.append((match.group(1), markdown[match.end():end]))
    return segments


def extract_label(text: str, label: str, next_labels: tuple[str, ...]) -> tuple[str, str]:
    start = re.search(LABEL_RE_TEMPLATE.format(label=re.escape(label)), text)
    if not start:
        return "", text
    begin = start.end()
    candidates = []
    for next_label in next_labels:
        match = re.search(LABEL_RE_TEMPLATE.format(label=re.escape(next_label)), text[begin:])
        if match:
            candidates.append(begin + match.start())
    # Anchors already delimit each canonical record.  Authored translations
    # may legitimately contain section headings inside one source block, so a
    # heading is content rather than a label boundary here.
    anchor = re.search(r'(?m)^<a\s+id=["\'][^"\']+["\']\s*>\s*</a>\s*$', text[begin:])
    if anchor:
        candidates.append(begin + anchor.start())
    end = min(candidates) if candidates else len(text)
    return text[begin:end].strip(), text[end:]


def source_page(source: str) -> int | None:
    match = re.search(r"\bp\.\s*(\d+)", source or "")
    return int(match.group(1)) if match else None


def block_type_for(block_id: str, source: str, segment: str) -> str:
    source_lower = source.lower()
    if block_id.startswith("A") or ALGORITHM_RE.search(segment):
        return "algorithm"
    if block_id.startswith("F") or "figure" in source_lower:
        return "figure"
    if block_id.startswith("T") or "table" in source_lower:
        return "table"
    if "equation_or_formula" in source_lower or DISPLAY_MATH_RE.search(segment):
        return "formula"
    if re.search(r"\b(contribution|propose|first|second|third)\b", segment, re.I):
        return "contribution"
    if re.search(r"\b(experiment|baseline|result|ablation|accuracy)\b", segment, re.I):
        return "experiment"
    return "paragraph"


def parse_bilingual(markdown: str) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[str]]:
    blocks: list[dict[str, Any]] = []
    sections: list[dict[str, str]] = []
    errors: list[str] = []
    current_section = ""
    for anchor, segment in split_segments(markdown):
        for heading in HEADING_RE.finditer(segment):
            current_section = clean_space(heading.group(2))
            sections.append({"level": str(len(heading.group(1))), "title": current_section, "anchor": anchor or ""})
        if not anchor:
            continue
        source, rest = extract_label(segment, "Source", ("Original", "中文", "注释", "Notes"))
        original, rest = extract_label(rest, "Original", ("中文", "注释", "Notes"))
        zh, rest = extract_label(rest, "中文", ("注释", "Notes"))
        notes, _rest = extract_label(rest, "注释", ("Notes",))
        if source and original and zh:
            block_type = block_type_for(anchor, source, segment)
            blocks.append({
                "block_id": anchor,
                "source_anchor": clean_space(source),
                "source_page": source_page(source),
                "section": current_section,
                "block_type": block_type,
                "original": clean_reader_field(original),
                "zh": clean_reader_field(zh),
                "notes": clean_reader_field(notes),
                "formulas": [],
                "concepts": [],
                "figures": [],
                "tables": [],
            })
        elif anchor.startswith(("S", "E")) and ("**Original:**" in segment or "**中文:**" in segment):
            errors.append(f"{anchor}: incomplete bilingual block shape")
    return blocks, sections, errors


def validate_text_quality(blocks: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for block in blocks:
        bid = block["block_id"]
        for field in ("original", "zh", "notes"):
            value = block.get(field, "")
            for marker in MOJIBAKE_PATTERNS:
                if marker in value:
                    errors.append(f"{bid}.{field}: mojibake/replacement marker detected: {marker}")
            if any(ord(ch) < 32 and ch not in "\n\r\t" for ch in value):
                errors.append(f"{bid}.{field}: control character detected")
        if any(marker in block["zh"] for marker in PLACEHOLDER_MARKERS):
            errors.append(f"{bid}: placeholder or draft translation marker remains")
        for field in ("original", "zh"):
            if re.search(r"(?m)^\s*#{1,6}\s+", block.get(field, "")):
                errors.append(
                    f"{bid}.{field}: Markdown heading inside a bilingual field breaks aligned panel boundaries; "
                    "normalize it as ordinary field text"
                )
            errors.extend(
                f"{bid}: {message}"
                for message in atomic_formula_issues(block.get(field, ""), field=field)
            )
        notes = block.get("notes", "")
        for pattern in NOTE_POLLUTION_PATTERNS:
            if re.search(pattern, notes, re.I | re.M):
                errors.append(f"{bid}.notes: structural pollution detected by {pattern}")
        if len(clean_space(notes).split()) > 90:
            warnings.append(f"{bid}.notes: unusually long note; verify it only explains the current block")
        if block["block_type"] == "formula" and not ANY_MATH_RE.search(block["original"]):
            errors.append(f"{bid}: formula block lacks reconstructed LaTeX in Original")
        if block.get("source_page") is None:
            errors.append(f"{bid}: source_page could not be parsed from Source label")
        for marker in MATH_NOISE:
            if marker in block["original"] or marker in block["zh"]:
                errors.append(f"{bid}: raw PDF formula noise remains: {marker}")
    return errors, warnings


def validate_math_balance(text: str) -> list[str]:
    errors: list[str] = []
    if text.count("$") % 2:
        errors.append("unclosed dollar math delimiter")
    for opener, closer in (("\\[", "\\]"), ("\\(", "\\)")):
        if text.count(opener) != text.count(closer):
            errors.append(f"unbalanced {opener} {closer}")
    for opener, closer in (("{", "}"), ("(", ")"), ("[", "]")):
        if text.count(opener) != text.count(closer):
            # Markdown links and prose can legitimately contain brackets; keep as warning elsewhere.
            if opener == "{" or "\\[" in text or "\\(" in text or "$" in text:
                errors.append(f"possibly unbalanced {opener}{closer} in math-bearing block")
    for formula in DISPLAY_MATH_RE.findall(text):
        if re.search(r"[。，；：！？]", formula):
            errors.append("CJK punctuation appears inside display-math delimiters")
    return errors


def formula_signature(formula: str) -> str:
    """Return a stable visual signature including inline/display presentation."""
    value = formula.strip()
    if value.startswith("$$") and value.endswith("$$"):
        kind, body = "display", value[2:-2]
    elif value.startswith("\\[") and value.endswith("\\]"):
        kind, body = "display", value[2:-2]
    elif value.startswith("\\(") and value.endswith("\\)"):
        kind, body = "inline", value[2:-2]
    elif value.startswith("$") and value.endswith("$"):
        kind, body = "inline", value[1:-1]
    else:
        kind, body = "unknown", value
    compact_body = re.sub(r"\s+", "", body)
    return f"{kind}:{compact_body}"


def bilingual_formula_alignment_errors(original_formulas: list[str], zh_formulas: list[str]) -> list[str]:
    original_signatures = [formula_signature(value) for value in original_formulas]
    zh_signatures = [formula_signature(value) for value in zh_formulas]
    if original_signatures == zh_signatures:
        return []
    return [
        "Original/Chinese formula components are not one-to-one aligned "
        f"(Original={original_signatures}, Chinese={zh_signatures})"
    ]


def formula_ledger(
    blocks: list[dict[str, Any]],
    exact_alignment_ids: set[str] | None = None,
    source_math_inventories: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    exact_alignment_ids = exact_alignment_ids or set()
    source_math_inventories = source_math_inventories or {}
    ledger: list[dict[str, Any]] = []
    errors: list[str] = []
    for block in blocks:
        original_formulas = [m.group(0) for m in ANY_MATH_RE.finditer(block["original"])]
        zh_formulas = [m.group(0) for m in ANY_MATH_RE.finditer(block["zh"])]
        combined = block["original"] + "\n" + block["zh"]
        formulas = [m.group(0) for m in ANY_MATH_RE.finditer(combined)]
        if block["block_type"] == "formula" or formulas:
            ferr = validate_math_balance("\n".join(formulas))
            alignment_required = block["block_id"] in exact_alignment_ids
            alignment_errors = (
                bilingual_formula_alignment_errors(original_formulas, zh_formulas)
                if alignment_required else []
            )
            ferr.extend(alignment_errors)
            inventory = source_math_inventories.get(str(block["source_anchor"]) or "")
            expected_inventory: list[dict[str, str]] = []
            if inventory:
                expected_inventory = [
                    {
                        "id": str(component.get("id") or ""),
                        "presentation": str(component.get("presentation") or ""),
                        "signature": canonical_math_signature(str(component.get("signature") or "")),
                    }
                    for component in (inventory.get("components") or [])
                    if isinstance(component, dict)
                ]
                expected_signatures = [f"{item['presentation']}:{item['signature']}" for item in expected_inventory]
                original_inventory_signatures = [
                    f"{formula_signature(value).split(':', 1)[0]}:{canonical_math_signature(value)}"
                    for value in original_formulas
                ]
                if original_inventory_signatures != expected_signatures:
                    ferr.append("Original math nodes do not match source_math_inventory")
                if alignment_required and not expected_inventory:
                    ferr.append("source_math_inventory has no usable components")
            errors.extend(f"{block['block_id']}: {err}" for err in ferr)
            entry = {
                "block_id": block["block_id"],
                "source_anchor": block["source_anchor"],
                "formulas": formulas,
                "original_formulas": original_formulas,
                "zh_formulas": zh_formulas,
                "original_formula_signatures": [formula_signature(value) for value in original_formulas],
                "zh_formula_signatures": [formula_signature(value) for value in zh_formulas],
                "bilingual_alignment_contract": "exact-v1" if alignment_required else "explicit-math-v1",
                "bilingual_alignment": "pass" if alignment_required and not alignment_errors else "fail" if alignment_errors else "not-required",
                "source_math_inventory": expected_inventory,
                "has_display_math": bool(DISPLAY_MATH_RE.search(combined)),
                "validation_errors": ferr,
            }
            ledger.append(entry)
            block["formulas"] = formulas
    return ledger, errors


def figure_table_ledger(markdown: str, source_map: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    segments = dict(split_segments(markdown))
    source_figures = source_map.get("figures") or []
    source_tables = source_map.get("tables") or []
    source_figure_ids = {str(row.get("id") or row.get("block_id") or "") for row in source_figures if isinstance(row, dict)}
    source_table_ids = {str(row.get("id") or row.get("block_id") or "") for row in source_tables if isinstance(row, dict)}
    for block_id in segments:
        if block_id and block_id.startswith("F") and block_id not in source_figure_ids:
            errors.append(f"{block_id}: figure card has no matching immutable source_map object")
        if block_id and block_id.startswith("T") and block_id not in source_table_ids:
            errors.append(f"{block_id}: table card has no matching immutable source_map object")
    for kind, rows in (("figure", source_figures), ("table", source_tables)):
        if not isinstance(rows, list):
            continue
        for row in rows:
            block_id = str(row.get("id") or row.get("block_id") or "")
            caption_id = str(row.get("caption_id") or "")
            segment = segments.get(block_id, "")
            if caption_id and caption_id != block_id:
                segment += "\n" + segments.get(caption_id, "")
            image_paths = [match.group(2).strip() for match in IMAGE_RE.finditer(segment)]
            has_image = bool(image_paths)
            has_table = bool(TABLE_SEP_RE.search(segment))
            has_caption = "Original caption" in segment and ("中文图注" in segment or "中文表注" in segment)
            uses_source_page_as_figure = kind == "figure" and any("assets/source_pages/" in path.replace("\\", "/") for path in image_paths)
            ok = (has_image if kind == "figure" else has_table) and has_caption and not uses_source_page_as_figure
            if not ok:
                errors.append(f"{block_id}: source_map {kind} lacks complete card/caption in normalized Markdown")
            if uses_source_page_as_figure:
                errors.append(f"{block_id}: figure card uses full source-page image as figure content")
            entries.append({
                "block_id": block_id,
                "kind": kind,
                "has_image": has_image,
                "image_paths": image_paths,
                "has_semantic_table": has_table,
                "has_bilingual_caption": has_caption,
                "source_page": row.get("page"),
                "source_evidence_hash": hashlib.sha256(
                    json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8")
                ).hexdigest(),
                "status": "ok" if ok else "error",
            })
    return entries, errors


def algorithm_ledger(reader_dir: Path, markdown: str, source_map: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    segments = dict(split_segments(markdown))
    source_algorithm_rows = {
        str(row.get("id") or row.get("block_id") or ""): row
        for row in [*(source_map.get("blocks") or []), *(source_map.get("algorithms") or [])]
        if isinstance(row, dict)
        and (
            str(row.get("type") or "").lower() == "algorithm"
            or ALGORITHM_RE.search(str(row.get("original") or row.get("original_text") or row.get("text") or ""))
        )
    }
    source_has_algorithm = bool(source_algorithm_rows)
    if re.search(r'Algorithm\s+\d+\s+summary|算法\s*\d+\s*摘要|摘要\s*:', markdown, re.I):
        errors.append("Algorithm content is summarized; formal reader requires a full algorithm card")
    for block_id, segment in segments.items():
        if not block_id:
            continue
        if block_id.startswith("A") or ALGORITHM_RE.search(segment):
            if block_id not in source_algorithm_rows:
                errors.append(f"{block_id}: algorithm card has no matching immutable source_map row")
            tex_value, rest = extract_label(
                segment, "Algorithm LaTeX", ("Compiled algorithm", "Compile manifest", "Reading note")
            )
            asset_value, rest = extract_label(
                rest, "Compiled algorithm", ("Compile manifest", "Reading note")
            )
            manifest_value, _ = extract_label(rest, "Compile manifest", ("Reading note",))
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
                    errors.append(f"{block_id}: Algorithm compile manifest is invalid: {exc}")
            ok = (
                block_id in source_algorithm_rows
                and tex_path.is_file()
                and asset_path.is_file()
                and bool(manifest)
                and manifest.get("contract") == "latex-compiled-algorithm-v1"
                and manifest.get("compile_status") == "pass"
                and manifest.get("tex_sha256") == sha256_file(tex_path)
                and manifest.get("svg_sha256") == sha256_file(asset_path)
                and int(manifest.get("numbered_states") or 0) >= 2
            )
            if any(label in segment for label in ("**Original algorithm:**", "**中文算法:**", "**Chinese algorithm:**")):
                errors.append(
                    f"{block_id}: legacy bilingual Algorithm body is forbidden; "
                    "preserve source statements and translate comments only"
                )
                ok = False
            if not ok:
                errors.append(
                    f"{block_id}: Algorithm requires hash-bound LaTeX source, compile manifest, and compiled SVG"
                )
            entries.append({
                "block_id": block_id,
                "kind": "algorithm",
                "representation": "latex_compiled_algorithm",
                "latex_source_path": tex_rel,
                "latex_source_sha256": manifest.get("tex_sha256", ""),
                "compiled_asset_path": asset_rel,
                "compiled_asset_sha256": manifest.get("svg_sha256", ""),
                "compile_manifest_path": manifest_rel,
                "compile_manifest_sha256": sha256_file(manifest_path) if manifest_path.is_file() else "",
                "compile_engine": manifest.get("engine", ""),
                "numbered_steps": int(manifest.get("numbered_states") or 0),
                "translated_comments": int(manifest.get("translated_comments") or 0),
                "source_evidence_hash": hashlib.sha256(
                    json.dumps(source_algorithm_rows.get(block_id, {}), ensure_ascii=False, sort_keys=True).encode("utf-8")
                ).hexdigest() if block_id in source_algorithm_rows else "",
                "status": "ok" if ok else "error",
            })
    if source_has_algorithm and not entries:
        errors.append("source_map contains Algorithm content but normalized Markdown has no algorithm card")
    return entries, errors


def invalid_concept(text: str) -> str:
    value = clean_space(text)
    if not value:
        return "empty"
    if len(value) > 90 or len(value.split()) > 8:
        return "too long / sentence-like"
    lowered = value.lower()
    if lowered in GENERIC_CONCEPT_NOISE or re.fullmatch(r"[A-M]\d+", value, re.I):
        return "equation/section/generic label"
    if any(fragment in lowered for fragment in STOP_CONCEPT_FRAGMENTS):
        return "source/header fragment"
    if re.search(r"<[^>]+>|https?://|assets/source_pages|^\d+$", value):
        return "html/url/source fragment"
    if any(marker in value for marker in MOJIBAKE_PATTERNS):
        return "mojibake"
    if any(ord(ch) < 32 for ch in value):
        return "control character"
    return ""


def profile_status(profile: dict[str, Any], names: list[str]) -> str:
    concepts = profile.get("concepts") or {}
    lookup: dict[str, str] = {}
    for cid, info in concepts.items():
        if not isinstance(info, dict):
            continue
        values = [cid, info.get("label", ""), *(info.get("aliases", []) or []), *(info.get("aliases_en", []) or []), *(info.get("aliases_zh", []) or [])]
        for value in values:
            if value:
                lookup[clean_space(value).lower()] = str(info.get("status") or "unrated").lower()
    for name in names:
        status = lookup.get(clean_space(name).lower())
        if status in VALID_STATUSES:
            return status
    return "unrated"


def load_authored_concept_candidates(reader_dir: Path, blocks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Load completion-authored concepts and prove their local source evidence.

    Candidate concepts are completion data, never profile imports: every entry must
    point to a normalized bilingual block and quote a short exact source span from
    that block's English original.  This prevents glossary padding and profile-only
    concepts from entering a formal reader.
    """
    path = reader_dir / "reader_wiki" / "concept_candidates.json"
    if not path.exists():
        return [], []
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return [], [f"cannot read concept_candidates.json: {exc}"]
    rows = payload.get("concepts") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return [], ["concept_candidates.json: concepts must be a list"]

    block_by_id = {str(block.get("block_id") or ""): block for block in blocks}
    valid: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, item in enumerate(rows, start=1):
        prefix = f"concept_candidates[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix}: entry must be an object")
            continue
        name = clean_space(item.get("canonical_name"))
        anchor = clean_space(item.get("source_anchor"))
        evidence = clean_space(item.get("evidence_span"))
        ctype = clean_space(item.get("concept_type"))
        if invalid_concept(name):
            errors.append(f"{prefix}: invalid canonical_name")
            continue
        if ctype not in VALID_CONCEPT_TYPES:
            errors.append(f"{prefix}: invalid concept_type {ctype!r}")
            continue
        if not anchor or anchor not in block_by_id:
            errors.append(f"{prefix}: source_anchor must name a normalized bilingual block")
            continue
        if not evidence:
            errors.append(f"{prefix}: evidence_span is required")
            continue
        original = clean_space(block_by_id[anchor].get("original"))
        if evidence.lower() not in original.lower():
            errors.append(f"{prefix}: evidence_span is not present in {anchor}.original")
            continue
        aliases_en = item.get("aliases_en") or []
        aliases_zh = item.get("aliases_zh") or []
        if not isinstance(aliases_en, list) or not isinstance(aliases_zh, list):
            errors.append(f"{prefix}: aliases_en and aliases_zh must be lists")
            continue
        clean_aliases_zh = [clean_space(alias) for alias in aliases_zh if clean_space(alias)]
        if any(invalid_concept(alias) for alias in aliases_en + clean_aliases_zh if clean_space(alias)):
            errors.append(f"{prefix}: invalid alias")
            continue
        if not clean_aliases_zh or not any(re.search(r"[\u3400-\u9fff]", alias) for alias in clean_aliases_zh):
            errors.append(f"{prefix}: requires a meaningful Chinese alias")
            continue
        if any(re.fullmatch(r"(?:\u91cf\u5b50|\u6982\u5ff5)\s*\d+", alias) for alias in clean_aliases_zh):
            errors.append(f"{prefix}: Chinese alias is a numbered placeholder")
            continue
        explanation_note = clean_optional_ledger_text(item.get("explanation_note"))
        generic_note = re.fullmatch(
            r"(?:Paper-specific concept anchored to the cited source block\.|"
            r"\u672c\u6587\u4e2d[\u201c\"].+[\u201d\"]\u7684\u4f5c\u7528\u89c1\u6e90\u5757\s*[A-Z]\d+\u3002?)",
            explanation_note,
        )
        if len(explanation_note) < 12 or generic_note:
            errors.append(f"{prefix}: explanation_note must state the concept's paper-specific role")
            continue
        valid.append({
            "canonical_name": name,
            "aliases_en": [clean_space(alias) for alias in aliases_en if clean_space(alias)],
            "aliases_zh": clean_aliases_zh,
            "concept_type": ctype,
            "source_anchor": anchor,
            "evidence_span": evidence,
            "explanation_note": explanation_note,
        })
    return valid, errors


def collect_concepts(
    blocks: list[dict[str, Any]],
    source_map: dict[str, Any],
    profile: dict[str, Any],
    authored_candidates: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    text = "\n".join(block["original"] + "\n" + block["zh"] + "\n" + block["notes"] for block in blocks)
    entries: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    def add(name: str, ctype: str, zh: str = "", note: str = "", anchors: Iterable[str] = ()) -> None:
        name = clean_space(name)
        reason = invalid_concept(name)
        if reason:
            warnings.append(f"rejected concept {name!r}: {reason}")
            return
        cid = slug(name)
        entry = entries.setdefault(cid, {
            "concept_id": cid,
            "canonical_name": name,
            "aliases_en": [],
            "aliases_zh": [],
            "concept_type": ctype,
            "status": "unrated",
            "source_anchors": [],
            "evidence_spans": [],
            "explanation_note": clean_optional_ledger_text(note),
        })
        if zh:
            zh = clean_optional_ledger_text(zh)
            if zh and zh not in entry["aliases_zh"]:
                entry["aliases_zh"].append(zh)
        if name not in entry["aliases_en"]:
            entry["aliases_en"].append(name)
        for anchor in anchors:
            if anchor and anchor not in entry["source_anchors"]:
                entry["source_anchors"].append(anchor)
        entry["status"] = profile_status(profile, [name, *entry["aliases_en"], *entry["aliases_zh"]])
        clean_note = clean_optional_ledger_text(note)
        if clean_note and not entry.get("explanation_note"):
            entry["explanation_note"] = clean_note

    authored_mode = bool(authored_candidates)
    if not authored_mode:
        for term, ctype, zh, note in SEED_CONCEPTS:
            if re.search(r'(?<![\w-])' + re.escape(term) + r'(?![\w-])', text, re.I):
                anchors = [b["block_id"] for b in blocks if re.search(r'(?<![\w-])' + re.escape(term) + r'(?![\w-])', b["original"] + "\n" + b["zh"], re.I)]
                add(term, ctype, zh, note, anchors[:12])

    for item in source_map.get("glossary", []) or []:
        if isinstance(item, dict):
            add(item.get("term", ""), "term", item.get("translation", ""), item.get("note", ""), [])

    for item in authored_candidates or []:
        aliases_zh = item.get("aliases_zh") or []
        add(
            item.get("canonical_name", ""),
            item.get("concept_type", "term"),
            aliases_zh[0] if aliases_zh else "",
            item.get("explanation_note", ""),
            [item.get("source_anchor", "")],
        )
        entry = entries.get(slug(item.get("canonical_name", "")))
        if not entry:
            continue
        for alias in item.get("aliases_en") or []:
            if alias not in entry["aliases_en"]:
                entry["aliases_en"].append(alias)
        for alias in aliases_zh:
            if alias not in entry["aliases_zh"]:
                entry["aliases_zh"].append(alias)
        evidence = clean_space(item.get("evidence_span"))
        if evidence and evidence not in entry["evidence_spans"]:
            entry["evidence_spans"].append(evidence)

    if not authored_mode:
        acronym_re = re.compile(r'\b[A-Z][A-Z0-9]{1,8}(?:-[A-Z0-9]+)?\b')
        for match in acronym_re.finditer(text):
            add(match.group(0), "term", "", "Acronym or model/dataset identifier appearing in the paper.", [])

    for block in blocks:
        for concept_id in list(entries):
            name = entries[concept_id]["canonical_name"]
            if re.search(r'(?<![\w-])' + re.escape(name) + r'(?![\w-])', block["original"] + "\n" + block["zh"], re.I):
                if block["block_id"] not in entries[concept_id]["source_anchors"]:
                    entries[concept_id]["source_anchors"].append(block["block_id"])
                    block["concepts"].append(concept_id)
                span = clean_space(block["original"])[:240]
                if span and span not in entries[concept_id]["evidence_spans"]:
                    entries[concept_id]["evidence_spans"].append(span)

    anchored_entries = []
    for entry in entries.values():
        if not entry.get("source_anchors") or not entry.get("evidence_spans"):
            warnings.append(f"rejected concept {entry.get('canonical_name')!r}: no source anchor/evidence span")
            continue
        anchored_entries.append(entry)
    result = sorted(anchored_entries, key=lambda row: (row["concept_type"], row["canonical_name"].lower()))
    if len(result) > 60:
        result = result[:60]
    return result, warnings


def claim_ledger(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for block in blocks:
        combined = clean_space(block["original"] + " " + block["zh"])
        lowered = combined.lower()
        if any(word in lowered for word in ("propose", "contribution", "outperform", "demonstrate", "achieves", "results show", "we design")):
            rows.append({
                "block_id": block["block_id"],
                "claim_type": "contribution" if "propose" in lowered or "contribution" in lowered else "claim",
                "summary": clean_space(block["notes"] or block["zh"])[:500],
                "source_anchor": block["source_anchor"],
            })
    return rows


def normalized_markdown_from_completion(ledger: dict[str, Any], fallback_markdown: str) -> str:
    segments = ((ledger.get("normalized_source") or {}).get("segments") or [])
    if not isinstance(segments, list) or not segments:
        return fallback_markdown
    parts: list[str] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        anchor = str(segment.get("anchor") or "")
        body = str(segment.get("markdown") or "").strip()
        if anchor:
            parts.append(f'<a id="{anchor}"></a>\n{body}'.rstrip())
        elif body:
            parts.append(body.rstrip())
    normalized = "\n\n".join(part for part in parts if part).strip()
    return normalized + "\n" if normalized else fallback_markdown


def compile_reader_wiki(reader_dir: Path, strict: bool = True, profile_path: Path | None = None) -> dict[str, Any]:
    reader_dir = reader_dir.resolve()
    source_map_path = reader_dir / "source_map.json"
    source_map = read_json(source_map_path)
    state_path = run_state_path(reader_dir)
    state = read_completion_json(state_path) if state_path.exists() else {}
    state_ready, state_errors = reader_is_formal_ready(reader_dir)
    md_path = canonical_path(reader_dir)
    if not md_path.exists():
        state_errors.append("missing canonical_reader.md compiled from v3 pass records")
    if state.get("pipeline_version") != PIPELINE_VERSION:
        state_errors.append("completion run state does not use formal-reader-v3")
    completion_ledger = {
        "status": "pass" if state_ready else "fail",
        "source_coverage": {
            "expected_bilingual_ids": [],
            "faithful_bilingual_ids": [],
        },
    }
    profile = read_json(profile_path) if profile_path else {}
    markdown = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    blocks, sections, parse_errors = parse_bilingual(markdown)
    errors = list(state_errors) + list(parse_errors)
    warnings: list[str] = []
    text_errors, text_warnings = validate_text_quality(blocks)
    errors.extend(text_errors)
    warnings.extend(text_warnings)
    exact_alignment_ids = {
        str(record.get("source_anchor") or "")
        for record in load_all_records(reader_dir)
        if record.get("record_kind") == "block"
        and (
            (record.get("object_metadata") or {}).get("bilingual_math_contract") == "exact-v1"
            or (record.get("object_metadata") or {}).get("source_math_inventory_required")
        )
    }
    source_math_inventories = {
        str(record.get("source_anchor") or ""): (record.get("object_metadata") or {}).get("source_math_inventory")
        for record in load_all_records(reader_dir)
        if record.get("record_kind") == "block"
        and (record.get("object_metadata") or {}).get("source_math_inventory_required")
    }
    formulas, formula_errors = formula_ledger(blocks, exact_alignment_ids, source_math_inventories)
    errors.extend(formula_errors)
    figures_tables, ft_errors = figure_table_ledger(markdown, source_map)
    errors.extend(ft_errors)
    algorithms, algorithm_errors = algorithm_ledger(reader_dir, markdown, source_map)
    errors.extend(algorithm_errors)
    authored_candidates, candidate_errors = load_authored_concept_candidates(reader_dir, blocks)
    errors.extend(candidate_errors)
    concepts, concept_warnings = collect_concepts(blocks, source_map, profile, authored_candidates)
    warnings.extend(concept_warnings[:20])
    page_count = int((source_map.get("paper") or {}).get("page_count") or len(source_map.get("pages") or []))
    is_fixture = "fixture" in json.dumps(source_map.get("paper") or {}, ensure_ascii=False).lower()
    paper_meta = source_map.get("paper") or {}
    source_path = str(paper_meta.get("source_path") or "")
    full_paper = not is_fixture and (page_count >= 4 or paper_meta.get("source_type") == "pdf" or source_path.lower().endswith(".pdf"))
    errors.extend(validate_source_page_assets(reader_dir, source_map, required=full_paper))
    paper_summary, summary_errors = load_authored_paper_summary(
        reader_dir,
        source_map,
        blocks,
        required=full_paper,
    )
    errors.extend(summary_errors)
    candidate_path = reader_dir / "reader_wiki" / "concept_candidates.json"
    if full_paper and not candidate_path.exists():
        errors.append("full-paper reader lacks completion-authored reader_wiki/concept_candidates.json")
    if full_paper and len(concepts) < 30:
        errors.append(f"concept ledger has {len(concepts)} concepts; expected at least 30 for a full paper")
    if len(concepts) > 60:
        errors.append(f"concept ledger has {len(concepts)} concepts; expected at most 60")
    for concept in concepts:
        if not concept.get("source_anchors") or not concept.get("evidence_spans"):
            errors.append(f"concept {concept.get('concept_id')} lacks source anchors or evidence spans")
    if full_paper and concepts:
        aliased = sum(bool(concept.get("aliases_zh")) for concept in concepts)
        explained = sum(bool(clean_space(concept.get("explanation_note"))) for concept in concepts)
        alias_ratio = aliased / len(concepts)
        explanation_ratio = explained / len(concepts)
        noisy = [
            concept.get("canonical_name")
            for concept in concepts
            if invalid_concept(str(concept.get("canonical_name") or ""))
        ]
        if alias_ratio < 0.90:
            errors.append(f"concept ledger Chinese-alias ratio is {alias_ratio:.1%}; expected at least 90%")
        if explanation_ratio < 0.90:
            errors.append(f"concept ledger explanation ratio is {explanation_ratio:.1%}; expected at least 90%")
        if noisy:
            errors.append(f"concept ledger contains equation/section/generic noise: {noisy[:12]}")

    annotation_metadata = {
        "version": 1,
        "generated_at": utc_now(),
        "concept_count": len(concepts),
        "required_mark_attrs": ["data-concept", "data-concept-id", "data-status", "data-source-anchor", "data-concept-type", "data-alias-zh", "title"],
        "concepts": concepts,
    }
    source_of_truth = {
        "canonical_reader": "reader_wiki/canonical_reader.md",
        "source_map": "source_map.json",
        "completion_run_state": "reader_wiki/completion_run_state.json",
        "completion_blocks": "reader_wiki/completion_blocks",
        "object_inventory": "reader_wiki/object_inventory.json",
        "preflight_manifest": "reader_wiki/preflight_manifest.json",
        "source_map_sha256": sha256_file(source_map_path),
        "canonical_reader_sha256": sha256_file(md_path) if md_path.exists() else "",
        "object_inventory_sha256": sha256_file(reader_dir / "reader_wiki" / "object_inventory.json") if (reader_dir / "reader_wiki" / "object_inventory.json").exists() else "",
        "preflight_manifest_sha256": sha256_file(reader_dir / "reader_wiki" / "preflight_manifest.json") if (reader_dir / "reader_wiki" / "preflight_manifest.json").exists() else "",
        "raw_sources_immutable": True,
    }
    normalization_path = reader_dir / "reader_wiki" / "original_normalization_ledger.json"
    if normalization_path.exists():
        source_of_truth["original_normalization_ledger"] = "reader_wiki/original_normalization_ledger.json"
        source_of_truth["original_normalization_ledger_sha256"] = sha256_file(normalization_path)
    if candidate_path.exists():
        source_of_truth["concept_candidates"] = "reader_wiki/concept_candidates.json"
        source_of_truth["concept_candidates_sha256"] = sha256_file(candidate_path)
    summary_path = reader_dir / "reader_wiki" / "paper_summary.json"
    if summary_path.exists():
        source_of_truth["paper_summary"] = "reader_wiki/paper_summary.json"
        source_of_truth["paper_summary_sha256"] = sha256_file(summary_path)
    manifest = {
        "version": 1,
        "generated_at": utc_now(),
        "source_of_truth": source_of_truth,
        "paper": source_map.get("paper") or {},
        "sections": sections,
        "bilingual_blocks": blocks,
        "paper_summary": paper_summary,
        "normalized_markdown": "reader_wiki/normalized_reader.md",
        "completion_run_state_status": state.get("status", "missing"),
    }
    report = {
        "version": 1,
        "generated_at": utc_now(),
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "bilingual_blocks": len(blocks),
            "formulas": len(formulas),
            "concepts": len(concepts),
            "figure_table_entries": len(figures_tables),
            "algorithms": len(algorithms),
            "claims": len(claim_ledger(blocks)),
            "paper_summary_sections": 1 + sum(len(paper_summary.get(key) or []) for key in SUMMARY_SECTION_MIN_ITEMS) if paper_summary else 0,
            "source_pages": len(source_map.get("pages") or []),
            "expected_source_blocks": int(state.get("expected_records") or 0),
            "faithful_source_blocks": int(state.get("completed_records") or 0),
        },
    }
    wiki = reader_dir / "reader_wiki"
    write_json(wiki / "reader_manifest.json", manifest)
    write_json(wiki / "concept_ledger.json", {
        "version": 1,
        "generated_at": utc_now(),
        "concept_count": len(concepts),
        "concepts": concepts,
    })
    write_json(wiki / "formula_ledger.json", formulas)
    write_json(wiki / "figure_table_ledger.json", figures_tables)
    write_json(wiki / "algorithm_ledger.json", algorithms)
    write_json(wiki / "claim_contribution_ledger.json", claim_ledger(blocks))
    write_json(wiki / "annotation_metadata.json", annotation_metadata)
    write_json(wiki / "structure_validation_report.json", report)
    write_text_atomic(wiki / "normalized_reader.md", markdown)
    if strict and errors:
        preview = "\n".join(f"- {err}" for err in errors[:20])
        raise ValueError(f"reader-wiki validation failed:\n{preview}")
    report["wiki_dir"] = str(wiki)
    return report


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reader_dir")
    parser.add_argument("--profile")
    parser.add_argument("--no-strict", action="store_true")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    try:
        report = compile_reader_wiki(
            Path(args.reader_dir),
            strict=not args.no_strict,
            profile_path=Path(args.profile).expanduser().resolve() if args.profile else None,
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("status") == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
