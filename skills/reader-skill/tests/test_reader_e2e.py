#!/usr/bin/env python3
"""End-to-end contract tests for reader_interactive.html generation."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CONVERTER = ROOT / "skills" / "reader-skill" / "scripts" / "markdown_reader_to_html.py"
ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def run_converter(reader_dir: Path, *, profile: Path | None = None, annotations: bool = False) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(CONVERTER),
        str(reader_dir),
        "--output",
        str(reader_dir / "reader_interactive.html"),
    ]
    if profile is not None:
        cmd.extend(["--profile", str(profile)])
    if not annotations:
        cmd.append("--no-knowledge-annotations")
    return subprocess.run(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


def source_map() -> dict:
    return {
        "paper": {
            "title": "Fixture Paper",
            "authors": ["Codex E2E"],
            "source_type": "reader-skill e2e fixture",
        },
        "blocks": [
            {"id": "S001", "type": "text", "page": 1},
            {"id": "E001", "type": "equation_or_formula", "page": 1},
            {"id": "F001", "type": "figure_caption", "page": 1},
            {"id": "T001", "type": "table_or_caption", "page": 1},
            {"id": "A001", "type": "algorithm", "page": 1, "original": "Algorithm 1 Fixture learning process 1: Input X 2: Output y"},
        ],
        "figures": [{"id": "F001", "page": 1, "caption": "Fig. 1. Model overview."}],
        "tables": [{"id": "T001", "page": 1, "caption": "Table 1. Results."}],
    }


def make_complete_reader(base: Path) -> Path:
    reader = base / "complete_reader"
    assets = reader / "assets"
    assets.mkdir(parents=True)
    (assets / "fig1.png").write_bytes(ONE_PIXEL_PNG)
    (reader / "paper.md").write_text(
        """# Fixture Paper

<a id="S001"></a>
**Source:** p.1 S001 · text

**Original:** We define a trainable Hamiltonian for graph classification.

**中文:** 我们为图分类定义一个可训练的 Hamiltonian。

**注释:** 本段给出模型对象：把 Hamiltonian 作为后续连续时间量子行走演化的可训练参数。

<a id="E001"></a>
**Source:** p.1 E001 · equation_or_formula

**Original:** The attention score is
\\[
\\operatorname{Attention}(Q,K,V,B)=\\operatorname{softmax}\\left(\\frac{QK^\\top}{\\sqrt d}+B\\right)V .
\\]

**中文:** 注意力分数由查询、键和值以及结构偏置共同给出；其中结构偏置进入 softmax 之前的 logits。

**注释:** 这个公式说明结构信息不是后处理项，而是直接改变注意力权重。

<a id="F001"></a>
### Fig. 1. Model overview / 模型概览

**Placed near:** p.1 S001

![Fig. 1](assets/fig1.png)

**Original caption:** Fig. 1. Model overview.

**中文图注:** 图 1. 模型整体结构。

**Reading note:** 关注 Hamiltonian、CTQW dynamics 和 classifier 之间的数据流。

<a id="T001"></a>
### Table 1. Results / 实验结果

**Placed near:** p.1 S001

| Model | Accuracy |
| --- | --- |
| CTQWformer | 92.54 |

**Original caption:** Table 1. Graph classification results.

**中文图注:** 表 1. 图分类结果。

**Reading note:** 该表用于定位模型性能比较，而不是给出新的算法定义。

<a id="A001"></a>
### Algorithm 1. Fixture learning process / Fixture 学习流程

**Placed near:** p.1 T001
**Source:** p.1 A001

**Original algorithm:**
1: Input: features $X$  
2: Initialize $H^{(0)}=\operatorname{MLP}(X)$  
3: Compute $U_t=e^{-iHt}$  
4: Pool $H^{(L)}$  
5: Output prediction $y$

**中文算法:**
1: 输入：特征 $X$  
2: 初始化 $H^{(0)}=\operatorname{MLP}(X)$  
3: 计算 $U_t=e^{-iHt}$  
4: 汇聚 $H^{(L)}$  
5: 输出预测 $y$

**Reading note:** 算法必须保留逐行输入、演化、池化和输出步骤，不能写成摘要。
""",
        encoding="utf-8",
    )
    write_json(reader / "source_map.json", source_map())
    return reader


def make_placeholder_reader(base: Path) -> Path:
    reader = base / "placeholder_reader"
    reader.mkdir(parents=True)
    (reader / "paper.md").write_text(
        """# Broken Placeholder

<a id="S001"></a>
**Source:** p.1 S001 · text

**Original:** We define a trainable Hamiltonian for graph classification.

**中文:** 【待忠实翻译】本栏必须逐段忠实翻译 Original。

**注释:** 本段说明 Hamiltonian 的建模角色。
""",
        encoding="utf-8",
    )
    write_json(reader / "source_map.json", source_map())
    return reader


def make_structurally_broken_reader(base: Path) -> Path:
    reader = base / "structurally_broken_reader"
    reader.mkdir(parents=True)
    (reader / "paper.md").write_text(
        """# Broken Structure

<a id="S001"></a>
**Source:** p.1 S001 · text

**Original:** We define a trainable Hamiltonian for graph classification.

**中文:** 我们为图分类定义一个可训练的 Hamiltonian。

**注释:** 本段给出 Hamiltonian 在模型中的位置。

<a id="E001"></a>
**Source:** p.1 E001 · equation_or_formula

**Original:** QKT √ d

**中文:** 这一项表示查询和键的相似度需要按维度缩放。

**注释:** 这里缺少正式 LaTeX 公式，应当被结构校验拦截。
""",
        encoding="utf-8",
    )
    write_json(reader / "source_map.json", source_map())
    return reader


def assert_ok(result: subprocess.CompletedProcess[str], context: str) -> None:
    if result.returncode != 0:
        raise AssertionError(f"{context} failed unexpectedly\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")


def assert_fails_with(result: subprocess.CompletedProcess[str], needle: str, context: str) -> None:
    combined = result.stdout + "\n" + result.stderr
    if result.returncode == 0 or needle not in combined:
        raise AssertionError(
            f"{context} did not fail with {needle!r}\ncode={result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="reader_e2e_", dir=ROOT) as tmp:
        base = Path(tmp)

        complete = make_complete_reader(base)
        complete_result = run_converter(complete)
        assert_ok(complete_result, "complete reader")
        html_path = complete / "reader_interactive.html"
        if not html_path.exists():
            raise AssertionError("complete reader did not write reader_interactive.html")
        for ledger_name in (
            "reader_manifest.json",
            "concept_ledger.json",
            "formula_ledger.json",
            "figure_table_ledger.json",
            "claim_contribution_ledger.json",
            "annotation_metadata.json",
            "structure_validation_report.json",
            "algorithm_ledger.json",
            "normalized_reader.md",
        ):
            if not (complete / "reader_wiki" / ledger_name).exists():
                raise AssertionError(f"missing reader_wiki ledger: {ledger_name}")
        html_text = html_path.read_text(encoding="utf-8")
        for snippet in ('id="MathJax-script"', "function closePanel()", "closePanel();"):
            if snippet not in html_text:
                raise AssertionError(f"missing generated HTML contract snippet: {snippet}")
        for snippet in ('class="algorithm-card"', "Original Algorithm", "中文算法"):
            if snippet not in html_text:
                raise AssertionError(f"missing algorithm card snippet: {snippet}")

        profile = base / "knowledge_profile.json"
        write_json(profile, {
            "version": 2,
            "concepts": {
                "hamiltonian": {
                    "concept_id": "hamiltonian",
                    "label": "Hamiltonian",
                    "aliases": ["Hamiltonian"],
                    "aliases_en": ["Hamiltonian"],
                    "aliases_zh": ["哈密顿量"],
                    "translation": "哈密顿量",
                    "status": "mastered",
                }
            },
            "events": [],
            "sources": {},
        })
        annotated_result = run_converter(complete, profile=profile, annotations=True)
        assert_ok(annotated_result, "annotated complete reader")
        annotated_html = html_path.read_text(encoding="utf-8")
        for snippet in (
            'class="knowledge-gap mastered"',
            "data-concept=",
            "data-status=",
            "data-source-anchor=",
            "data-concept-type=",
            "data-alias-zh=",
            "data-concept-id=",
        ):
            if snippet not in annotated_html:
                raise AssertionError(f"missing knowledge mark metadata: {snippet}")

        placeholder = make_placeholder_reader(base)
        assert_fails_with(
            run_converter(placeholder),
            "reader-wiki validation failed",
            "placeholder reader",
        )

        broken = make_structurally_broken_reader(base)
        assert_fails_with(
            run_converter(broken),
            "reader-wiki validation failed",
            "structurally broken reader",
        )

    print("reader-skill E2E passed: valid reader builds, placeholder and structural defects fail.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
