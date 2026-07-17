#!/usr/bin/env python3
"""Regression tests for formal-reader-v3 resumable completion state."""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "skills" / "reader-skill" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
NATURE_SCRIPTS = ROOT / "skills" / "nature-reader" / "scripts"
if str(NATURE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NATURE_SCRIPTS))

from completion_state import (  # noqa: E402
    atomic_write_json,
    canonical_path,
    compile_canonical_markdown,
    ensure_object_inventory,
    formal_status_path,
    load_all_records,
    mark_stale,
    reader_is_formal_ready,
    record_path,
    render_progress_html,
    seed_records,
    sha256_file,
    update_run_state,
    write_record,
)
from reader_wiki_compile import compile_reader_wiki, load_authored_paper_summary, validate_source_page_assets  # noqa: E402
from markdown_reader_to_html import (  # noqa: E402
    annotate_html_text,
    build_knowledge_panel,
    concepts_for_annotation,
    markdown_inline,
)
from preflight_reader_bundle import build_preflight_manifest, write_json as write_preflight_json  # noqa: E402


PIXEL = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=")
PIXEL_SHA256 = hashlib.sha256(PIXEL).hexdigest()
CONVERTER = ROOT / "skills" / "reader-skill" / "scripts" / "markdown_reader_to_html.py"
AUDIT = ROOT / "skills" / "reader-skill" / "tests" / "adversarial_html_audit.py"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def source_map() -> dict:
    return {
        "version": 2,
        "paper": {
            "title": "V3 Fixture Paper",
            "authors": "PaperTrace",
            "source_type": "fixture",
            "page_count": 1,
            "source_pdf_sha256": "a" * 64,
        },
        "blocks": [
            {"id": "S001", "page": 1, "type": "paragraph", "original_text": "A grounded statement about a quantum circuit."},
            {"id": "E001", "page": 1, "type": "equation_or_formula", "original_text": "The amplitude is \\[x^2+y^2\\]."},
            {"id": "A001", "page": 1, "type": "algorithm", "original_text": "1: Input circuit\n2: Output result"},
            {"id": "R001", "page": 1, "type": "reference", "original_text": "[1] Grounded Reference, 2026."},
        ],
        "pages": [{"page": 1, "source_page_image": "assets/source_pages/page-01.png", "sha256": PIXEL_SHA256}],
        "figures": [{"id": "F001", "page": 1, "caption_original": "Figure 1. Fixture object.", "source_page_image": "assets/source_pages/page-01.png"}],
        "tables": [{"id": "T001", "page": 1, "caption_original": "Table 1. Fixture data."}],
        "algorithms": [{"id": "A001", "page": 1, "source_block_id": "", "original_text": "1: Input circuit\n2: Output result"}],
    }


def complete_records(reader: Path) -> None:
    assets = reader / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    figure_asset = assets / "figure-f001.png"
    figure_asset.write_bytes(PIXEL)
    algorithm_dir = assets / "algorithms"
    algorithm_dir.mkdir(parents=True, exist_ok=True)
    algorithm_tex = algorithm_dir / "A001.tex"
    algorithm_svg = algorithm_dir / "A001.svg"
    algorithm_manifest = algorithm_dir / "A001.compile.json"
    algorithm_tex.write_text(
        "\\begin{algorithmic}[1]\n\\Require circuit\n\\State Input circuit\n"
        "\\State Output result\n\\Ensure result\n\\end{algorithmic}\n",
        encoding="utf-8",
    )
    algorithm_svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 80"><text x="8" y="30">Algorithm fixture</text></svg>\n',
        encoding="utf-8",
    )
    write_json(algorithm_manifest, {
        "schema_version": 1,
        "contract": "latex-compiled-algorithm-v1",
        "engine": "fixture-xelatex",
        "tex_path": "A001.tex",
        "tex_sha256": sha256_file(algorithm_tex),
        "svg_path": "A001.svg",
        "svg_sha256": sha256_file(algorithm_svg),
        "numbered_states": 2,
        "translated_comments": 0,
        "status": "pass",
        "compile_status": "pass",
    })
    seed_records(reader)
    for record in load_all_records(reader):
        kind = record["record_kind"]
        if kind == "block":
            if record["source_anchor"] == "S001":
                record.update({"original": "A grounded statement about a quantum circuit.", "zh": "一条关于量子电路的可追溯陈述。", "notes": "用于验证逐块状态。"})
            elif record["source_anchor"] == "E001":
                record.update({"original": "The amplitude is \\[x^2+y^2\\].", "zh": "振幅为 \\[x^2+y^2\\]。", "notes": "双语两侧保留同一可验证 LaTeX。"})
            else:
                record.update({"original": "1: Input circuit\n2: Output result", "zh": "1：输入量子电路\n2：输出结果", "notes": "算法源块与对象卡分别登记。"})
            if record["source_anchor"] == "E001":
                record["object_metadata"] = {
                    **record["object_metadata"],
                    "source_math_inventory": {
                        "contract": "source-math-inventory-v1",
                        "status": "complete",
                        "components": [
                            {"id": "amplitude", "presentation": "display", "signature": "x^2+y^2"},
                        ],
                    },
                }
            record["status"] = "pass"
        elif kind == "formula":
            record.update({"original": "\\[x^2+y^2\\]", "zh": "", "notes": "由对应原文块保留。", "status": "pass"})
        elif kind == "reference":
            record.update({"original": "[1] Grounded Reference, 2026.", "zh": "", "notes": "原文参考文献，不翻译。", "status": "pass"})
        elif kind == "figure":
            record.update({
                "notes": "对象级裁剪资产。", "status": "pass",
                "object_metadata": {**record["object_metadata"], "asset_path": "assets/figure-f001.png", "asset_sha256": sha256_file(figure_asset), "bbox": [0, 0, 1, 1], "original_caption": "Figure 1. Fixture object.", "zh_caption": "图 1：测试对象。"},
            })
        elif kind == "table":
            record.update({
                "notes": "语义表。", "status": "pass",
                "object_metadata": {**record["object_metadata"], "representation": "semantic_table", "markdown_table": "| Metric | Value |\n| --- | --- |\n| Fidelity | 1.0 |", "original_caption": "Table 1. Fixture data.", "zh_caption": "表 1：测试数据。"},
            })
        elif kind == "algorithm":
            record.update({
                "notes": "完整源码算法，经构建期 LaTeX 编译。", "status": "pass",
                "object_metadata": {
                    **record["object_metadata"],
                    "representation": "latex_compiled_algorithm",
                    "latex_source_path": "assets/algorithms/A001.tex",
                    "latex_source_sha256": sha256_file(algorithm_tex),
                    "compiled_asset_path": "assets/algorithms/A001.svg",
                    "compiled_asset_sha256": sha256_file(algorithm_svg),
                    "compile_manifest_path": "assets/algorithms/A001.compile.json",
                    "compile_manifest_sha256": sha256_file(algorithm_manifest),
                    "compile_engine": "fixture-xelatex",
                    "numbered_steps": 2,
                    "translated_comments": 0,
                },
            })
        write_record(reader, record)


def complete_inventory(reader: Path) -> None:
    inventory_path = ensure_object_inventory(reader)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    for row in inventory["objects"]:
        if row["id"] == "F001":
            row.update({"asset_path": "assets/figure-f001.png", "bbox": [0, 0, 1, 1], "representation": "tight_crop", "status": "complete"})
        elif row["id"] == "T001":
            row.update({"representation": "semantic_table", "status": "complete"})
        elif row["id"] == "A001":
            row.update({
                "representation": "latex_compiled_algorithm",
                "asset_path": "assets/algorithms/A001.svg",
                "latex_source_path": "assets/algorithms/A001.tex",
                "compiled_asset_path": "assets/algorithms/A001.svg",
                "compile_manifest_path": "assets/algorithms/A001.compile.json",
                "status": "complete",
            })
    write_json(inventory_path, inventory)


def make_reader(base: Path) -> Path:
    reader = base / "reader"
    reader.mkdir()
    source_pages = reader / "assets" / "source_pages"
    source_pages.mkdir(parents=True)
    (source_pages / "page-01.png").write_bytes(PIXEL)
    write_json(reader / "source_map.json", source_map())
    complete_records(reader)
    complete_inventory(reader)
    compile_canonical_markdown(reader, materialize_paper=True)
    preflight, issues = build_preflight_manifest(reader)
    if issues:
        raise AssertionError(f"fixture preflight unexpectedly failed: {issues}")
    write_preflight_json(reader / "reader_wiki" / "preflight_manifest.json", preflight)
    state = update_run_state(reader)
    if state["status"] != "pass":
        raise AssertionError(f"fixture state is not pass: {state}")
    write_json(reader / "reader_wiki" / "paper_summary.json", {
        "schema_version": 1,
        "language": "zh-CN",
        "overview": {
            "text": "这份测试论文通过一个可追溯的量子电路陈述和一个双语公式块，验证正式阅读器能把源证据、中文解释、数学表达、对象卡片与交互界面组合为同一个可审计产物，并确保新增的论文总结、原始页面预览与视图控件不会绕过既有完成记录和结构门禁。",
            "source_anchors": ["S001", "E001"],
        },
        "what_it_does": [
            {"text": "给出一个可由稳定来源锚点定位的量子电路陈述。", "source_anchors": ["S001"]},
            {"text": "使用独立公式块验证双语数学表达的一致性。", "source_anchors": ["E001"]},
        ],
        "how_it_works": [
            {"text": "先将英文原始陈述和忠实中文翻译绑定到同一个来源块。", "source_anchors": ["S001"]},
            {"text": "再在双语两侧保留相同的显式 LaTeX 公式签名。", "source_anchors": ["E001"]},
            {"text": "最后把图、表和算法对象登记为可独立审核的结构化卡片。", "source_anchors": ["F001", "T001", "A001"]},
        ],
        "why_it_matters": [
            {"text": "证明正式 HTML 可以保持从解释界面返回原始证据的路径。", "source_anchors": ["S001"]},
            {"text": "证明交互增强不会替代公式和对象层面的结构验证。", "source_anchors": ["E001", "F001"]},
        ],
        "evidence_and_limitations": [
            {"text": "该夹具只验证管线契约，不代表真实论文的科学结论或完整篇幅。", "source_anchors": ["S001"]},
        ],
    })
    return reader


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True)


def main() -> int:
    glossary = [
        {
            "term": "Quantum Fourier transform",
            "aliases_en": ["QFT"],
            "aliases_zh": ["量子傅里叶变换"],
            "translation": "量子傅里叶变换",
            "note": "在本文中执行相干重组。",
            "concept_id": "quantum-fourier-transform",
            "concept_type": "math_object",
            "source_anchors": ["S001"],
            "status": "unrated",
        },
        {
            "term": "Color ordering",
            "aliases_en": [],
            "aliases_zh": ["颜色排序"],
            "translation": "颜色排序",
            "note": "标记外部粒子的次序。",
            "concept_id": "color-ordering",
            "concept_type": "term",
            "source_anchors": ["S001"],
            "status": "unrated",
        },
    ]
    annotation_concepts = concepts_for_annotation({}, glossary)
    bilingual_html = (
        '<section class="bilingual-block has-notes" id="S001">'
        '<article class="lang-panel original"><p>The quantum Fourier transform is applied.</p></article>'
        '<article class="lang-panel translation"><p>随后应用量子傅里叶变换；颜色排序只在译文补充说明中出现。</p></article>'
        '</section>'
    )
    annotated = annotate_html_text(bilingual_html, annotation_concepts)
    if annotated.count('data-concept-id="quantum-fourier-transform"') != 2:
        raise AssertionError("bilingual concept annotation did not emit one aligned mark per language")
    if '<mark class="knowledge-gap unrated"' not in annotated or '>量子傅里叶变换</mark>' not in annotated:
        raise AssertionError("Chinese panel did not match its controlled Chinese alias")
    if 'data-concept-id="color-ordering"' in annotated:
        raise AssertionError("an incidental Chinese term created a concept absent from Original")
    panel = build_knowledge_panel(None, glossary, annotation_concepts, None, ROOT, True, [])
    for token in (
        "Paper Concept Ledger / Personal Knowledge Boundary",
        "Personal Status",
        "Chinese Name",
        "Role in This Paper",
        "Mathematical object",
        "Not in personal profile",
    ):
        if token not in panel:
            raise AssertionError(f"knowledge panel lacks English interface token: {token}")
    if ">math_object<" in panel or ">个人状态<" in panel:
        raise AssertionError("knowledge panel leaked an internal enum or Chinese interface label")

    with tempfile.TemporaryDirectory(prefix="completion_v3_", dir=ROOT) as temporary:
        reader = make_reader(Path(temporary))

        # Resume must retain same-source completed records byte-for-byte except
        # no record is rewritten by seeding.
        block_path = record_path(reader, "block:S001")
        before = block_path.read_bytes()
        seed_records(reader)
        if block_path.read_bytes() != before:
            raise AssertionError("same-source pass record was overwritten on resume")

        # A contract upgrade must not let an old same-PDF pass record bypass
        # source-math inventory requirements. The source block is deliberately
        # typed as a formula in the fixture, while the migration behaviour is
        # independent of the extraction type in production.
        equation_path = record_path(reader, "block:E001")
        equation_record = json.loads(equation_path.read_text(encoding="utf-8"))
        reviewed_inventory = equation_record["object_metadata"].pop("source_math_inventory")
        equation_record["object_metadata"].pop("source_math_inventory_required", None)
        equation_record["object_metadata"].pop("source_math_evidence_contract", None)
        equation_record["object_metadata"].pop("source_math_evidence", None)
        equation_record["status"] = "pass"
        equation_record["validation_errors"] = []
        write_json(equation_path, equation_record)
        seed_records(reader)
        migrated = json.loads(equation_path.read_text(encoding="utf-8"))
        if migrated["status"] != "invalid" or not migrated["object_metadata"].get("source_math_inventory_required"):
            raise AssertionError("same-source math-contract upgrade did not invalidate a legacy pass record")
        migrated["object_metadata"]["source_math_inventory"] = reviewed_inventory
        migrated["status"] = "pass"
        migrated["validation_errors"] = []
        write_json(equation_path, migrated)
        seed_records(reader)

        progress = render_progress_html(reader)
        progress_text = progress.read_text(encoding="utf-8")
        if progress.name != "reader_progress.html" or "INCOMPLETE / NOT FORMAL" not in progress_text:
            raise AssertionError("progress artifact is not clearly non-formal")
        if any(token in progress_text for token in ("downloadFeedback", "readerFeedbackSeed", "knowledge_profile")):
            raise AssertionError("progress artifact exposes formal interaction/profile contracts")

        mark_stale(reader, ["test legacy HTML invalidation"])
        if json.loads(formal_status_path(reader).read_text(encoding="utf-8"))["status"] != "stale":
            raise AssertionError("stale status was not persisted")
        if not reader_is_formal_ready(reader)[0]:
            raise AssertionError("stale old HTML incorrectly blocks a newly complete v3 state")

        compile_reader_wiki(reader, strict=True)
        converted = run([sys.executable, str(CONVERTER), str(reader)])
        if converted.returncode:
            raise AssertionError(f"converter failed\n{converted.stdout}\n{converted.stderr}")
        rendered_html = (reader / "reader_interactive.html").read_text(encoding="utf-8")
        for token in (
            'class="paper-summary" id="paper-summary"',
            'class="layout has-source-pages"',
            'id="sourcePageViewer"',
            'id="toggleOriginal"',
            'id="toggleSourcePages"',
            'id="toggleContents"',
            'id="sourcePaneToggle"',
            'id="contentsPaneToggle"',
            'id="sourcePaneResizer"',
            'id="contentsPaneResizer"',
            'role="separator"',
            'data-source-page="1"',
            "Hide Original",
            "Show Original",
            "Hide Source Pages",
            "Show Source Pages",
            "Hide Contents",
            "Show Contents",
            "feedback-open",
            'data-algorithm-contract="latex-compiled-algorithm-v1"',
            'class="algorithm-render"',
        ):
            if token not in rendered_html:
                raise AssertionError(f"formal reader lacks summary/source-view control token: {token}")
        source_viewer_position = rendered_html.find('<aside class="reader-sidebar"')
        article_position = rendered_html.find("<main>")
        contents_position = rendered_html.find('<nav class="toc"')
        if not 0 <= source_viewer_position < article_position < contents_position:
            raise AssertionError("formal reader must order the source viewer left, article center, and Contents right")
        audited = run([sys.executable, str(AUDIT), str(reader)])
        if audited.returncode:
            raise AssertionError(f"audit failed\n{audited.stdout}\n{audited.stderr}")
        if not (reader / "reader_wiki" / "formal_artifact_manifest.json").is_file():
            raise AssertionError("formal artifact manifest was not written after audit")

        summary_path = reader / "reader_wiki" / "paper_summary.json"
        summary_fixture = json.loads(summary_path.read_text(encoding="utf-8"))
        broken_summary = json.loads(json.dumps(summary_fixture, ensure_ascii=False))
        broken_summary["why_it_matters"][0]["source_anchors"] = ["S999"]
        write_json(summary_path, broken_summary)
        _summary, summary_errors = load_authored_paper_summary(reader, source_map(), [], required=True)
        if not any("unknown source anchor" in message for message in summary_errors):
            raise AssertionError("paper summary contract accepted an unknown source anchor")
        write_json(summary_path, summary_fixture)

        unsafe_map = source_map()
        unsafe_map["pages"][0]["source_page_image"] = "../page-01.png"
        source_page_errors = validate_source_page_assets(reader, unsafe_map, required=True)
        if not any("unsafe/noncanonical" in message for message in source_page_errors):
            raise AssertionError("source-page contract accepted path traversal")

        # A block that explicitly opts into exact bilingual math must reject
        # a component present on only one language side.
        formula_block_path = record_path(reader, "block:E001")
        formula_block = json.loads(formula_block_path.read_text(encoding="utf-8"))
        formula_block.setdefault("object_metadata", {})["bilingual_math_contract"] = "exact-v1"
        formula_block["zh"] = "振幅表达式包含平方和。"
        write_json(formula_block_path, formula_block)
        try:
            compile_canonical_markdown(reader, materialize_paper=True)
            compile_reader_wiki(reader, strict=True)
        except ValueError as exc:
            if "bilingual math count mismatch" not in str(exc):
                raise AssertionError(f"wrong asymmetric-formula failure: {exc}")
        else:
            raise AssertionError("reader-wiki accepted an Original-only formula component")
        formula_block["zh"] = "振幅为 \\[x^2+y^2\\]。"
        write_json(formula_block_path, formula_block)
        compile_canonical_markdown(reader, materialize_paper=True)

        # One display may not pack two independent formulas together merely
        # to save horizontal space; both languages must use atomic displays.
        compound = "First \\[x=1,\\qquad y=2\\]"
        formula_block["original"] = compound
        formula_block["zh"] = "首先 \\[x=1,\\qquad y=2\\]"
        write_json(formula_block_path, formula_block)
        try:
            compile_canonical_markdown(reader, materialize_paper=True)
            compile_reader_wiki(reader, strict=True)
        except ValueError as exc:
            if "multiple logical formulas" not in str(exc):
                raise AssertionError(f"wrong compound-formula failure: {exc}")
        else:
            raise AssertionError("reader-wiki accepted two formulas in one display")
        formula_block["original"] = "The amplitude is \\[x^2+y^2\\]."
        formula_block["zh"] = "振幅为 \\[x^2+y^2\\]。"
        write_json(formula_block_path, formula_block)
        compile_canonical_markdown(reader, materialize_paper=True)

        heading_block = json.loads(block_path.read_text(encoding="utf-8"))
        original_heading_zh = heading_block["zh"]
        heading_block["zh"] = "# 错误的字段内标题\n\n" + original_heading_zh
        write_json(block_path, heading_block)
        compile_canonical_markdown(reader, materialize_paper=True)
        try:
            compile_reader_wiki(reader, strict=True)
        except ValueError as exc:
            if "Markdown heading inside a bilingual field" not in str(exc):
                raise AssertionError(f"wrong field-heading failure: {exc}")
        else:
            raise AssertionError("reader-wiki accepted a field-local Markdown heading")
        heading_block["zh"] = original_heading_zh
        write_json(block_path, heading_block)
        compile_canonical_markdown(reader, materialize_paper=True)

        rendered_plain_variable = markdown_inline("plain token_i text", reader, True, [])
        if 'class="math-inline"' in rendered_plain_variable:
            raise AssertionError("renderer auto-promoted plain underscore text into one-sided math")

        # Atomic write validates before replacing the old valid record.
        bad = json.loads(block_path.read_text(encoding="utf-8"))
        bad.pop("source_evidence_hash")
        try:
            atomic_write_json(block_path, bad, validator=lambda value: (_ for _ in ()).throw(ValueError("bad schema")))
        except ValueError:
            pass
        else:
            raise AssertionError("atomic schema validation accepted malformed record")
        if json.loads(block_path.read_text(encoding="utf-8"))["status"] != "pass":
            raise AssertionError("failed atomic write replaced a valid completion record")

        # Immutable source changes invalidate only the affected record; a
        # subsequent run must not silently reuse its former pass status.
        changed_map = json.loads((reader / "source_map.json").read_text(encoding="utf-8"))
        changed_map["blocks"][0]["original_text"] = "A changed immutable source statement."
        write_json(reader / "source_map.json", changed_map)
        seed_records(reader)
        changed = json.loads(block_path.read_text(encoding="utf-8"))
        if changed["status"] != "invalid" or not changed["validation_errors"]:
            raise AssertionError("source-evidence change did not invalidate stale completion record")

    print("completion-state v3 regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
