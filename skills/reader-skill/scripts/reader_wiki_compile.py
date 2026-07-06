#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compile a reader bundle into llm-wiki style ledgers before HTML generation."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


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
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
    heading = re.search(r"(?m)^\s*#{1,6}\s+", text[begin:])
    if heading:
        candidates.append(begin + heading.start())
    anchor = re.search(r'(?m)^<a\s+id=["\'][^"\']+["\']\s*>\s*</a>\s*$', text[begin:])
    if anchor:
        candidates.append(begin + anchor.start())
    end = min(candidates) if candidates else len(text)
    return text[begin:end].strip(), text[end:]


def source_page(source: str) -> int | None:
    match = re.search(r"\bp\.(\d+)", source or "")
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
        notes = block.get("notes", "")
        for pattern in NOTE_POLLUTION_PATTERNS:
            if re.search(pattern, notes, re.I | re.M):
                errors.append(f"{bid}.notes: structural pollution detected by {pattern}")
        if len(clean_space(notes).split()) > 90:
            warnings.append(f"{bid}.notes: unusually long note; verify it only explains the current block")
        if block["block_type"] == "formula" and not ANY_MATH_RE.search(block["original"] + "\n" + block["zh"]):
            errors.append(f"{bid}: formula block lacks LaTeX math")
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
    return errors


def formula_ledger(blocks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    ledger: list[dict[str, Any]] = []
    errors: list[str] = []
    for block in blocks:
        combined = block["original"] + "\n" + block["zh"]
        formulas = [m.group(0) for m in ANY_MATH_RE.finditer(combined)]
        if block["block_type"] == "formula" or formulas:
            ferr = validate_math_balance("\n".join(formulas))
            errors.extend(f"{block['block_id']}: {err}" for err in ferr)
            entry = {
                "block_id": block["block_id"],
                "source_anchor": block["source_anchor"],
                "formulas": formulas,
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
    for kind, rows in (("figure", source_figures), ("table", source_tables)):
        if not isinstance(rows, list):
            continue
        for row in rows:
            block_id = str(row.get("id") or row.get("block_id") or "")
            segment = segments.get(block_id, "")
            has_image = bool(IMAGE_RE.search(segment))
            has_table = bool(TABLE_SEP_RE.search(segment))
            has_caption = "Original caption" in segment and ("中文图注" in segment or "中文表注" in segment)
            ok = (has_image if kind == "figure" else has_table) and has_caption
            if not ok:
                errors.append(f"{block_id}: source_map {kind} lacks complete card/caption in normalized Markdown")
            entries.append({
                "block_id": block_id,
                "kind": kind,
                "has_image": has_image,
                "has_semantic_table": has_table,
                "has_bilingual_caption": has_caption,
                "source_page": row.get("page"),
                "status": "ok" if ok else "error",
            })
    return entries, errors


def algorithm_ledger(markdown: str, source_map: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    segments = dict(split_segments(markdown))
    source_has_algorithm = any(
        isinstance(row, dict) and ALGORITHM_RE.search(str(row.get("original", "")))
        for row in (source_map.get("blocks") or [])
    )
    if re.search(r'Algorithm\s+\d+\s+summary|算法\s*\d+\s*摘要|摘要\s*:', markdown, re.I):
        errors.append("Algorithm content is summarized; formal reader requires a full algorithm card")
    for block_id, segment in segments.items():
        if not block_id:
            continue
        if block_id.startswith("A") or ALGORITHM_RE.search(segment):
            has_original = "**Original algorithm:**" in segment
            has_zh = "**中文算法:**" in segment or "**Chinese algorithm:**" in segment
            line_count = len(ALGORITHM_LINE_RE.findall(segment))
            ok = has_original and has_zh and line_count >= 5
            if not ok:
                errors.append(f"{block_id}: algorithm card must include full original and Chinese numbered steps")
            entries.append({
                "block_id": block_id,
                "kind": "algorithm",
                "has_original_algorithm": has_original,
                "has_chinese_algorithm": has_zh,
                "numbered_steps": line_count,
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


def collect_concepts(blocks: list[dict[str, Any]], source_map: dict[str, Any], profile: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
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

    for term, ctype, zh, note in SEED_CONCEPTS:
        if re.search(r'(?<![\w-])' + re.escape(term) + r'(?![\w-])', text, re.I):
            anchors = [b["block_id"] for b in blocks if re.search(r'(?<![\w-])' + re.escape(term) + r'(?![\w-])', b["original"] + "\n" + b["zh"], re.I)]
            add(term, ctype, zh, note, anchors[:12])

    for item in source_map.get("glossary", []) or []:
        if isinstance(item, dict):
            add(item.get("term", ""), "term", item.get("translation", ""), item.get("note", ""), [])

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

    result = sorted(entries.values(), key=lambda row: (row["concept_type"], row["canonical_name"].lower()))
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


def compile_reader_wiki(reader_dir: Path, strict: bool = True, profile_path: Path | None = None) -> dict[str, Any]:
    reader_dir = reader_dir.resolve()
    md_path = reader_dir / "paper.md"
    if not md_path.exists():
        raise FileNotFoundError(f"Cannot find {md_path}")
    source_map = read_json(reader_dir / "source_map.json")
    profile = read_json(profile_path) if profile_path else {}
    markdown = md_path.read_text(encoding="utf-8")
    blocks, sections, parse_errors = parse_bilingual(markdown)
    errors = list(parse_errors)
    warnings: list[str] = []
    text_errors, text_warnings = validate_text_quality(blocks)
    errors.extend(text_errors)
    warnings.extend(text_warnings)
    formulas, formula_errors = formula_ledger(blocks)
    errors.extend(formula_errors)
    figures_tables, ft_errors = figure_table_ledger(markdown, source_map)
    errors.extend(ft_errors)
    algorithms, algorithm_errors = algorithm_ledger(markdown, source_map)
    errors.extend(algorithm_errors)
    concepts, concept_warnings = collect_concepts(blocks, source_map, profile)
    warnings.extend(concept_warnings[:20])
    page_count = int((source_map.get("paper") or {}).get("page_count") or len(source_map.get("pages") or []))
    is_fixture = "fixture" in json.dumps(source_map.get("paper") or {}, ensure_ascii=False).lower()
    if page_count >= 4 and not is_fixture and len(concepts) < 30:
        errors.append(f"concept ledger has {len(concepts)} concepts; expected at least 30 for a full paper")
    if len(concepts) > 60:
        errors.append(f"concept ledger has {len(concepts)} concepts; expected at most 60")

    annotation_metadata = {
        "version": 1,
        "generated_at": utc_now(),
        "concept_count": len(concepts),
        "required_mark_attrs": ["data-concept", "data-status", "data-source-anchor", "data-concept-type", "data-alias-zh", "title"],
        "concepts": concepts,
    }
    manifest = {
        "version": 1,
        "generated_at": utc_now(),
        "source_of_truth": {
            "paper_md": str(md_path),
            "source_map": str(reader_dir / "source_map.json"),
            "raw_sources_immutable": True,
        },
        "paper": source_map.get("paper") or {},
        "sections": sections,
        "bilingual_blocks": blocks,
        "normalized_markdown": "reader_wiki/normalized_reader.md",
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
    (wiki / "normalized_reader.md").write_text(markdown, encoding="utf-8")
    if strict and errors:
        preview = "\n".join(f"- {err}" for err in errors[:20])
        raise ValueError(f"reader-wiki validation failed:\n{preview}")
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
