# -*- coding: utf-8 -*-
"""Build a source-grounded explanation report from reader feedback JSON."""

from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATUS_LABELS = {
    "mastered": "已掌握",
    "known": "已理解",
    "learning": "学习中",
    "unknown": "不清楚",
    "unrated": "未判断",
    "": "未判断",
}

CONFUSION_LABELS = {
    "term_definition": "术语定义",
    "paper_usage": "论文用法",
    "math_step": "数学步骤",
    "algorithm_step": "算法步骤",
    "assumption": "隐含假设",
    "evidence": "证据/图表",
    "relation": "概念关系",
    "other": "其他",
    "": "未指定",
}

CONCEPT_EXPLANATIONS = {
    "time-dependent schrödinger equation (tdse)": {
        "cn": "含时薛定谔方程（TDSE）",
        "core": "TDSE 是量子态实时演化的基本方程：哈密顿量 H 决定态矢量随时间如何变化。",
        "paper": "在这篇文章里，TDSE 是最完整、最严格的目标动力学。CETE 和 TDCSE 都是在试图用更适合量子算法的形式来等价或近似地实现 TDSE。",
        "watch": "你已把它标为 known，所以它可以作为阅读锚点：后面所有 contracted、ansatz、unitary 都是在问怎样更经济地实现 TDSE。",
    },
    "correlation-efficient time-evolution (cete) algorithm": {
        "cn": "相关高效时间演化算法（CETE）",
        "core": "CETE 的目标是用较少、较有物理结构的相关操作来模拟多体系统的实时演化，而不是机械地堆叠很多短时间传播子。",
        "paper": "本文从 TDCSE 与 TDSE 的等价关系出发，选择由双电子反厄米生成元指数化得到的 ansatz，并通过迭代残差/梯度构造双电子酉操作。",
        "watch": "难点不在名字，而在三层连接：TDSE 是目标，TDCSE 给出二体收缩条件，CETE 把这个条件转成可执行的量子线路更新。",
    },
    "time-dependent contracted schrödinger equation (tdcse)": {
        "cn": "含时收缩薛定谔方程（TDCSE）",
        "core": "TDCSE 可以理解为把完整 TDSE 投影/收缩到双电子算符层面的方程。它关注的是约化密度矩阵层面的动力学条件。",
        "paper": "本文的关键理论点是：当哈密顿量最多只有成对相互作用时，满足所有合适的双电子收缩条件可以推出完整 TDSE 成立；反过来 TDSE 成立当然也会使其收缩形式成立。",
        "watch": "不要把 TDCSE 误解为另一个近似方程。本文强调的是在给定条件下它和 TDSE 的等价性，然后利用这个等价性设计 ansatz。",
    },
    "ansatz": {
        "cn": "拟设",
        "core": "ansatz 是你预先选择的一类状态或线路形式，后面通过参数或迭代更新在这类形式里寻找目标态。",
        "paper": "本文的 ansatz 不是任意参数化线路，而是由一串双电子酉算符构成。这个选择来自 TDCSE 推出的二体生成元结构。",
        "watch": "阅读时要问：这个 ansatz 的表达能力来自哪里，为什么它比普通 Trotter/顺序传播更相关高效。",
    },
    "slater determinant": {
        "cn": "Slater 行列式",
        "core": "Slater 行列式是满足费米子反对称性的平均场参考态，可以用一组被占据的自旋轨道来表示。",
        "paper": "H2 示例中，Hartree-Fock 基态和一个双激发态都可以看成不同的 Slater 行列式占据模式。作者利用只有这两个态耦合的结构，把问题约化到单量子比特。",
        "watch": "这里的重点不是行列式计算本身，而是“占据模式 -> 量子比特基态”的编码关系。",
    },
    "two-electron unitary": {
        "cn": "双电子酉算符",
        "core": "双电子酉算符通常形如 exp(A)，其中 A 是反厄米的二体费米子激发算符。反厄米保证指数化后是酉操作。",
        "paper": "CETE 用这类酉操作逐步修正 ansatz，使其沿着最能降低 TDSE/TDCSE 残差的二体方向前进。",
        "watch": "“双电子”不是说只能模拟两个电子，而是生成元最多同时作用在两个电子自由度上，因此与二体相互作用和 2-RDM 自然匹配。",
    },
    "one-particle reduced density matrix (1-rdm)": {
        "cn": "单粒子约化密度矩阵（1-RDM）",
        "core": "1-RDM 记录单粒子占据和相干信息，典型元素是 <a_p^dagger a_q>。",
        "paper": "图 1 测量的是 H2 的对角 1-RDM 元素随时间的变化。它用来检查模拟出来的电子占据动力学是否贴近无噪声参考。",
        "watch": "它是可观测量，不是完整波函数。图 1 看的是演化后投影到单粒子层面的正确性。",
    },
    "two-particle reduced density matrix (2-rdm)": {
        "cn": "双粒子约化密度矩阵（2-RDM）",
        "core": "2-RDM 记录二体关联，典型元素是 <a_p^dagger a_q^dagger a_s a_r>。",
        "paper": "因为本文的哈密顿量最多含二体相互作用，能量和 TDCSE 条件都可以通过 2-RDM 或二体收缩信息表达。",
        "watch": "2-RDM 是从完整多体态压缩出来的对象；CETE 的“相关高效”正是利用二体层面的充分信息。",
    },
    "pauli-sum tomography": {
        "cn": "Pauli 和层析",
        "core": "把一个可观测量写成多个 Pauli 字符串的加权和，分别测量每个字符串，再把结果按系数加回来。",
        "paper": "图 1 和图 2 中，作者每隔 0.9 Ha^-1 做 Pauli-sum tomography，每个 Pauli 字符串用 10^4 shots，从而估计 1-RDM 或能量。",
        "watch": "shot 数决定统计噪声；硬件设备和测量频率决定图中误差点的可信度。",
    },
    "sequential short-time propagators": {
        "cn": "序列短时传播子",
        "core": "这是常见的时间演化做法：把总时间切成很多小步，每一步应用短时间传播近似。",
        "paper": "本文把它作为比较基线。CETE 试图用更少、更贴近相关结构的 ansatz 达到更好的硬件表现或更小偏差。",
        "watch": "它不是错的方法，而是可能在深线路、噪声、误差累积上不如 CETE。",
    },
    "ibm_fez": {
        "cn": "ibm_fez",
        "core": "这是 IBM Quantum 的具体硬件设备名。文中保留英文设备名。",
        "paper": "图 1 和图 2 的实验测量都在 ibm_fez 的 137 号量子比特上完成，因此硬件噪声、读出误差和 shot 噪声会影响数据点。",
        "watch": "它不是算法概念，而是实验平台信息。读图时把它理解为“真实硬件条件”。",
    },
}

BLOCK_EXPLANATIONS = {
    "S005": {
        "title": "哈密顿量为什么能写成厄米双电子算符",
        "core": "这里说的“双电子算符”不是系统只有两个电子，而是哈密顿量最多包含一体项和二体项；这些项可以统一写进 a^dagger a^dagger a a 形式的二体费米子算符里。",
        "paper": "2K 张量把一电子积分和二电子积分的信息打包成 two-electron reduced Hamiltonian。厄米性保证能量期望值为实数，也与酉时间演化相容。",
        "watch": "把“一体/二体相互作用”与“二电子算符表示”区分开。后者是二次量子化中的表达形式。",
    },
    "S006": {
        "title": "2K 与 TDCSE 的角色",
        "core": "2K 是双电子约化哈密顿量，包含一电子积分和二电子积分信息。它让能量和动力学条件可以在二体约化层面表达。",
        "paper": "作者从 TDSE 出发，用二体算符收缩得到 TDCSE。由于 H 最多是二体的，这种收缩没有丢掉本文所需的动力学信息。",
        "watch": "这里的 reduced 不是简单删掉变量，而是把完整多体方程投影到足以描述二体相互作用的对象上。",
    },
    "S009": {
        "title": "TDCSE 推出 TDSE 的数学逻辑",
        "core": "作者把 TDCSE 的残差用反厄米二体算符的系数加权并求和，得到 TDSE 残差范数/方差形式。",
        "paper": "这个量具有正定性质：当且仅当 TDSE 残差为零时才为零。因此如果所有 TDCSE 收缩条件都满足，就能推出 TDSE 满足；反过来 TDSE 成立，其任意二体收缩自然也为零。",
        "watch": "关键是“残差范数为零”而不是普通代数消项。你可以把它理解为证明两个方程组在这个物理条件下等价。",
    },
    "S011": {
        "title": "为什么出现反厄米双电子生成元",
        "core": "量子态时间演化的切向量可以写成某个反厄米生成元作用在当前态上；反厄米生成元指数化后给出酉操作。",
        "paper": "TDCSE 的等价性说明，只需要二体层面的生成元就可以最小地表示所需的演化方向，于是自然得到由双电子酉算符组成的 CETE ansatz。",
        "watch": "“最小”指在本文二体生成元空间里足够表达所需动力学，不是说任意多体酉都能无条件压成一个简单二体门。",
    },
    "S016": {
        "title": "迭代构造双电子酉算符",
        "core": "每一步都比较目标态和当前 ansatz 的差距，把残差看成保真度的梯度方向，然后选一个最能提高重叠的二体生成元更新线路。",
        "paper": "这把抽象的 TDCSE 条件变成了算法步骤：计算/估计残差，选择双电子酉，更新 ansatz，重复直到残差足够小。",
        "watch": "这里的 residual 不是错误提示，而是“下一步应该沿哪个二体相关方向修正”的信号。",
    },
    "S017": {
        "title": "H2 应用示例的设置",
        "core": "H2/STO-3G 是一个小而可控的基准体系。0.735 Å 是接近平衡键长的设置；Ha^-1 是原子单位时间，18 Ha^-1 约为 435.4 attoseconds。",
        "paper": "作者用 0.90 Ha^-1 的时间步，并把每步 Trotter 化为 0.03 Ha^-1 子步。初态是从 Hartree-Fock 基态出发的双激发，目的是制造非平凡但仍可控的实时动力学。",
        "watch": "这段把理论算法落到实验验证：体系、基组、总演化时间、步长、初态全都决定后面图 1/图 2 的含义。",
    },
    "S018": {
        "title": "Slater 行列式到单量子比特的约化",
        "core": "四个自旋轨道的占据可写成 bitstring。文中由于演化只耦合 HF 基态和一个双激发态，动力学实际落在二维子空间。",
        "paper": "作者把这两个 Slater determinant 态映射成单量子比特的 |0> 和 |1>。因此 1-RDM、2-RDM 和哈密顿量也能在这个单量子比特空间里表示和测量。",
        "watch": "这不是说真实 H2 只有一个量子比特，而是这个特定初态和演化结构允许有效二维约化。",
    },
    "F001": {
        "title": "图 1 的证据含义",
        "core": "图 1 看的是 H2 对角 1-RDM 元素随时间的测量值，也就是电子占据动力学是否正确。",
        "paper": "CETE 和序列演化都和无噪声 state-vector 参考线比较。数据点越贴近实线，说明该方法在硬件测量下越接近理想演化。",
        "watch": "图注里的 Pauli-sum tomography、10^4 shots、ibm_fez 137 号量子比特说明这是实际测量结果，不只是仿真曲线。",
    },
    "F002": {
        "title": "图 2 的证据含义",
        "core": "图 2 看的是 H2 能量随时间的测量值。能量是由 Pauli 字符串测量结果加权求和得到的。",
        "paper": "如果 CETE 的能量点更贴近无噪声参考线，而 sequential evolution 偏离更明显，就支持 CETE 在这个实验设置下有更好的时间演化表现或更小误差累积。",
        "watch": "这里的证据不是单个时间点，而是整条时间序列相对参考线的趋势。",
    },
    "S022": {
        "title": "致谢段落",
        "core": "这是资金和协助致谢，不是技术论证的一部分。",
        "paper": "除非你在追踪项目来源或硬件/合作背景，否则它不影响 CETE、TDCSE、ansatz 或实验结果的理解。",
        "watch": "可归档为非技术标注。",
    },
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_html(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def clean_inline(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def clip(text: Any, limit: int = 420) -> str:
    value = clean_inline(text)
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def norm_key(text: str) -> str:
    return re.sub(r"\s+", " ", clean_inline(text).casefold())


def bullet(label: str, value: Any, limit: int = 600) -> str:
    value_text = clip(value, limit)
    if not value_text:
        value_text = "（无）"
    return f"- **{label}**：{value_text}"


def inline_markdown_to_html(text: str) -> str:
    escaped = html_lib.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def heading_id(text: str, index: int) -> str:
    ascii_slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if ascii_slug:
        return f"h-{index}-{ascii_slug[:48]}"
    return f"h-{index}"


def mathjax_script_src(value: str | None) -> str:
    src = clean_inline(value)
    if not src or src.lower() == "none":
        return ""
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", src):
        return src
    path = Path(src)
    try:
        if path.exists():
            return path.resolve().as_uri()
    except OSError:
        return src
    return src


def markdown_report_to_html(markdown_text: str, title: str, mathjax_url: str | None) -> str:
    body: list[str] = []
    toc: list[tuple[int, str, str]] = []
    list_mode: str | None = None
    heading_index = 0

    def close_list() -> None:
        nonlocal list_mode
        if list_mode:
            body.append(f"</{list_mode}>")
            list_mode = None

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip()
        if not line:
            close_list()
            body.append("")
            continue

        heading_match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if heading_match:
            close_list()
            level = len(heading_match.group(1))
            text = heading_match.group(2)
            heading_index += 1
            element_id = heading_id(text, heading_index)
            toc.append((level, element_id, clean_inline(text)))
            body.append(f'<h{level} id="{element_id}">{inline_markdown_to_html(text)}</h{level}>')
            continue

        if line.startswith("- "):
            if list_mode != "ul":
                close_list()
                body.append("<ul>")
                list_mode = "ul"
            body.append(f"<li>{inline_markdown_to_html(line[2:])}</li>")
            continue

        ordered_match = re.match(r"^\d+\.\s+(.+)$", line)
        if ordered_match:
            if list_mode != "ol":
                close_list()
                body.append("<ol>")
                list_mode = "ol"
            body.append(f"<li>{inline_markdown_to_html(ordered_match.group(1))}</li>")
            continue

        close_list()
        body.append(f"<p>{inline_markdown_to_html(line)}</p>")

    close_list()

    toc_items = []
    for level, element_id, text in toc:
        if level <= 3:
            toc_items.append(
                f'<a class="toc-level-{level}" href="#{html_lib.escape(element_id)}">{inline_markdown_to_html(text)}</a>'
            )
    nav = "\n".join(toc_items)
    mathjax_src = mathjax_script_src(mathjax_url)
    mathjax = ""
    if mathjax_src:
        mathjax = f"""
<script>
window.MathJax = {{
  tex: {{ inlineMath: [['$', '$'], ['\\\\(', '\\\\)']], displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']] }},
  chtml: {{ displayAlign: 'left', displayIndent: '0' }},
  options: {{ skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'] }}
}};
</script>
<script async src="{html_lib.escape(mathjax_src)}"></script>
"""

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html_lib.escape(title)}</title>
<style>
:root {{
  color-scheme: light;
  --bg: #f7f7f4;
  --paper: #ffffff;
  --ink: #1f2933;
  --muted: #667085;
  --line: #d9dee7;
  --accent: #2563eb;
  --soft: #eef4ff;
  --code: #f3f4f6;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
  line-height: 1.68;
}}
.layout {{
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
  gap: 24px;
  width: min(1480px, calc(100% - 32px));
  margin: 0 auto;
  padding: 28px 0 48px;
}}
nav {{
  position: sticky;
  top: 16px;
  align-self: start;
  max-height: calc(100vh - 32px);
  overflow: auto;
  padding: 16px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.86);
}}
nav h2 {{
  margin: 0 0 10px;
  font-size: 14px;
  color: var(--muted);
}}
nav a {{
  display: block;
  color: #334155;
  text-decoration: none;
  border-left: 2px solid transparent;
  padding: 5px 0 5px 8px;
  font-size: 13px;
}}
nav a:hover {{ border-color: var(--accent); color: var(--accent); background: var(--soft); }}
.toc-level-1 {{ font-weight: 700; }}
.toc-level-2 {{ margin-left: 8px; }}
.toc-level-3 {{ margin-left: 18px; color: var(--muted); }}
main {{
  min-width: 0;
  background: var(--paper);
  border: 1px solid var(--line);
  padding: 32px;
}}
h1, h2, h3 {{
  line-height: 1.25;
  letter-spacing: 0;
}}
h1 {{
  margin: 0 0 24px;
  font-size: 30px;
}}
h2 {{
  margin: 36px 0 12px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  font-size: 22px;
}}
h3 {{
  margin: 26px 0 10px;
  font-size: 18px;
  color: #0f172a;
}}
p {{ margin: 10px 0; }}
ul, ol {{ margin: 8px 0 16px; padding-left: 24px; }}
li {{ margin: 5px 0; }}
strong {{ color: #111827; }}
code {{
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--code);
  font-family: Consolas, "Cascadia Mono", monospace;
  font-size: 0.92em;
}}
@media (max-width: 900px) {{
  .layout {{ display: block; width: min(100% - 20px, 760px); padding: 12px 0 32px; }}
  nav {{ position: static; max-height: none; margin-bottom: 12px; }}
  main {{ padding: 20px; }}
  h1 {{ font-size: 24px; }}
}}
@media print {{
  body {{ background: #fff; }}
  .layout {{ display: block; width: 100%; padding: 0; }}
  nav {{ display: none; }}
  main {{ border: 0; padding: 0; }}
}}
</style>
{mathjax}
</head>
<body>
<div class="layout">
<nav aria-label="目录">
<h2>目录</h2>
{nav}
</nav>
<main>
{chr(10).join(body)}
</main>
</div>
</body>
</html>
"""


def find_feedback_path(value: str | None) -> Path:
    if not value:
        raise SystemExit("Provide --feedback or a reader directory as the positional input.")
    path = Path(value)
    if path.is_file():
        return path
    if path.is_dir():
        candidates = sorted(path.glob("reader_feedback*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not candidates:
            raise SystemExit(f"No reader_feedback*.json file found in {path}")
        return candidates[0]
    raise SystemExit(f"Feedback path does not exist: {path}")


def infer_reader_dir(feedback_path: Path, feedback: dict[str, Any], explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    reader_path = clean_inline(feedback.get("reader_path"))
    if reader_path and Path(reader_path).exists():
        return Path(reader_path)
    return feedback_path.parent


def find_lean_html_script(start: Path) -> Path | None:
    resolved = start.resolve()
    for base in [resolved, *resolved.parents]:
        candidate = base / "skills" / "utils" / "lean-html-skill" / "scripts" / "lean_html.py"
        if candidate.exists():
            return candidate
    return None


def attach_lean_feedback_panel(html_path: Path, feedback_path: Path, search_start: Path) -> str:
    script = find_lean_html_script(search_start)
    if not script:
        return "lean-html-skill not found; HTML feedback2 panel was not attached"
    command = [
        sys.executable,
        str(script),
        "attach-feedback",
        "--html",
        str(html_path),
        "--feedback",
        str(feedback_path),
        "--source",
        "read-feedback-skill",
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").strip()
        return f"lean-html-skill failed to attach feedback2 panel: {message}"
    return ""


def find_profile(reader_dir: Path, explicit: str | None) -> Path | None:
    if explicit:
        return Path(explicit)
    current = reader_dir.resolve()
    for base in [current, *current.parents]:
        candidate = base / ".agents" / "reader-learner" / "knowledge_profile.json"
        if candidate.exists():
            return candidate
    return None


def load_source_map(path: Path | None) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], list[str]]:
    if not path or not path.exists():
        return {}, {}, ["source_map.json not found"]
    data = load_json(path)
    warnings: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    for block in data.get("blocks", []) or []:
        block_id = clean_inline(block.get("id"))
        if block_id:
            by_id[block_id] = dict(block)

    for fig in data.get("figures", []) or []:
        fig_id = clean_inline(fig.get("id"))
        if not fig_id:
            continue
        fig_entry = dict(fig)
        fig_entry["type"] = "figure" if fig_id.startswith("F") else "table"
        caption_id = clean_inline(fig.get("caption_id"))
        caption = by_id.get(caption_id, {})
        if caption:
            fig_entry["original_text"] = caption.get("original_text", "")
            fig_entry["translation"] = caption.get("translation", "")
            fig_entry["caption_page"] = caption.get("page", "")
        by_id[fig_id] = fig_entry

    glossary: dict[str, dict[str, Any]] = {}
    for entry in data.get("glossary", []) or []:
        term = clean_inline(entry.get("term"))
        if term:
            glossary[norm_key(term)] = dict(entry)
    return by_id, glossary, warnings


def find_profile_entry(profile: dict[str, Any] | None, concept: str) -> tuple[str, dict[str, Any] | None]:
    if not profile:
        return "", None
    concepts = profile.get("concepts", {}) or {}
    key = norm_key(concept)
    for name, entry in concepts.items():
        candidates = [name]
        if isinstance(entry, dict):
            candidates.append(str(entry.get("label", "")))
            candidates.extend(str(alias) for alias in entry.get("aliases", []) or [])
        for candidate in candidates:
            if norm_key(candidate) == key:
                return name, entry
    for name, entry in concepts.items():
        candidates = [name]
        if isinstance(entry, dict):
            candidates.append(str(entry.get("label", "")))
            candidates.extend(str(alias) for alias in entry.get("aliases", []) or [])
        for candidate in candidates:
            candidate_key = norm_key(candidate)
            if key and candidate_key and (key in candidate_key or candidate_key in key):
                return name, entry
    return "", None


def find_glossary_entry(glossary: dict[str, dict[str, Any]], concept: str) -> dict[str, Any] | None:
    key = norm_key(concept)
    if key in glossary:
        return glossary[key]
    for term_key, entry in glossary.items():
        if key and (key in term_key or term_key in key):
            return entry
    return None


def concept_explanation(concept: str) -> dict[str, str] | None:
    key = norm_key(concept)
    if key in CONCEPT_EXPLANATIONS:
        return CONCEPT_EXPLANATIONS[key]
    for term_key, entry in CONCEPT_EXPLANATIONS.items():
        if key and (key in term_key or term_key in key):
            return entry
    return None


def block_explanation(block_id: str) -> dict[str, str] | None:
    return BLOCK_EXPLANATIONS.get(clean_inline(block_id))


def source_context_for_item(item: dict[str, Any], source_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    block_id = clean_inline(item.get("block_id") or item.get("bilingual_block_id"))
    return source_by_id.get(block_id, {})


def profile_status(profile_entry: dict[str, Any] | None) -> str:
    if not profile_entry:
        return "（未在 profile 中找到）"
    status = clean_inline(profile_entry.get("status")) or "unrated"
    label = STATUS_LABELS.get(status, status)
    return f"{label} / {status}"


def status_text(status: str) -> str:
    return f"{STATUS_LABELS.get(status, status or '未判断')} / {status or 'unrated'}"


def needs_explanation(item: dict[str, Any]) -> bool:
    status = clean_inline(item.get("status")) or "unrated"
    if bool(item.get("needs_explanation")):
        return True
    if status in {"unknown", "learning", "unrated"}:
        return True
    return bool(clean_inline(item.get("user_question")) or clean_inline(item.get("selected_text")))


def build_direct_explanation(
    item: dict[str, Any],
    source: dict[str, Any],
    glossary_entry: dict[str, Any] | None,
    profile_entry: dict[str, Any] | None,
) -> list[str]:
    concept = clean_inline(item.get("concept") or item.get("selected_text") or "未命名反馈")
    block_id = clean_inline(item.get("block_id") or item.get("bilingual_block_id"))
    kind = clean_inline(item.get("annotation_kind"))
    confusion = clean_inline(item.get("confusion_type"))
    cexp = concept_explanation(concept)
    bexp = block_explanation(block_id)
    prefer_block = bool(bexp) and (kind == "freeform" or block_id.startswith(("S", "F", "C")))
    primary = bexp if prefer_block else cexp
    secondary = cexp if prefer_block else bexp

    lines: list[str] = []
    lines.append("**直接解释**")

    if primary:
        lines.append(f"- **核心意思**：{primary['core']}")
        lines.append(f"- **本文用法**：{primary['paper']}")
        lines.append(f"- **容易卡住的点**：{primary['watch']}")
        if secondary and secondary is not primary:
            lines.append(f"- **相关术语补充**：{secondary['core']}")
    else:
        source_hint = clean_inline(item.get("source_excerpt") or source.get("translation") or source.get("original_text"))
        if source_hint:
            lines.append(f"- **核心意思**：这条标注来自具体文本，不是标准术语。先按原文语境理解：{clip(source_hint, 260)}")
        else:
            lines.append("- **核心意思**：这条反馈没有足够的上下文，建议回到对应 HTML 标注位置重新查看前后段。")
        lines.append("- **本文用法**：把它作为一个局部问题处理，优先结合相邻 source block，而不是只按词典解释。")

    if glossary_entry:
        trans = clean_inline(glossary_entry.get("translation"))
        note = clean_inline(glossary_entry.get("note"))
        if trans or note:
            lines.append(f"- **术语表补充**：{trans or '（无译名）'}；{note or '（无备注）'}")

    if profile_entry:
        ai_explanation = clean_inline(profile_entry.get("ai_explanation"))
        if ai_explanation:
            lines.append(f"- **profile 已有解释**：{clip(ai_explanation, 240)}")

    if confusion:
        lines.append(confusion_guidance(confusion))

    return lines


def confusion_guidance(confusion: str) -> str:
    if confusion == "math_step":
        return "- **按数学步骤看**：先找残差/算符/矩阵对象，再看作者怎样通过收缩、加权、范数为零或指数化把它转成下一步结论。"
    if confusion == "paper_usage":
        return "- **按论文用法看**：不要停在通用定义，要问作者在这里把它用作理论证明、线路构造、测量对象还是比较基线。"
    if confusion == "algorithm_step":
        return "- **按算法步骤看**：把输入、更新方向、停止条件和输出分开；CETE 中常见输入是当前 ansatz/残差，输出是下一段双电子酉操作。"
    if confusion == "evidence":
        return "- **按证据看**：先识别横轴、纵轴、参考线和比较对象，再判断数据是否支持作者说的方法优势。"
    if confusion == "relation":
        return "- **按关系看**：把这段放到链条里读：TDSE 目标 -> TDCSE 等价条件 -> 双电子酉 ansatz -> H2 实验验证。"
    if confusion == "assumption":
        return "- **按假设看**：优先检查哈密顿量是否最多二体、体系是否被约化、测量是否在有限 shot 和真实硬件上进行。"
    if confusion == "term_definition":
        return "- **按术语定义看**：先掌握最小定义，再回到本文看它承担的具体角色。"
    return "- **阅读建议**：这条没有指定问题类型，建议从“它是什么、本文为什么需要它、它和前后概念如何连接”三问入手。"


def source_lines(item: dict[str, Any], source: dict[str, Any]) -> list[str]:
    block_id = clean_inline(item.get("block_id") or item.get("bilingual_block_id"))
    lines = ["**来源上下文**"]
    if block_id:
        page = clean_inline(source.get("page") or source.get("caption_page"))
        source_type = clean_inline(source.get("type"))
        source_label = block_id
        if page:
            source_label += f" / p.{page}"
        if source_type:
            source_label += f" / {source_type}"
        lines.append(f"- **source**：{source_label}")
    else:
        lines.append("- **source**：（反馈中未记录 block id）")

    if clean_inline(item.get("selected_text")):
        lines.append(bullet("选中文本", item.get("selected_text"), 480))
    if clean_inline(item.get("selected_language")):
        lines.append(bullet("选中语言", item.get("selected_language"), 80))
    if clean_inline(item.get("user_question")):
        lines.append(bullet("你的原问题", item.get("user_question"), 300))
    if clean_inline(item.get("note")):
        lines.append(bullet("你的备注", item.get("note"), 300))
    if clean_inline(item.get("original_context")):
        lines.append(bullet("英文上下文", item.get("original_context"), 650))
    elif clean_inline(source.get("original_text")):
        lines.append(bullet("英文上下文", source.get("original_text"), 650))
    if clean_inline(item.get("translation_context")):
        lines.append(bullet("中文上下文", item.get("translation_context"), 650))
    elif clean_inline(source.get("translation")):
        lines.append(bullet("中文上下文", source.get("translation"), 650))
    if clean_inline(item.get("source_excerpt")):
        lines.append(bullet("反馈摘录", item.get("source_excerpt"), 650))
    if clean_inline(source.get("image_path")):
        lines.append(bullet("图表文件", source.get("image_path"), 160))
    return lines


def short_concept(item: dict[str, Any], limit: int = 90) -> str:
    return clip(item.get("concept") or item.get("selected_text") or "未命名反馈", limit)


def feedback_display_title(feedback: dict[str, Any], reader_dir: Path) -> str:
    return clean_inline(
        feedback.get("briefing_title")
        or feedback.get("paper_title")
        or feedback.get("title")
        or reader_dir.name.replace("_reader", "")
    )


def news_lens(item: dict[str, Any]) -> dict[str, str]:
    concept = clean_inline(item.get("concept") or item.get("selected_text"))
    category = clean_inline(item.get("category"))
    source_title = clean_inline(item.get("source_title"))
    excerpt = clean_inline(item.get("source_excerpt") or item.get("original_context"))
    text = norm_key(" ".join([concept, category, source_title, excerpt]))
    if any(token in text for token in ["regulation", "policy", "governance", "standard", "export control", "safety"]):
        return {
            "role": "治理/安全信号",
            "mechanism": "先区分政策对象、约束指标和执行主体：它回答的是谁被约束、按什么能力阈值约束、对模型发布或跨境访问有什么影响。",
            "math": "可把它抽象成风险评分函数 R(model, use, region)。日报里需要追的是 R 的输入变量，而不是把政策词当成技术概念。",
            "boundary": "如果你已掌握基础术语，本条真正的未知通常在“评测指标如何落到模型能力”和“政策如何改变研究/部署路径”。",
        }
    if any(token in text for token in ["infrastructure", "compute", "cloud", "neocloud", "grid", "rental"]):
        return {
            "role": "算力基础设施信号",
            "mechanism": "把它拆成供给、能耗/电网、租赁模式和训练/推理需求四层；核心不是公司新闻，而是算力供给曲线如何约束模型迭代。",
            "math": "可以写成 capacity = chips x utilization x power_limit x networking_efficiency；新闻里的不确定点通常落在 power_limit 或 utilization。",
            "boundary": "你需要标清楚自己是不懂商业模式、硬件瓶颈，还是不懂它为什么会反馈到模型能力增长。",
        }
    if any(token in text for token in ["agent", "coding", "workflow", "cli", "code review"]):
        return {
            "role": "Agentic AI 工程能力信号",
            "mechanism": "看 agent 是否闭环：任务分解 -> 工具调用 -> 代码/文档产物 -> 人类审核 -> 迭代。真正的瓶颈常在审核吞吐和错误责任边界。",
            "math": "可用吞吐近似：delivery_rate = min(agent_generation_rate, human_review_rate, test_feedback_rate)。代码生成更快不等于系统交付更快。",
            "boundary": "若你已懂 agent 概念，下一步应追问评测、审查和失败恢复机制，而不是只记产品名。",
        }
    if any(token in text for token in ["quantum walk", "mhv", "kraus", "parke", "scattering"]):
        return {
            "role": "量子行走/散射振幅理论信号",
            "mechanism": "把图或排列结构编码成量子行走路径，振幅由路径权重叠加得到；Kraus 算子说明这可能是开放系统或测量诱导的表示。",
            "math": "读法是 path amplitude = sum_paths product(edge weights)。你需要追的是路径空间、归一化和物理振幅之间的映射。",
            "boundary": "这里的未知多半不是“量子行走是什么”，而是它为什么能表达 color-ordered MHV/Parke-Taylor 结构。",
        }
    if any(token in text for token in ["qpipe", "qubo", "llm-based quantum", "ai for quantum", "quantum applications"]):
        return {
            "role": "AI for Quantum 工作流信号",
            "mechanism": "看 LLM/agent 在量子应用链条里承担哪一步：问题建模、QUBO 化、线路生成、后端选择、结果诊断或文档化。",
            "math": "QUBO 的核心形式是 minimize x^T Q x, x in {0,1}^n。新闻里要追的是自然语言任务如何被约束成 Q 矩阵。",
            "boundary": "如果你已懂量子算法入口，本条要补的是 agent 工作流如何避免把物理约束翻译错。",
        }
    if any(token in text for token in ["error correction", "syndrome", "logical pauli", "luci"]):
        return {
            "role": "量子纠错信号",
            "mechanism": "纠错新闻要按 physical error -> syndrome -> decoder -> logical error 读；不要把硬件实验和理论阈值混在一起。",
            "math": "综合征可看作 s = H e mod 2，decoder 要从 s 反推出最可能的错误 e；logical Pauli error 是穿过码空间保护后的残余逻辑错误。",
            "boundary": "若你对 QEC 还在 learning，优先补 syndrome density、decoder 假设和 logical/physical error 的区别。",
        }
    if any(token in text for token in ["neutral-atom", "compilation", "transport", "graph coloring", "rydberg"]):
        return {
            "role": "中性原子编译/调度信号",
            "mechanism": "中性原子平台的核心是把逻辑门需求映射到可移动原子阵列和 Rydberg 相互作用约束；编译问题常变成空间排布与运输调度。",
            "math": "图着色/调度形式可理解为给冲突图 G 的节点分配时间槽或颜色，使相邻冲突节点不同色，同时最小化移动和空闲时间。",
            "boundary": "这里要分清物理平台限制、编译优化目标和算法复杂度三件事。",
        }
    if any(token in text for token in ["reservoir", "symmetry", "equivariance", "hamiltonian dynamics", "observable orbit"]):
        return {
            "role": "量子机器学习结构信号",
            "mechanism": "量子 reservoir 用固定动力学产生高维特征；symmetry/equivariance 说明可观测量在群作用下成轨道，能减少训练或补全观测。",
            "math": "若群 G 作用在 observable O 上，轨道是 {gOg^-1 | g in G}；equivariance 要求模型输出随群作用同步变换。",
            "boundary": "本条的知识边界常在群对称如何具体减少样本复杂度，而不是 reservoir 的口号定义。",
        }
    if any(token in text for token in ["economics", "productivity", "labor", "monopoly", "redistribution"]):
        return {
            "role": "AI 经济影响信号",
            "mechanism": "把新闻拆成生产率提升、替代效应、市场集中和再分配政策；同一项 AI 进展可能同时提高产出并扩大不平等。",
            "math": "粗略看作 wage/share change = productivity_gain - displacement_pressure - monopoly_rent；政策讨论是在调这些项的权重。",
            "boundary": "如果概念不清，优先标注你不懂的是经济机制、政策工具，还是研究结论的证据强度。",
        }
    return {
        "role": "新闻知识信号",
        "mechanism": "先读 source claim，再抽出技术机制、限制条件和与你研究的关系；不要把来源标题、公司名和核心概念混成一个概念。",
        "math": "可统一写成 claim -> mechanism -> evidence -> implication 的四步链条。若缺少 evidence，本条只能作为待跟踪信号。",
        "boundary": "本条需要靠你的二次反馈继续细分：是不懂术语、机制、证据，还是不确定它和量子/AI 研究主线的关系。",
    }


def build_news_direct_explanation(
    item: dict[str, Any],
    profile_entry: dict[str, Any] | None,
) -> list[str]:
    concept = clean_inline(item.get("concept") or item.get("selected_text") or "未命名反馈")
    category = clean_inline(item.get("category")) or "未分类"
    source_title = clean_inline(item.get("source_title")) or "未记录来源标题"
    source_url = clean_inline(item.get("source_url"))
    status = clean_inline(item.get("status")) or "unrated"
    question = clean_inline(item.get("user_question") or item.get("note"))
    excerpt = clean_inline(item.get("source_excerpt") or item.get("original_context"))
    lens = news_lens(item)
    lines = ["**新闻知识点解析**"]
    lines.append(f"- **本条角色**：{lens['role']}；日报分类为 `{category}`，来源是 {source_title}。")
    lines.append(f"- **你当前状态**：{status_text(status)}。{'这条可作为已知锚点。' if status in {'known', 'mastered'} and not question else '这条需要继续解释或追踪。'}")
    lines.append(f"- **机制拆解**：{lens['mechanism']}")
    lines.append(f"- **数学/物理读法**：{lens['math']}")
    lines.append(f"- **按画像补边界**：{lens['boundary']}")
    if excerpt:
        lines.append(f"- **短上下文锚点**：{clip(excerpt, 240)}")
    if source_url:
        lines.append(f"- **来源 URL**：{source_url}")
    if question:
        lines.append(f"- **你的自由问题/备注**：{question}")
    if profile_entry:
        ai_explanation = clean_inline(profile_entry.get("ai_explanation"))
        if ai_explanation:
            lines.append(f"- **画像已有解释**：{clip(ai_explanation, 220)}")
    return lines


def news_route_lines() -> list[str]:
    return [
        "1. 先按来源与 category 分组：policy/safety、infrastructure、agentic AI、AI for Quantum、quantum theory、QEC、QML。",
        "2. 对 known/mastered 条目只当锚点，不展开大段背景；重点检查它能否帮助你理解相邻 unknown/learning 条目。",
        "3. 对 unknown/learning 条目按 source claim -> 技术机制 -> 证据强度 -> 研究相关性拆解。",
        "4. 读完 HTML 后用二次标注面板导出 `news_feedback2.json`，再交给 `reader-learner` 迭代画像。",
    ]


def news_learning_focus_lines(items: list[dict[str, Any]]) -> list[str]:
    weak = [item for item in items if clean_inline(item.get("status")) in {"unknown", "learning", "unrated"}]
    category_counts = Counter(clean_inline(item.get("category")) or "未分类" for item in weak)
    focus = [f"- {category}：{count} 个需要继续解释/追踪的知识点。" for category, count in category_counts.most_common(6)]
    return focus or ["- 本次日报反馈主要是 known/mastered，可把它作为后续新闻阅读的锚点集合。"]


def news_followup_lines(item: dict[str, Any]) -> list[str]:
    concept = short_concept(item, 40)
    category = clean_inline(item.get("category")) or "当前 category"
    return [
        f"- “请把 `{concept}` 按 source claim -> mechanism -> evidence -> implication 四步拆开。”",
        f"- “请解释 `{category}` 里这条新闻和我的量子/AI 研究知识边界有什么关系。”",
    ]


def build_report(
    feedback_path: Path,
    feedback: dict[str, Any],
    reader_dir: Path,
    profile_path: Path | None,
    profile: dict[str, Any] | None,
    source_map_path: Path | None,
    source_by_id: dict[str, dict[str, Any]],
    glossary: dict[str, dict[str, Any]],
    warnings: list[str],
) -> str:
    items = list(feedback.get("items", []) or [])
    news_mode = is_news_feedback(feedback, feedback_path)
    title = feedback_display_title(feedback, reader_dir)
    status_counts = Counter((clean_inline(item.get("status")) or "unrated") for item in items)
    kind_counts = Counter((clean_inline(item.get("annotation_kind")) or "unknown") for item in items)
    known_items = [item for item in items if clean_inline(item.get("status")) in {"known", "mastered"}]
    explain_items = [item for item in items if needs_explanation(item)]

    lines: list[str] = []
    lines.append(f"# {title} - 阅读反馈全解析")
    lines.append("")
    lines.append("## 生成信息")
    lines.append("")
    lines.append(bullet("生成时间", datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"), 120))
    lines.append(bullet("feedback", str(feedback_path), 260))
    lines.append(bullet("reader directory", str(reader_dir), 260))
    lines.append(bullet("profile", str(profile_path) if profile else "未加载", 260))
    lines.append(bullet("source_map", str(source_map_path) if source_by_id else "未加载", 260))
    lines.append(bullet("feedback items", len(items), 80))
    if warnings:
        lines.append(bullet("warnings", "; ".join(warnings), 400))
    lines.append("")

    lines.append("## 个人知识边界快照")
    lines.append("")
    lines.append("### 状态统计")
    lines.append("")
    for status, count in sorted(status_counts.items()):
        lines.append(f"- {status_text(status)}：{count}")
    lines.append("")
    lines.append("### 标注类型")
    lines.append("")
    for kind, count in sorted(kind_counts.items()):
        lines.append(f"- {kind}：{count}")
    lines.append("")
    lines.append("### 已知锚点")
    lines.append("")
    if known_items:
        for item in known_items:
            lines.append(f"- {short_concept(item)}")
    else:
        lines.append("- （这次反馈没有 known/mastered 条目）")
    lines.append("")
    lines.append("### 需要优先解释")
    lines.append("")
    if explain_items:
        for item in explain_items:
            status = clean_inline(item.get("status")) or "unrated"
            block_id = clean_inline(item.get("block_id") or item.get("bilingual_block_id"))
            block = f" `{block_id}`" if block_id else ""
            confusion = CONFUSION_LABELS.get(clean_inline(item.get("confusion_type")), clean_inline(item.get("confusion_type")) or "未指定")
            lines.append(f"- {short_concept(item)}{block}：{status_text(status)}，问题类型 {confusion}")
    else:
        lines.append("- （这次反馈没有需要解释的条目）")
    lines.append("")
    lines.append("### 建议阅读路线")
    lines.append("")
    if news_mode:
        lines.extend(news_route_lines())
    else:
        lines.append("1. 先用 TDSE 作为已知锚点：它是完整实时演化目标。")
        lines.append("2. 接着读 TDCSE 和 2-RDM：理解为什么二体收缩在本文条件下足够。")
        lines.append("3. 再读 ansatz 与 two-electron unitary：理解 CETE 怎样把理论条件变成线路。")
        lines.append("4. 最后读 H2 示例、1-RDM/energy 图和 Pauli-sum tomography：看实验如何验证 CETE。")
    lines.append("")

    lines.append("## 逐条解析")
    lines.append("")
    for index, item in enumerate(items, start=1):
        concept = clean_inline(item.get("concept") or item.get("selected_text") or "未命名反馈")
        status = clean_inline(item.get("status")) or "unrated"
        kind = clean_inline(item.get("annotation_kind")) or "unknown"
        block_id = clean_inline(item.get("block_id") or item.get("bilingual_block_id"))
        confusion = clean_inline(item.get("confusion_type"))
        source = source_context_for_item(item, source_by_id)
        glossary_entry = find_glossary_entry(glossary, concept)
        profile_name, profile_entry = find_profile_entry(profile, concept)

        lines.append(f"### {index:02d}. {short_concept(item, 120)}")
        lines.append("")
        lines.append(bullet("反馈状态", status_text(status), 120))
        lines.append(bullet("profile 状态", profile_status(profile_entry), 160))
        if profile_name and profile_name != concept:
            lines.append(bullet("profile 匹配项", profile_name, 180))
        lines.append(bullet("标注类型", kind, 100))
        lines.append(bullet("问题类型", CONFUSION_LABELS.get(confusion, confusion or "未指定"), 120))
        if block_id and not source and not news_mode:
            lines.append(bullet("source warning", f"{block_id} 未在 source_map.json 中找到；以下解释使用 feedback 文本。", 220))
        lines.append("")
        lines.extend(source_lines(item, source))
        lines.append("")
        if news_mode:
            lines.extend(build_news_direct_explanation(item, profile_entry))
        else:
            lines.extend(build_direct_explanation(item, source, glossary_entry, profile_entry))
        lines.append("")
        lines.append("**你可以继续追问**")
        if news_mode:
            lines.extend(news_followup_lines(item))
        else:
            lines.append(f"- “请围绕 `{block_id or short_concept(item, 40)}` 再展开公式/物理意义。”")
            lines.append(f"- “把 `{short_concept(item, 40)}` 和 CETE 主线重新串起来。”")
        lines.append("")

    lines.append("## 本次迭代后的学习重点")
    lines.append("")
    if news_mode:
        lines.extend(news_learning_focus_lines(items))
    else:
        lines.append("- CETE 主线：TDSE -> TDCSE -> 双电子酉 ansatz -> 迭代残差/梯度 -> H2 硬件验证。")
        lines.append("- 数学重点：S005/S006/S009/S011，尤其是二体收缩为什么可推出完整 TDSE。")
        lines.append("- 算法重点：S016，残差如何决定下一段 two-electron unitary。")
        lines.append("- 实验重点：S017/S018/F001/F002，H2 如何约化、测什么、图如何支持结论。")
    lines.append("")
    lines.append("## 后续可直接问 Codex 的问题")
    lines.append("")
    if news_mode:
        lines.append("- 请按 source claim -> mechanism -> evidence -> implication 解析本次所有 unknown 条目。")
        lines.append("- 请把 AI for Quantum 与 Quantum machine learning 两类新闻按研究路径做对比。")
        lines.append("- 请解释本次日报里 QEC、neutral-atom、quantum walk 三条量子方向各自卡在什么物理/数学边界。")
        lines.append("- 请根据我的画像，把这些新闻整理成下一周需要复习的知识队列。")
    else:
        lines.append("- 请按公式推导详细解释 S009：为什么 TDCSE 残差加权后等价于 TDSE 方差？")
        lines.append("- 请用一个二能级 H2 玩具模型解释 S018 的单量子比特约化。")
        lines.append("- 请把 CETE 与普通 Trotter/sequential short-time propagators 做逐项对比。")
        lines.append("- 请只围绕图 1 和图 2 解释本文的实验证据链。")
    lines.append("")
    return "\n".join(lines)


def h(value: Any) -> str:
    return html_lib.escape(clean_inline(value))


def js_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def is_news_feedback(feedback: dict[str, Any], feedback_path: Path) -> bool:
    source_kind = clean_inline(feedback.get("source_kind"))
    return (
        source_kind == "news_briefing"
        or bool(clean_inline(feedback.get("briefing_title")))
        or feedback_path.name.startswith("news_feedback")
    )


def report_feedback_item_meta(index: int, item: dict[str, Any]) -> dict[str, Any]:
    concept = clean_inline(item.get("concept") or item.get("selected_text") or f"feedback item {index}")
    block_id = clean_inline(item.get("block_id") or item.get("bilingual_block_id") or f"item-{index:02d}")
    return {
        "index": index,
        "anchor": f"item-{index:02d}",
        "concept": concept,
        "status": clean_inline(item.get("status")) or "unrated",
        "category": clean_inline(item.get("category") or item.get("confusion_type")),
        "source_title": clean_inline(item.get("source_title")),
        "source_url": clean_inline(item.get("source_url")),
        "source_excerpt": clean_inline(item.get("source_excerpt")),
        "selected_text": clean_inline(item.get("selected_text") or concept),
        "selected_language": clean_inline(item.get("selected_language") or "report_item"),
        "original_context": clean_inline(item.get("original_context") or item.get("source_excerpt")),
        "translation_context": clean_inline(item.get("translation_context")),
        "block_id": block_id,
        "annotation_kind": clean_inline(item.get("annotation_kind") or "report_item"),
        "confusion_type": clean_inline(item.get("confusion_type")),
        "explanation_style": clean_inline(item.get("explanation_style")),
        "note": clean_inline(item.get("note")),
        "user_question": clean_inline(item.get("user_question") or item.get("question")),
    }


def report_feedback_payload(
    feedback_path: Path,
    feedback: dict[str, Any],
    reader_dir: Path,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    news = is_news_feedback(feedback, feedback_path)
    title = clean_inline(
        feedback.get("briefing_title")
        or feedback.get("paper_title")
        or feedback.get("title")
        or reader_dir.name.replace("_reader", "")
    )
    return {
        "kind": "news" if news else "reader",
        "export_filename": "news_feedback2.json" if news else "reader_feedback2.json",
        "source_kind": "news_briefing" if news else clean_inline(feedback.get("source_kind") or "reader_feedback"),
        "title": title,
        "paper_title": clean_inline(feedback.get("paper_title") or title),
        "briefing_title": clean_inline(feedback.get("briefing_title") or title),
        "date_range": clean_inline(feedback.get("date_range")),
        "reader_path": clean_inline(feedback.get("reader_path") or str(reader_dir)),
        "briefing_path": clean_inline(feedback.get("briefing_path") or feedback.get("reader_path") or str(reader_dir)),
        "feedback_path": str(feedback_path),
        "report_source": "read-feedback-skill",
        "items": [report_feedback_item_meta(index, item) for index, item in enumerate(items, start=1)],
    }


def interactive_feedback_css() -> str:
    return """
.report-feedback-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}
.mark-report-btn, .feedback-action-btn {
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
  color: #1d4ed8;
  padding: 7px 10px;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.mark-report-btn:hover, .feedback-action-btn:hover {
  background: #dbeafe;
}
.feedback-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.feedback-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #d1d5db;
  border-radius: 999px;
  background: #fff;
  padding: 3px 8px;
  color: #475467;
  font-size: 12px;
}
.feedback-pill button {
  border: 0;
  background: transparent;
  color: #b42318;
  cursor: pointer;
  font-size: 12px;
  padding: 0;
}
.feedback-dock {
  position: fixed;
  right: 18px;
  bottom: 18px;
  z-index: 20;
  width: min(420px, calc(100vw - 36px));
  max-height: calc(100vh - 36px);
  display: grid;
  grid-template-rows: auto auto 1fr;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  background: #ffffff;
  box-shadow: 0 18px 44px rgba(15, 23, 42, .18);
  overflow: hidden;
}
.feedback-dock.collapsed {
  grid-template-rows: auto;
}
.feedback-dock.collapsed .feedback-body,
.feedback-dock.collapsed .saved-feedback {
  display: none;
}
.feedback-dock header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  background: #0f172a;
  color: #fff;
}
.feedback-dock header strong {
  font-size: 14px;
}
.feedback-dock header button {
  border: 1px solid rgba(255,255,255,.35);
  border-radius: 6px;
  background: transparent;
  color: #fff;
  cursor: pointer;
  padding: 3px 7px;
}
.feedback-body {
  padding: 12px;
  overflow: auto;
}
.feedback-body label {
  display: block;
  margin: 8px 0 4px;
  color: #475467;
  font-size: 12px;
}
.feedback-body input,
.feedback-body select,
.feedback-body textarea {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 8px;
  color: #111827;
  font: inherit;
  font-size: 13px;
}
.feedback-body textarea {
  min-height: 70px;
  resize: vertical;
}
.feedback-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.feedback-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.saved-feedback {
  border-top: 1px solid #e5e7eb;
  padding: 10px 12px;
  max-height: 180px;
  overflow: auto;
  background: #f8fafc;
}
.saved-feedback h3 {
  margin: 0 0 6px;
  font-size: 13px;
}
.saved-feedback ul {
  margin: 0;
  padding-left: 18px;
}
.saved-feedback li {
  margin: 4px 0;
  font-size: 12px;
}
.saved-feedback button {
  margin-left: 6px;
  border: 0;
  background: transparent;
  color: #b42318;
  cursor: pointer;
}
@media print {
  .feedback-dock, .report-feedback-actions { display: none; }
}
"""


def interactive_feedback_shell(
    feedback_path: Path,
    feedback: dict[str, Any],
    reader_dir: Path,
    items: list[dict[str, Any]],
) -> str:
    payload = report_feedback_payload(feedback_path, feedback, reader_dir, items)
    payload_json = js_json(payload)
    title = h(payload["export_filename"])
    template = r"""
<aside class="feedback-dock collapsed" id="report-feedback-dock" aria-label="Second-pass feedback export">
  <header>
    <strong>Second-pass feedback · __TITLE__</strong>
    <button type="button" id="feedback-toggle">Open</button>
  </header>
  <div class="feedback-body">
    <div class="feedback-toolbar">
      <button class="feedback-action-btn" type="button" id="annotate-selection">Annotate selection</button>
      <button class="feedback-action-btn" type="button" id="download-feedback2">Download JSON</button>
      <button class="feedback-action-btn" type="button" id="copy-feedback2">Copy for Codex</button>
    </div>
    <label for="feedback-concept">Concept / selected text</label>
    <input id="feedback-concept" type="text" placeholder="Click Mark this item or select report text">
    <div class="feedback-row">
      <div>
        <label for="feedback-status">Status</label>
        <select id="feedback-status">
          <option value="unknown">unknown</option>
          <option value="learning">learning</option>
          <option value="known">known</option>
          <option value="mastered">mastered</option>
          <option value="unrated">unrated</option>
        </select>
      </div>
      <div>
        <label for="feedback-confusion">Question type</label>
        <select id="feedback-confusion">
          <option value="term_definition">term definition</option>
          <option value="paper_usage">paper/news usage</option>
          <option value="math_step">math step</option>
          <option value="algorithm_step">algorithm step</option>
          <option value="assumption">assumption</option>
          <option value="evidence">evidence</option>
          <option value="relation">relation</option>
          <option value="physical_intuition">physical intuition</option>
          <option value="other">other</option>
        </select>
      </div>
    </div>
    <label for="feedback-style">Preferred explanation style</label>
    <select id="feedback-style">
      <option value="paper_context">paper/news context</option>
      <option value="math_derivation">math derivation</option>
      <option value="physical_intuition">physical intuition</option>
      <option value="algorithm_trace">algorithm trace</option>
      <option value="examples">examples</option>
    </select>
    <label for="feedback-question">Exact question</label>
    <textarea id="feedback-question" placeholder="Write the exact thing still unclear after reading this report"></textarea>
    <label for="feedback-note">Note</label>
    <textarea id="feedback-note" placeholder="Optional: what you understood, what still feels vague"></textarea>
    <div class="feedback-toolbar">
      <button class="feedback-action-btn" type="button" id="save-feedback-mark">Save mark</button>
      <button class="feedback-action-btn" type="button" id="clear-feedback-form">Clear</button>
    </div>
    <p class="source-note" id="feedback-active-source">No active report item.</p>
  </div>
  <div class="saved-feedback">
    <h3>Saved marks</h3>
    <ul id="saved-feedback-list"></ul>
  </div>
</aside>
<script>
(function(){
  const REPORT_FEEDBACK = __PAYLOAD__;
  const storageKey = 'read-feedback-skill:v2:' + REPORT_FEEDBACK.feedback_path + ':' + REPORT_FEEDBACK.export_filename;
  const byAnchor = new Map((REPORT_FEEDBACK.items || []).map(item => [item.anchor, item]));
  const byIndex = new Map((REPORT_FEEDBACK.items || []).map(item => [String(item.index), item]));
  let marks = [];
  let activeBase = null;

  const dock = document.getElementById('report-feedback-dock');
  const toggle = document.getElementById('feedback-toggle');
  const conceptEl = document.getElementById('feedback-concept');
  const statusEl = document.getElementById('feedback-status');
  const confusionEl = document.getElementById('feedback-confusion');
  const styleEl = document.getElementById('feedback-style');
  const questionEl = document.getElementById('feedback-question');
  const noteEl = document.getElementById('feedback-note');
  const activeSourceEl = document.getElementById('feedback-active-source');
  const savedList = document.getElementById('saved-feedback-list');

  function loadMarks(){
    try {
      const raw = localStorage.getItem(storageKey);
      marks = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(marks)) marks = [];
    } catch (error) {
      marks = [];
    }
  }
  function persistMarks(){
    localStorage.setItem(storageKey, JSON.stringify(marks));
  }
  function openDock(){
    dock.classList.remove('collapsed');
    toggle.textContent = 'Close';
  }
  function toggleDock(){
    dock.classList.toggle('collapsed');
    toggle.textContent = dock.classList.contains('collapsed') ? 'Open' : 'Close';
  }
  function shortText(text, limit){
    text = String(text || '').trim();
    return text.length > limit ? text.slice(0, limit - 1) + '…' : text;
  }
  function baseFromItem(item){
    return {
      concept: item.concept || '',
      category: item.category || '',
      source_title: item.source_title || '',
      source_url: item.source_url || '',
      source_excerpt: item.source_excerpt || '',
      selected_text: item.selected_text || item.concept || '',
      selected_language: item.selected_language || 'report_item',
      original_context: item.original_context || item.source_excerpt || '',
      translation_context: item.translation_context || '',
      block_id: item.block_id || item.anchor || '',
      annotation_kind: 'report_item',
      source_kind: REPORT_FEEDBACK.source_kind || '',
      report_item_index: item.index,
      report_anchor: item.anchor
    };
  }
  function setActive(base){
    activeBase = base || {};
    conceptEl.value = activeBase.concept || activeBase.selected_text || '';
    if (activeBase.user_question) questionEl.value = activeBase.user_question;
    activeSourceEl.textContent = activeBase.report_anchor
      ? ('Active: ' + activeBase.report_anchor + ' · ' + shortText(activeBase.source_title || activeBase.category || activeBase.block_id, 90))
      : 'Active: freeform report selection';
    openDock();
  }
  function selectionBase(){
    const selection = window.getSelection();
    const text = selection ? String(selection.toString()).trim() : '';
    if (!text) {
      alert('请先选中报告中的一段文本。');
      return null;
    }
    let node = selection.anchorNode;
    if (node && node.nodeType === Node.TEXT_NODE) node = node.parentElement;
    const card = node && node.closest ? node.closest('.item-card') : null;
    const item = card ? byAnchor.get(card.id) : null;
    const base = item ? baseFromItem(item) : {};
    base.concept = shortText(text, 140);
    base.selected_text = text;
    base.selected_language = 'report_selection';
    base.original_context = text;
    base.annotation_kind = 'report_freeform';
    base.report_anchor = item ? item.anchor : '';
    return base;
  }
  function currentMark(){
    const concept = conceptEl.value.trim();
    if (!concept) {
      alert('请先选择一个概念或选中文本。');
      return null;
    }
    const question = questionEl.value.trim();
    const status = statusEl.value;
    return Object.assign({}, activeBase || {}, {
      feedback_id: 'feedback2::' + Date.now().toString(36) + '::' + Math.random().toString(36).slice(2, 8),
      concept,
      status,
      user_question: question,
      note: noteEl.value.trim(),
      confusion_type: confusionEl.value,
      question_type: confusionEl.value,
      explanation_style: styleEl.value,
      needs_explanation: status === 'unknown' || status === 'learning' || Boolean(question),
      action: 'read_feedback_report_mark',
      source_kind: REPORT_FEEDBACK.source_kind || activeBase?.source_kind || '',
      created_at: new Date().toISOString()
    });
  }
  function payload(){
    const base = {
      exported_at: new Date().toISOString(),
      generated_from: 'read-feedback-skill interactive explanation HTML',
      source_feedback_path: REPORT_FEEDBACK.feedback_path,
      report_source: REPORT_FEEDBACK.report_source,
      items: marks
    };
    if (REPORT_FEEDBACK.kind === 'news') {
      return Object.assign({
        news_feedback_version: 2,
        briefing_title: REPORT_FEEDBACK.briefing_title || REPORT_FEEDBACK.title,
        date_range: REPORT_FEEDBACK.date_range || '',
        briefing_path: REPORT_FEEDBACK.briefing_path || REPORT_FEEDBACK.reader_path || REPORT_FEEDBACK.feedback_path
      }, base);
    }
    return Object.assign({
      reader_feedback_version: 2,
      paper_title: REPORT_FEEDBACK.paper_title || REPORT_FEEDBACK.title,
      reader_path: REPORT_FEEDBACK.reader_path || REPORT_FEEDBACK.feedback_path,
      source_kind: REPORT_FEEDBACK.source_kind || 'reader_feedback'
    }, base);
  }
  function render(){
    persistMarks();
    savedList.innerHTML = '';
    const grouped = new Map();
    for (const mark of marks) {
      const anchor = mark.report_anchor || '';
      if (!grouped.has(anchor)) grouped.set(anchor, []);
      grouped.get(anchor).push(mark);
    }
    document.querySelectorAll('[data-feedback-anchor]').forEach(strip => {
      const anchor = strip.getAttribute('data-feedback-anchor') || '';
      const local = grouped.get(anchor) || [];
      strip.innerHTML = local.map(mark => '<span class="feedback-pill">' + shortText(mark.concept, 36) + ' · ' + mark.status + '</span>').join('');
    });
    if (!marks.length) {
      savedList.innerHTML = '<li>No saved marks yet.</li>';
      return;
    }
    marks.forEach((mark, index) => {
      const li = document.createElement('li');
      li.textContent = shortText(mark.concept, 52) + ' · ' + mark.status;
      const del = document.createElement('button');
      del.type = 'button';
      del.textContent = 'Delete';
      del.addEventListener('click', () => {
        marks.splice(index, 1);
        render();
      });
      li.appendChild(del);
      savedList.appendChild(li);
    });
  }
  function download(){
    const data = JSON.stringify(payload(), null, 2);
    const blob = new Blob([data], {type: 'application/json;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = REPORT_FEEDBACK.export_filename || 'feedback2.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }
  async function copy(){
    const data = JSON.stringify(payload(), null, 2);
    await navigator.clipboard.writeText(data);
    alert('已复制 feedback2 JSON，可直接粘给 Codex。');
  }
  document.querySelectorAll('[data-mark-report-item]').forEach(button => {
    button.addEventListener('click', () => {
      const item = byIndex.get(button.getAttribute('data-mark-report-item'));
      if (item) setActive(baseFromItem(item));
    });
  });
  document.getElementById('annotate-selection').addEventListener('click', () => {
    const base = selectionBase();
    if (base) setActive(base);
  });
  document.getElementById('save-feedback-mark').addEventListener('click', () => {
    const mark = currentMark();
    if (!mark) return;
    marks.push(mark);
    questionEl.value = '';
    noteEl.value = '';
    render();
  });
  document.getElementById('clear-feedback-form').addEventListener('click', () => {
    activeBase = null;
    conceptEl.value = '';
    questionEl.value = '';
    noteEl.value = '';
    activeSourceEl.textContent = 'No active report item.';
  });
  document.getElementById('download-feedback2').addEventListener('click', download);
  document.getElementById('copy-feedback2').addEventListener('click', copy);
  toggle.addEventListener('click', toggleDock);
  loadMarks();
  render();
})();
</script>
"""
    return template.replace("__TITLE__", title).replace("__PAYLOAD__", payload_json)


def status_class(status: str) -> str:
    value = clean_inline(status) or "unrated"
    if value in {"known", "mastered"}:
        return "good"
    if value == "learning":
        return "warn"
    if value == "unknown":
        return "bad"
    return "neutral"


def html_status_badge(status: str) -> str:
    value = clean_inline(status) or "unrated"
    return f'<span class="badge {status_class(value)}">{h(status_text(value))}</span>'


def html_meta(label: str, value: Any) -> str:
    text = h(value) or "无"
    return f"<div><dt>{h(label)}</dt><dd>{text}</dd></div>"


def compact_text(value: Any, limit: int = 280) -> tuple[str, str, bool]:
    text = clean_inline(value)
    if len(text) <= limit:
        return text, text, False
    return text[: limit - 1].rstrip() + "...", text, True


def html_text_panel(title: str, value: Any, css_class: str = "", limit: int = 280, collapsible: bool = True) -> str:
    text = clean_inline(value)
    if not text:
        return ""
    preview, full, truncated = compact_text(text, limit)
    details = ""
    if collapsible and truncated:
        details = (
            '<details class="context-details">'
            "<summary>展开完整上下文</summary>"
            f"<p>{inline_markdown_to_html(full)}</p>"
            "</details>"
        )
    return (
        f'<div class="text-panel {css_class}">'
        f"<div class=\"panel-label\">{h(title)}</div>"
        f"<p>{inline_markdown_to_html(preview)}</p>"
        f"{details}"
        "</div>"
    )


def source_anchor_summary(item: dict[str, Any], source: dict[str, Any], source_label: str) -> str:
    parts = [source_label]
    category = clean_inline(item.get("category"))
    source_title = clean_inline(item.get("source_title"))
    if category:
        parts.append(category)
    if source_title:
        parts.append(clip(source_title, 90))
    return " · ".join(part for part in parts if part)


def formula_for_item(concept: str, block_id: str) -> list[tuple[str, str, str]]:
    key = norm_key(concept)
    formulas: list[tuple[str, str, str]] = []
    if block_id == "S009" or "tdcse" in key:
        formulas.append(
            (
                "TDCSE 的收缩条件",
                r"\[\langle \Psi(t)|\hat B^\dagger(\partial_t+i\hat H)|\Psi(t)\rangle=0\quad(\hat B:\ \text{two-electron operator})\]",
                "读法：不是直接求完整波函数误差，而是要求所有二体方向看到的 TDSE 残差都为零。",
            )
        )
    if "tdse" in key:
        formulas.append(
            (
                "TDSE 基准方程",
                r"\[i\frac{\partial}{\partial t}|\Psi(t)\rangle=\hat H|\Psi(t)\rangle\]",
                "读法：哈密顿量给出演化方向，后面的 contracted/ansatz 都是在压缩或实现这个方向。",
            )
        )
    if block_id in {"S005", "S006"} or "two-particle reduced density matrix" in key or "2-rdm" in key:
        formulas.append(
            (
                "二体哈密顿量与 2-RDM",
                r"\[E=\langle\hat H\rangle=\sum_{pq}h^p_q\gamma^q_p+\frac{1}{4}\sum_{pqrs}v^{pq}_{rs}\,{}^2D^{rs}_{pq}\]",
                "读法：如果哈密顿量最多含二体项，能量和收缩动力学主要落在 1-RDM/2-RDM 这些约化对象上。",
            )
        )
    if block_id == "S011" or (
        block_id not in {"F001", "F002"} and ("two-electron unitary" in key or "ansatz" in key or "cete" in key)
    ):
        formulas.append(
            (
                "反厄米生成元到酉操作",
                r"\[\hat U(\epsilon)=e^{\epsilon\hat A},\qquad \hat A^\dagger=-\hat A\]",
                "读法：反厄米性保证指数化后是酉的；CETE 选择二体 \(\hat A\) 来更新线路。",
            )
        )
    if block_id == "S016" or (block_id not in {"F001", "F002"} and "cete" in key):
        formulas.append(
            (
                "残差驱动的更新方向",
                r"\[\frac{d}{d\epsilon}\left|\langle\Phi|e^{\epsilon\hat A}|\Psi\rangle\right|^2_{\epsilon=0}\quad\Rightarrow\quad \text{choose a two-electron }\hat A\text{ that most reduces the residual}\]",
                "读法：CETE 不是随便加门，而是在二体生成元空间里找最能修正当前残差的方向。",
            )
        )
    if block_id == "S018" or "slater determinant" in key:
        formulas.append(
            (
                "二维子空间到单量子比特",
                r"\[|\mathrm{HF}\rangle\mapsto |0\rangle,\qquad |\mathrm{double}\rangle\mapsto |1\rangle,\qquad \hat H\mapsto \hat H_{\mathrm{eff}}^{(2\times2)}\]",
                "读法：不是说 H2 天然只有一个量子比特，而是这个特定初态/耦合结构允许把动力学投影到二维子空间。",
            )
        )
    if "one-particle reduced density matrix" in key or "1-rdm" in key or block_id == "F001":
        formulas.append(
            (
                "1-RDM 元素",
                r"\[\gamma^p_q=\langle\Psi|a_p^\dagger a_q|\Psi\rangle\]",
                "读法：它看单粒子占据/相干，是图 1 用来检查电子占据动力学的量。",
            )
        )
    if "two-particle reduced density matrix" in key or "2-rdm" in key:
        formulas.append(
            (
                "2-RDM 元素",
                r"\[{}^2D^{pq}_{rs}=\langle\Psi|a_p^\dagger a_q^\dagger a_s a_r|\Psi\rangle\]",
                "读法：它保留二体关联信息，因此和二体哈密顿量、TDCSE、CETE 的二体生成元天然相连。",
            )
        )
    if "pauli-sum tomography" in key or block_id in {"F001", "F002"}:
        formulas.append(
            (
                "Pauli-sum 测量",
                r"\[\langle O\rangle=\sum_j c_j\langle P_j\rangle\]",
                "读法：把可观测量拆成 Pauli 字符串分别测量，最后按系数合成图中的 1-RDM 或能量点。",
            )
        )
    if "sequential short-time propagators" in key:
        formulas.append(
            (
                "短时传播子乘积",
                r"\[|\Psi(T)\rangle\approx \prod_{n=1}^{N}e^{-i\hat H\Delta t}|\Psi(0)\rangle,\qquad T=N\Delta t\]",
                "读法：顺序短时传播把时间切成很多步；线路深度和每步误差会随步数累积。",
            )
        )
    return formulas


def html_formula_panel(title: str, formula: str, note: str = "") -> str:
    note_html = f'<p class="formula-note">{inline_markdown_to_html(note)}</p>' if note else ""
    return (
        '<div class="formula-panel">'
        f'<div class="formula-title">{h(title)}</div>'
        f'<div class="math-display">{html_lib.escape(formula)}</div>'
        f"{note_html}"
        "</div>"
    )


def profile_entry_raw_status(profile_entry: dict[str, Any] | None) -> str:
    if not profile_entry:
        return "unrated"
    return clean_inline(profile_entry.get("status")) or "unrated"


def known_profile_anchors(profile: dict[str, Any] | None, limit: int = 4) -> list[str]:
    if not profile:
        return []
    anchors: list[str] = []
    for entry in (profile.get("concepts", {}) or {}).values():
        if not isinstance(entry, dict):
            continue
        if clean_inline(entry.get("status")) not in {"known", "mastered"}:
            continue
        label = clean_inline(entry.get("label") or entry.get("concept_id"))
        if label:
            anchors.append(label)
        if len(anchors) >= limit:
            break
    return anchors


def profile_facet_hint(profile_entry: dict[str, Any] | None, confusion: str) -> str:
    if not profile_entry:
        return "画像里还没有稳定匹配项，所以本条按反馈状态和论文上下文展开。"
    facet_status = profile_entry.get("facet_status", {}) or {}
    facet_labels = {
        "definition": "基础定义",
        "paper_usage": "论文用法",
        "math_derivation": "公式推导",
        "algorithm_step": "算法步骤",
        "assumption": "隐含假设",
        "evidence_interpretation": "证据解读",
        "relation": "概念关系",
        "english_term": "英文术语",
        "physical_intuition": "物理直觉",
    }
    confusion_to_facet = {
        "term_definition": "definition",
        "paper_usage": "paper_usage",
        "math_step": "math_derivation",
        "algorithm_step": "algorithm_step",
        "assumption": "assumption",
        "evidence": "evidence_interpretation",
        "relation": "relation",
    }
    focused = confusion_to_facet.get(confusion)
    if focused and clean_inline(facet_status.get(focused)) in {"unknown", "learning", "unrated"}:
        return f"画像提示本条最该补的是「{facet_labels.get(focused, focused)}」，因此下面会先讲物理意义，再接回本文用法。"
    weak = [
        facet_labels.get(name, name)
        for name, status in facet_status.items()
        if clean_inline(status) in {"unknown", "learning"}
    ]
    if weak:
        return f"画像里仍不稳的面向：{'、'.join(weak[:3])}。本条会优先补这些环节。"
    unrated = [
        facet_labels.get(name, name)
        for name, status in facet_status.items()
        if clean_inline(status) == "unrated"
    ]
    if unrated:
        return f"画像里这些面向还未判定：{'、'.join(unrated[:3])}。本条按阅读时最容易断链的位置补充。"
    return "画像显示这项已较稳定；这里保留简短定位，主要帮你把它放回论文链条。"


def physical_meaning_html(
    item: dict[str, Any],
    source: dict[str, Any],
    glossary_entry: dict[str, Any] | None,
    profile_entry: dict[str, Any] | None,
    profile: dict[str, Any] | None,
) -> str:
    concept = clean_inline(item.get("concept") or item.get("selected_text") or "未命名反馈")
    block_id = clean_inline(item.get("block_id") or item.get("bilingual_block_id"))
    kind = clean_inline(item.get("annotation_kind"))
    feedback_status = clean_inline(item.get("status")) or "unrated"
    profile_state = profile_entry_raw_status(profile_entry)
    confusion = clean_inline(item.get("confusion_type"))
    cexp = concept_explanation(concept)
    bexp = block_explanation(block_id)
    prefer_block = bool(bexp) and (kind == "freeform" or block_id.startswith(("S", "F", "C")))
    primary = bexp if prefer_block else cexp
    secondary = cexp if prefer_block else bexp
    deep = feedback_status in {"unknown", "learning", "unrated"} or profile_state in {"unknown", "learning", "unrated"}
    panel_class = "deep" if deep else "anchor"
    title = "物理意义与本文角色" if deep else "已知锚点的本文定位"

    core = ""
    paper = ""
    watch = ""
    if primary:
        core = primary.get("core", "")
        paper = primary.get("paper", "")
        watch = primary.get("watch", "")
    if secondary:
        core = core or secondary.get("core", "")
        paper = paper or secondary.get("paper", "")
        watch = watch or secondary.get("watch", "")
    source_hint = clean_inline(item.get("source_excerpt") or item.get("selected_text") or source.get("translation") or source.get("original_text"))
    if not core:
        core = f"这条标注不是稳定术语时，先把它当作论文局部论证的一个节点：{clip(source_hint, 180) if source_hint else '当前缺少足够上下文，需要回到原标注位置确认。'}"
    if not paper:
        paper = "把它放回 CETE 主线：TDSE 给出目标动力学，TDCSE/2-RDM 给出二体层面的条件，双电子酉 ansatz 把条件变成可执行线路，H2 图表再验证效果。"
    if not watch:
        watch = "继续读时不要只记定义，要问它在“目标方程 -> 二体收缩 -> 线路更新 -> 实验证据”哪一环承担作用。"

    anchors = known_profile_anchors(profile)
    anchor_text = f"你的已知锚点：{h('、'.join(anchors))}。建议从这些锚点往当前概念连接。" if anchors else "暂时没有可用的 known/mastered 锚点，本条按论文主线搭桥。"
    profile_hint = profile_facet_hint(profile_entry, confusion)
    glossary_html = ""
    if glossary_entry:
        term_cn = clean_inline(glossary_entry.get("translation"))
        note = clean_inline(glossary_entry.get("note"))
        if term_cn or note:
            glossary_html = f"<li><strong>术语补充：</strong>{h(term_cn or '无译名')}；{h(note or '无备注')}</li>"

    context_html = ""
    if source_hint:
        context_html = f'<p class="context-link"><strong>短上下文锚点：</strong>{inline_markdown_to_html(clip(source_hint, 180))}</p>'

    return (
        f'<section class="explain-panel physical-panel {panel_class}">'
        f"<h4>{h(title)}</h4>"
        f'<p class="depth-note">{h(profile_hint)}</p>'
        "<ul>"
        f"<li><strong>物理直觉：</strong>{inline_markdown_to_html(core)}</li>"
        f"<li><strong>本文角色：</strong>{inline_markdown_to_html(paper)}</li>"
        f"<li><strong>按你的画像读：</strong>{anchor_text}</li>"
        f"<li><strong>阅读抓手：</strong>{inline_markdown_to_html(watch)}</li>"
        f"{glossary_html}"
        "</ul>"
        f"{context_html}"
        "</section>"
    )


def math_physics_derivation_spec(item: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    concept = clean_inline(item.get("concept") or item.get("selected_text") or "未命名反馈")
    block_id = clean_inline(item.get("block_id") or item.get("bilingual_block_id"))
    key = norm_key(concept)
    source_hint = clean_inline(item.get("source_excerpt") or item.get("selected_text") or source.get("translation") or source.get("original_text"))

    if block_id == "S022":
        return {
            "premise": "这条是致谢/声明，不是技术论证节点。",
            "steps": [
                "把它从 CETE 的理论链条中剥离出来，只保留为资金、硬件服务或立场声明信息。",
                "阅读技术路线时不要把它当作算法假设、实验数据或物理结论。",
            ],
            "conclusion": "本条无需公式推导；应归档为非技术上下文。",
        }
    if block_id == "S009" or "tdcse" in key:
        return {
            "premise": "从 TDSE 残差出发：如果当前态没有完全满足 TDSE，就存在残差向量。",
            "steps": [
                r"定义残差 \(R=(\partial_t+i\hat H)|\Psi(t)\rangle\)。TDSE 成立等价于 \(R=0\)。",
                r"TDCSE 不直接检查整个 \(R\)，而是让所有二体算符方向 \(\hat B\) 都看不到残差，即 \(\langle\Psi|\hat B^\dagger R\rangle=0\)。",
                r"当 \(\hat H\) 最多含二体相互作用时，这些二体收缩方向覆盖了本文需要的动力学信息；对收缩残差加权求和可还原残差范数/方差型正定量。",
                "正定量为零只能说明残差本身为零，所以满足全部 TDCSE 条件就推出 TDSE；TDSE 成立时任意收缩自然也为零。",
            ],
            "conclusion": "TDCSE 在本文不是泛泛的近似，而是在二体哈密顿量条件下把完整 TDSE 改写成可被二体对象检测的等价条件。",
        }
    if "tdse" in key:
        return {
            "premise": "把 TDSE 当作已知锚点：它给出量子态随时间变化的微分方程。",
            "steps": [
                r"方程 \(i\partial_t|\Psi\rangle=\hat H|\Psi\rangle\) 等价于 \(\partial_t|\Psi\rangle=-i\hat H|\Psi\rangle\)。",
                r"若短时间内 \(\hat H\) 近似固定，则解为 \(|\Psi(t+\Delta t)\rangle\approx e^{-i\hat H\Delta t}|\Psi(t)\rangle\)。",
                "因此任何时间演化算法都要回答同一个问题：怎样在硬件上实现或近似这个指数酉演化。",
            ],
            "conclusion": "本文的 TDCSE、CETE ansatz、实验图表都可以从这个 TDSE 锚点向下推出来。",
        }
    if block_id in {"S005", "S006"} or "2-rdm" in key or "two-particle reduced density matrix" in key:
        return {
            "premise": "电子结构哈密顿量通常只含一体项和二体库仑相互作用。",
            "steps": [
                r"二次量子化中，一体项形如 \(a_p^\dagger a_q\)，二体项形如 \(a_p^\dagger a_q^\dagger a_s a_r\)。",
                r"对态取期望后，一体项由 1-RDM \(\gamma\) 决定，二体项由 2-RDM \({}^2D\) 决定。",
                r"所以当 \(\hat H\) 没有三体、四体项时，能量和二体收缩条件不需要完整波函数的全部振幅，而可以通过约化密度矩阵表达。",
            ],
            "conclusion": "这就是 CETE 能把多体演化问题转到二体相关结构上的数学原因。",
        }
    if block_id in {"S011", "S016"} or (
        block_id not in {"F001", "F002"} and ("cete" in key or "ansatz" in key or "two-electron unitary" in key)
    ):
        return {
            "premise": "量子时间演化必须保持态的范数，因此线路更新应当是酉操作。",
            "steps": [
                r"若生成元 \(\hat A^\dagger=-\hat A\)，则 \(e^{\epsilon\hat A}\) 是酉的，因为 \((e^{\epsilon\hat A})^\dagger e^{\epsilon\hat A}=I\)。",
                "TDCSE 告诉我们在二体哈密顿量条件下，应优先检查/修正二体算符方向的残差。",
                r"CETE 因此把候选更新限制为双电子反厄米生成元，并用残差或保真度梯度选择下一步 \(\hat A\)。",
                "每一步不是任意加参数门，而是把当前态沿最有用的二体相关方向旋转一点。",
            ],
            "conclusion": "CETE ansatz 的物理来源是“二体残差方向 + 酉范数保持”，不是单纯的经验线路模板。",
        }
    if block_id in {"S017", "S018"} or "slater determinant" in key:
        return {
            "premise": "H2/STO-3G 的这个示例被选择成一个很小但可检验的动力学问题。",
            "steps": [
                "Slater 行列式可以看成自旋轨道占据模式；HF 态和双激发态对应两个不同占据 bitstring。",
                "在本文设置下，主要动力学被限制在这两个态张成的二维子空间里。",
                r"把这两个基态分别映射为单量子比特的 \(|0\rangle\)、\(|1\rangle\)，原来的哈密顿量和 RDM 测量也随之投影成单比特可测对象。",
            ],
            "conclusion": "实验里的单量子比特不是偷换物理体系，而是利用特定 H2 动力学的有效二维约化。",
        }
    if block_id == "F001" or "1-rdm" in key or "one-particle reduced density matrix" in key:
        return {
            "premise": "图 1 要验证的是电子占据动力学，而不是完整波函数每个振幅。",
            "steps": [
                r"对角 1-RDM 元素 \(\gamma^p_p=\langle a_p^\dagger a_p\rangle\) 表示第 \(p\) 个自旋轨道的平均占据数。",
                "理想 state-vector 曲线给出无噪声参考；CETE 和 sequential evolution 的硬件测量点与它比较。",
                "如果 CETE 点列更贴近参考曲线，说明 CETE 在这个可观测量上更好地保持了 TDSE 预测的占据振荡。",
                "Pauli-sum tomography 和 \(10^4\) shots 决定每个点的统计估计方式和噪声水平。",
            ],
            "conclusion": "图 1 的证据链是：RDM 定义 -> Pauli 测量估计 -> 与无噪声 TDSE 参考比较 -> 判断 CETE 的占据动力学质量。",
        }
    if block_id == "F002":
        return {
            "premise": "图 2 要验证的是能量期望值随时间的保持/偏离情况。",
            "steps": [
                r"把哈密顿量写成 Pauli 字符串和 \(\hat H=\sum_j c_jP_j\)，逐项测得 \(\langle P_j\rangle\)。",
                r"能量估计为 \(E(t)=\sum_j c_j\langle P_j\rangle_t\)，有限 shots 会带来约 \(1/\sqrt{N}\) 量级的统计波动。",
                "无噪声 state-vector 曲线是理论参考；硬件点偏离它越小，说明该时间演化线路在能量可观测量上越可靠。",
                "若 sequential evolution 随时间更明显漂移，而 CETE 更贴近参考线，就支持 CETE 在该设置下减少误差累积。",
            ],
            "conclusion": "图 2 的证据链是：Pauli 分解 -> shot 估计能量 -> 与 TDSE/state-vector 参考比较 -> 判断两种演化方法的误差趋势。",
        }
    if "pauli-sum tomography" in key:
        return {
            "premise": "量子硬件不能直接读出任意可观测量，只能通过测量基变换和多次 shots 估计。",
            "steps": [
                r"把目标可观测量写成 \(O=\sum_j c_jP_j\)，其中 \(P_j\) 是 Pauli 字符串。",
                r"分别测量每个 \(P_j\) 的期望值，再按系数加权求和得到 \(\langle O\rangle\)。",
                "shots 越多，统计误差通常越小；但硬件噪声和读出误差不会只靠增加 shots 完全消失。",
            ],
            "conclusion": "图 1/图 2 的点不是精确解析值，而是 Pauli 分解后的有限采样估计。",
        }
    if "sequential short-time propagators" in key:
        return {
            "premise": "顺序短时传播子用很多小步近似总时间演化。",
            "steps": [
                r"把 \(T\) 切成 \(N\) 个 \(\Delta t\)，每步作用 \(e^{-i\hat H\Delta t}\) 或其 Trotter 近似。",
                "步长越小，单步近似误差通常下降；但步数和线路深度增加，硬件噪声和门误差会累积。",
                "CETE 的比较目标就是用更贴近二体相关结构的更新减少这种深线路压力。",
            ],
            "conclusion": "它是合理基线，但在真实硬件上可能被线路深度和误差累积拖累。",
        }
    if "ibm_fez" in key:
        return {
            "premise": "ibm_fez 是实验硬件平台，不是理论变量。",
            "steps": [
                "硬件测量值可以写成理想期望值加上统计噪声、门噪声、退相干和读出误差。",
                "同一算法在 state-vector 模拟和真实设备上的差距，反映了硬件噪声与线路结构的共同影响。",
            ],
            "conclusion": "读图时把 ibm_fez 信息用于判断实验可信度和噪声背景，而不是把它当作 CETE 理论假设。",
        }
    return {
        "premise": "这条反馈没有匹配到稳定推导模板，需要从局部上下文抽取论证对象。",
        "steps": [
            f"先定位短上下文锚点：{clip(source_hint, 180) if source_hint else '当前缺少可用上下文。'}",
            "再判断它属于理论假设、数学步骤、算法更新、实验可观测量，还是非技术说明。",
            "最后把它接到主链条：TDSE 目标 -> 二体收缩/TDCSE -> CETE 线路 -> H2 证据。",
        ],
        "conclusion": "如果这条仍显得泛，需要在 reader HTML 中补一条更具体的自由问题，下一轮画像才能定位到推导缺口。",
    }


def math_physics_derivation_html(
    item: dict[str, Any],
    source: dict[str, Any],
    profile_entry: dict[str, Any] | None,
) -> str:
    concept = clean_inline(item.get("concept") or item.get("selected_text") or "未命名反馈")
    block_id = clean_inline(item.get("block_id") or item.get("bilingual_block_id"))
    status = clean_inline(item.get("status")) or "unrated"
    profile_state = profile_entry_raw_status(profile_entry)
    spec = math_physics_derivation_spec(item, source)
    speed = "慢推导" if status in {"unknown", "learning", "unrated"} or profile_state in {"unknown", "learning", "unrated"} else "快速锚定"
    formulas = "".join(
        html_formula_panel(formula_title, formula, note)
        for formula_title, formula, note in formula_for_item(concept, block_id)
    )
    steps = "".join(f"<li>{inline_markdown_to_html(step)}</li>" for step in spec.get("steps", []))
    return (
        '<section class="explain-panel derivation-panel">'
        f"<h4>数学物理推导线 · {h(speed)}</h4>"
        f'<p class="derivation-premise"><strong>出发点：</strong>{inline_markdown_to_html(spec.get("premise", ""))}</p>'
        f"{formulas}"
        f'<ol class="derivation-steps">{steps}</ol>'
        f'<p class="derivation-conclusion"><strong>推出：</strong>{inline_markdown_to_html(spec.get("conclusion", ""))}</p>'
        "</section>"
    )


def explanation_lines_to_html(lines: list[str]) -> str:
    title = "补充解释"
    items: list[str] = []
    paragraphs: list[str] = []
    for line in lines:
        clean = clean_inline(line)
        if not clean:
            continue
        if clean == "**直接解释**":
            continue
        if clean.startswith("- "):
            items.append(f"<li>{inline_markdown_to_html(clean[2:])}</li>")
        else:
            paragraphs.append(f"<p>{inline_markdown_to_html(clean)}</p>")
    item_html = f"<ul>{''.join(items)}</ul>" if items else ""
    return f'<section class="explain-panel"><h4>{title}</h4>{"".join(paragraphs)}{item_html}</section>'


def source_context_html(item: dict[str, Any], source: dict[str, Any]) -> str:
    block_id = clean_inline(item.get("block_id") or item.get("bilingual_block_id"))
    page = clean_inline(source.get("page") or source.get("caption_page"))
    source_type = clean_inline(source.get("type"))
    source_label = block_id or "未记录 block id"
    if page:
        source_label += f" / p.{page}"
    if source_type:
        source_label += f" / {source_type}"
    summary = source_anchor_summary(item, source, source_label)
    source_url = clean_inline(item.get("source_url"))
    source_title = clean_inline(item.get("source_title"))
    category = clean_inline(item.get("category"))
    panels = [
        html_text_panel("你的原问题", item.get("user_question"), "question", 140, True),
        html_text_panel("选中文本", item.get("selected_text"), "selected", 120, True),
        html_text_panel("反馈摘录", item.get("source_excerpt"), "excerpt", 140, True),
        html_text_panel("英文上下文", item.get("original_context") or source.get("original_text"), "original", 140, True),
        html_text_panel("中文上下文", item.get("translation_context") or source.get("translation"), "translation", 140, True),
    ]
    meta_bits = [
        f"<span><strong>block</strong> {h(source_label)}</span>",
        f"<span><strong>category</strong> {h(category)}</span>" if category else "",
        f"<span><strong>source</strong> {h(source_title)}</span>" if source_title else "",
        f'<span><strong>url</strong> <a href="{h(source_url)}">{h(clip(source_url, 120))}</a></span>' if source_url else "",
    ]
    meta_html = '<p class="source-mini-meta">' + "".join(bit for bit in meta_bits if bit) + "</p>"
    image_path = clean_inline(source.get("image_path"))
    image_html = f'<p class="source-file">图表文件：<code>{h(image_path)}</code></p>' if image_path else ""
    return (
        '<section class="source-panel compact-source">'
        '<details class="source-anchor-details">'
        f'<summary><span class="summary-title">来源锚点</span><span class="summary-text">{h(summary)}</span></summary>'
        '<div class="source-anchor-body">'
        f"{meta_html}"
        '<p class="source-note">默认折叠来源细节，只保留一行定位；需要核对原文、译文或摘录时再展开。</p>'
        f'{"".join(panels)}'
        f"{image_html}"
        "</div>"
        "</details>"
        "</section>"
    )


def knowledge_flow_html(profile: dict[str, Any] | None) -> str:
    nodes = [
        ("TDSE", "完整实时演化目标", ["TDSE", "time-dependent Schrödinger equation (TDSE)"]),
        ("TDCSE", "把目标方程收缩到二体条件", ["TDCSE", "time-dependent contracted Schrödinger equation (TDCSE)"]),
        ("2-RDM / 2K", "二体关联与二体哈密顿量的语言", ["two-particle reduced density matrix (2-RDM)", "2-RDM", "2K"]),
        ("反厄米生成元", "保证指数化后仍是酉演化", ["two-electron unitary", "anti-Hermitian"]),
        ("CETE ansatz", "用双电子酉逐步更新线路", ["CETE algorithm", "correlation-efficient time-evolution (CETE) algorithm", "ansatz"]),
        ("H2 约化", "把特定动力学压到可实验验证的小空间", ["Slater determinant", "H2"]),
        ("1-RDM / Energy", "用图表检验演化结果", ["one-particle reduced density matrix (1-RDM)", "Pauli-sum tomography"]),
    ]
    pieces: list[str] = []
    for index, (title, caption, aliases) in enumerate(nodes):
        entry_status = "unrated"
        for alias in aliases:
            _, entry = find_profile_entry(profile, alias)
            if entry:
                entry_status = profile_entry_raw_status(entry)
                break
        pieces.append(
            f'<div class="flow-node {status_class(entry_status)}">'
            f"<strong>{h(title)}</strong>"
            f"<span>{h(caption)}</span>"
            f'<em>{h(status_text(entry_status))}</em>'
            "</div>"
        )
        if index < len(nodes) - 1:
            pieces.append('<div class="flow-arrow" aria-hidden="true">→</div>')
    return (
        '<section class="panel" id="knowledge-flow">'
        "<h2>知识链条流程图</h2>"
        '<p class="section-note">这是按你的画像给出的阅读路线：绿色可当锚点，黄色/红色是需要优先补物理意义和论文用法的位置。</p>'
        '<div class="flow-scroll"><div class="flow-diagram">'
        f"{''.join(pieces)}"
        "</div></div>"
        "</section>"
    )


def news_category_status(items: list[dict[str, Any]]) -> dict[str, str]:
    grouped: dict[str, list[str]] = {}
    for item in items:
        category = clean_inline(item.get("category")) or "未分类"
        grouped.setdefault(category, []).append(clean_inline(item.get("status")) or "unrated")
    result: dict[str, str] = {}
    for category, statuses in grouped.items():
        if "unknown" in statuses:
            result[category] = "unknown"
        elif "learning" in statuses:
            result[category] = "learning"
        elif "unrated" in statuses:
            result[category] = "unrated"
        elif "known" in statuses:
            result[category] = "known"
        else:
            result[category] = "mastered"
    return result


def news_category_counts(items: list[dict[str, Any]]) -> dict[str, Counter[str]]:
    grouped: dict[str, Counter[str]] = {}
    for item in items:
        category = clean_inline(item.get("category")) or "未分类"
        status = clean_inline(item.get("status")) or "unrated"
        grouped.setdefault(category, Counter())[status] += 1
    return grouped


def news_knowledge_flow_html(items: list[dict[str, Any]], profile: dict[str, Any] | None) -> str:
    category_counts = Counter(clean_inline(item.get("category")) or "未分类" for item in items)
    category_status = news_category_status(items)
    category_breakdown = news_category_counts(items)
    category_cards = []
    for category, count in category_counts.most_common(8):
        status = category_status.get(category, "unrated")
        counts = category_breakdown.get(category, Counter())
        weak = int(counts.get("unknown", 0) + counts.get("learning", 0) + counts.get("unrated", 0))
        stable = int(counts.get("known", 0) + counts.get("mastered", 0))
        category_cards.append(
            f'<div class="news-topic-card {status_class(status)}">'
            f'<div class="topic-card-head"><strong>{h(category)}</strong>{html_status_badge(status)}</div>'
            f'<p>{count} 个知识点 · {weak} 个待解释 · {stable} 个锚点</p>'
            '<div class="topic-status-bar" aria-hidden="true">'
            f'<span class="bar-bad" style="width:{max(0, counts.get("unknown", 0) / count * 100):.1f}%"></span>'
            f'<span class="bar-warn" style="width:{max(0, (counts.get("learning", 0) + counts.get("unrated", 0)) / count * 100):.1f}%"></span>'
            f'<span class="bar-good" style="width:{max(0, stable / count * 100):.1f}%"></span>'
            "</div>"
            "</div>"
        )
    if not category_cards:
        category_cards.append(
            '<div class="news-topic-card neutral"><div class="topic-card-head"><strong>未分类</strong><span class="badge neutral">未判断 / unrated</span></div><p>等待二次反馈补充。</p></div>'
        )
    anchor_text = "、".join(known_profile_anchors(profile, 5)) or "暂无稳定锚点"
    unknown_count = sum(1 for item in items if clean_inline(item.get("status")) == "unknown")
    learning_count = sum(1 for item in items if clean_inline(item.get("status")) in {"learning", "unrated"})
    anchor_count = sum(1 for item in items if clean_inline(item.get("status")) in {"known", "mastered"})
    return (
        '<section class="panel news-flow-panel" id="knowledge-flow">'
        '<div class="news-flow-head">'
        '<div><h2>新闻知识链条流程图</h2>'
        '<p class="section-note">按“来源主张 -> 主题簇 -> 机制/证据 -> 个人画像 -> 二次反馈”组织，不再把新闻读成一条拥挤横线。</p></div>'
        '<div class="news-flow-stats">'
        f'<span class="stat-chip bad">{unknown_count} unknown</span>'
        f'<span class="stat-chip warn">{learning_count} learning/unrated</span>'
        f'<span class="stat-chip good">{anchor_count} anchors</span>'
        "</div></div>"
        '<div class="news-flow-map">'
        '<article class="flow-stage stage-source"><span class="stage-index">01</span><h3>Source Claim</h3><p>先确认来源到底声称了什么，区分事实、预测、政策口径和论文结果。</p></article>'
        '<article class="flow-stage stage-themes"><span class="stage-index">02</span><h3>Theme Clusters</h3><p>主题簇直接显示你的稳定区和卡点区。</p><div class="news-topic-grid">'
        f'{"".join(category_cards)}'
        "</div></article>"
        '<article class="flow-stage stage-mechanism"><span class="stage-index">03</span><h3>Mechanism / Evidence</h3><p>对 unknown/learning 条目按机制、公式、证据强度、限制条件拆解。</p></article>'
        f'<article class="flow-stage stage-profile"><span class="stage-index">04</span><h3>Profile Loop</h3><p>已知锚点：{h(anchor_text)}</p><p>读完后用 <code>news_feedback2.json</code> 把新问题回灌画像。</p></article>'
        "</div>"
        '<div class="news-flow-legend"><span><i class="legend-bad"></i>unknown</span><span><i class="legend-warn"></i>learning/unrated</span><span><i class="legend-good"></i>known/mastered</span></div>'
        "</section>"
    )


def paper_route_html() -> str:
    return """
  <section class="panel" id="route">
    <h2>建议阅读路线</h2>
    <ol>
      <li>先用 TDSE 作为已知锚点：它是完整实时演化目标。</li>
      <li>接着读 TDCSE 和 2-RDM：理解为什么二体收缩在本文条件下足够。</li>
      <li>再读 ansatz 与 two-electron unitary：理解 CETE 怎样把理论条件变成线路。</li>
      <li>最后读 H2 示例、1-RDM/energy 图和 Pauli-sum tomography：看实验如何验证 CETE。</li>
    </ol>
  </section>
"""


def strip_ordered_marker(line: str) -> str:
    return re.sub(r"^\d+\.\s*", "", clean_inline(line))


def news_route_html() -> str:
    return (
        '<section class="panel" id="route">'
        "<h2>建议阅读路线</h2>"
        "<ol>"
        + "".join(f"<li>{inline_markdown_to_html(strip_ordered_marker(line))}</li>" for line in news_route_lines())
        + "</ol>"
        "</section>"
    )


def news_formula_specs(item: dict[str, Any]) -> list[tuple[str, str, str]]:
    concept = clean_inline(item.get("concept") or item.get("selected_text"))
    category = clean_inline(item.get("category"))
    excerpt = clean_inline(item.get("source_excerpt") or item.get("original_context"))
    key = norm_key(" ".join([concept, category, excerpt]))
    formulas: list[tuple[str, str, str]] = []
    if "qubo" in key:
        formulas.append(("QUBO 最小形式", r"\[\min_{x\in\{0,1\}^n} x^\top Qx\]", "读法：LLM/agent 若生成量子应用，关键是把自然语言约束正确落到 Q 矩阵。"))
    if any(token in key for token in ["syndrome", "logical pauli", "error correction", "luci"]):
        formulas.append(("纠错综合征", r"\[s = H e \pmod 2\]", "读法：综合征 s 是错误 e 的可观测投影，decoder 根据它推断最可能修正。"))
    if any(token in key for token in ["quantum walk", "mhv", "parke", "scattering"]):
        formulas.append(("路径振幅叠加", r"\[A=\sum_{\mathrm{paths}}\prod_{e\in path} w_e\]", "读法：量子行走表示的重点是路径权重如何复现目标振幅结构。"))
    if any(token in key for token in ["graph coloring", "transport", "neutral-atom", "compilation"]):
        formulas.append(("冲突图调度", r"\[(i,j)\in E \Rightarrow c_i\ne c_j\]", "读法：相互冲突的门、移动或相互作用不能安排在同一颜色/时间槽。"))
    if any(token in key for token in ["symmetry", "equivariance", "observable orbit", "reservoir"]):
        formulas.append(("可观测量轨道", r"\[\mathcal O_G(O)=\{gOg^{-1}\mid g\in G\}\]", "读法：对称性让一组相关可观测量能由群作用组织起来，减少重复学习。"))
    if any(token in key for token in ["compute", "infrastructure", "cloud", "grid", "neocloud"]):
        formulas.append(("算力有效供给", r"\[\mathrm{capacity}\approx N_{\mathrm{chips}}\times u\times P_{\mathrm{limit}}\times \eta_{\mathrm{network}}\]", "读法：新闻里的电力、网络和租赁模式都会改变真实可用算力。"))
    if any(token in key for token in ["code review", "coding agent", "workflow", "agentic"]):
        formulas.append(("工程吞吐瓶颈", r"\[\mathrm{delivery}=\min(r_{\mathrm{agent}}, r_{\mathrm{review}}, r_{\mathrm{test}})\]", "读法：agent 生成更快时，瓶颈可能转移到人类 review 或测试反馈。"))
    return formulas


def news_signal_html(
    item: dict[str, Any],
    profile_entry: dict[str, Any] | None,
    profile: dict[str, Any] | None,
) -> str:
    status = clean_inline(item.get("status")) or "unrated"
    concept = clean_inline(item.get("concept") or item.get("selected_text") or "未命名反馈")
    category = clean_inline(item.get("category")) or "未分类"
    source_title = clean_inline(item.get("source_title")) or "未记录来源标题"
    source_url = clean_inline(item.get("source_url"))
    question = clean_inline(item.get("user_question") or item.get("note"))
    lens = news_lens(item)
    anchors = known_profile_anchors(profile, 5)
    anchor_text = "、".join(anchors) if anchors else "暂无可直接调用的 known/mastered 锚点"
    profile_state = profile_entry_raw_status(profile_entry)
    depth = "deep" if status in {"unknown", "learning", "unrated"} or profile_state in {"unknown", "learning", "unrated"} else "anchor"
    source_link = f' <a href="{h(source_url)}">source</a>' if source_url else ""
    question_html = f'<p class="context-link"><strong>你的问题/备注：</strong>{inline_markdown_to_html(question)}</p>' if question else ""
    return (
        f'<section class="explain-panel physical-panel {depth}">'
        "<h4>新闻信号、物理/技术意义与个人边界</h4>"
        f'<p class="depth-note">本条按日报模式解析，不套用论文 CETE/TDSE 主线。状态：{h(status_text(status))}；profile：{h(profile_status(profile_entry))}。</p>'
        "<ul>"
        f"<li><strong>知识点：</strong>{h(concept)}；<strong>分类：</strong>{h(category)}；<strong>来源：</strong>{h(source_title)}{source_link}</li>"
        f"<li><strong>本条角色：</strong>{h(lens['role'])}</li>"
        f"<li><strong>机制拆解：</strong>{inline_markdown_to_html(lens['mechanism'])}</li>"
        f"<li><strong>数学/物理读法：</strong>{inline_markdown_to_html(lens['math'])}</li>"
        f"<li><strong>结合你的画像：</strong>{inline_markdown_to_html(lens['boundary'])}</li>"
        f"<li><strong>可借用的已知锚点：</strong>{h(anchor_text)}</li>"
        "</ul>"
        f"{question_html}"
        "</section>"
    )


def news_reasoning_html(item: dict[str, Any], profile_entry: dict[str, Any] | None) -> str:
    concept = clean_inline(item.get("concept") or item.get("selected_text") or "未命名反馈")
    category = clean_inline(item.get("category")) or "未分类"
    source_title = clean_inline(item.get("source_title")) or "未记录来源标题"
    excerpt = clean_inline(item.get("source_excerpt") or item.get("original_context"))
    lens = news_lens(item)
    formulas = "".join(html_formula_panel(title, formula, note) for title, formula, note in news_formula_specs(item))
    steps = [
        f"Source claim：先确认 {source_title} 这条来源到底声称了什么；不要只记标题。",
        f"Mechanism：把 `{concept}` 放回 `{category}`，按“对象、机制、约束、证据”四项拆开。",
        f"Math/physics：{lens['math']}",
        f"Profile action：若本条仍是 unknown/learning，下一轮反馈要写清是定义、机制、证据还是研究相关性不清楚。",
    ]
    if excerpt:
        steps.insert(1, f"Context anchor：{clip(excerpt, 180)}")
    profile_hint = ""
    if profile_entry:
        profile_hint = f'<p class="derivation-conclusion"><strong>画像状态：</strong>{h(profile_status(profile_entry))}</p>'
    return (
        '<section class="explain-panel derivation-panel">'
        "<h4>新闻知识推理链</h4>"
        '<p class="derivation-premise"><strong>出发点：</strong>日报条目不是论文推导段落，先做事实/机制拆解，再决定是否进入数学或物理补课。</p>'
        f"{formulas}"
        '<ol class="derivation-steps">'
        + "".join(f"<li>{inline_markdown_to_html(step)}</li>" for step in steps)
        + "</ol>"
        f"{profile_hint}"
        "</section>"
    )


def news_followup_html(item: dict[str, Any]) -> str:
    return (
        '<details class="followup"><summary>可以继续追问</summary>'
        "<ul>"
        + "".join(f"<li>{inline_markdown_to_html(line[3:] if line.startswith('- ') else line)}</li>" for line in news_followup_lines(item))
        + "</ul>"
        "</details>"
    )


def paper_next_questions_html() -> str:
    return """
  <section class="panel" id="next">
    <h2>后续可直接问 Codex 的问题</h2>
    <ul>
      <li>请按公式推导详细解释 S009：为什么 TDCSE 残差加权后等价于 TDSE 方差？</li>
      <li>请用一个二能级 H2 玩具模型解释 S018 的单量子比特约化。</li>
      <li>请把 CETE 与普通 Trotter/sequential short-time propagators 做逐项对比。</li>
      <li>请只围绕图 1 和图 2 解释本文的实验证据链。</li>
    </ul>
  </section>
"""


def news_next_questions_html() -> str:
    return """
  <section class="panel" id="next">
    <h2>后续可直接问 Codex 的问题</h2>
    <ul>
      <li>请按 source claim -> mechanism -> evidence -> implication 解析本次所有 unknown 条目。</li>
      <li>请把 AI for Quantum 与 Quantum machine learning 两类新闻按研究路径做对比。</li>
      <li>请解释本次日报里 QEC、neutral-atom、quantum walk 三条量子方向各自卡在什么物理/数学边界。</li>
      <li>请根据我的画像，把这些新闻整理成下一周需要复习的知识队列。</li>
    </ul>
  </section>
"""


def build_html_report(
    feedback_path: Path,
    feedback: dict[str, Any],
    reader_dir: Path,
    profile_path: Path | None,
    profile: dict[str, Any] | None,
    source_map_path: Path | None,
    source_by_id: dict[str, dict[str, Any]],
    glossary: dict[str, dict[str, Any]],
    warnings: list[str],
    mathjax_url: str | None,
) -> str:
    items = list(feedback.get("items", []) or [])
    news_mode = is_news_feedback(feedback, feedback_path)
    title = feedback_display_title(feedback, reader_dir)
    page_title = f"{title} - 阅读反馈全解析"
    generated = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    status_counts = Counter((clean_inline(item.get("status")) or "unrated") for item in items)
    known_items = [item for item in items if clean_inline(item.get("status")) in {"known", "mastered"}]
    explain_items = [item for item in items if needs_explanation(item)]
    report_claim = (
        "本页把日报 feedback、个人知识画像和新闻来源摘录组织成可检查的知识边界报告：先按主题簇看已知/未知，再逐条拆 source claim、机制、证据和研究相关性。它只读取输入并写报告，不修改 `.agents`。"
        if news_mode
        else "本页把导出的 reader feedback、个人知识画像和 source map 组织成可检查的阅读报告：先给出知识边界，再列证据矩阵，最后逐条解释每个不清楚或需要巩固的点。它只读取输入并写报告，不修改 `.agents`。"
    )
    boundary_text = (
        "这些卡片解释本次 news feedback 的状态分布；它们不是新闻事实判断，而是你的阅读知识边界。"
        if news_mode
        else "这些卡片解释本次 feedback 的状态分布；它们不是论文结论，而是你的阅读状态。"
    )
    source_map_value = (
        "news feedback 内嵌来源摘录"
        if news_mode
        else (source_map_path if source_by_id else "未加载")
    )
    html_role = "日报反馈解析，不作为新闻原文全文证据" if news_mode else "阅读反馈解析，不作为论文原始证据"
    flow_section = news_knowledge_flow_html(items, profile) if news_mode else knowledge_flow_html(profile)
    route_section = news_route_html() if news_mode else paper_route_html()
    next_questions_section = news_next_questions_html() if news_mode else paper_next_questions_html()

    status_cards = []
    for status in ["unknown", "learning", "known", "mastered", "unrated"]:
        status_cards.append(
            f'<div class="stat-card {status_class(status)}">'
            f"<span>{h(status_text(status))}</span>"
            f"<strong>{int(status_counts.get(status, 0))}</strong>"
            "</div>"
        )

    known_html = "".join(f"<li>{h(short_concept(item))}</li>" for item in known_items) or "<li>这次 feedback 没有 known/mastered 条目。</li>"
    explain_html = "".join(
        f"<li><a href=\"#item-{index:02d}\">{h(short_concept(item))}</a> {html_status_badge(clean_inline(item.get('status')) or 'unrated')}</li>"
        for index, item in enumerate(items, start=1)
        if needs_explanation(item)
    ) or "<li>这次 feedback 没有需要展开解释的条目。</li>"

    evidence_rows = []
    for index, item in enumerate(items, start=1):
        concept = clean_inline(item.get("concept") or item.get("selected_text") or "未命名反馈")
        block_id = clean_inline(item.get("block_id") or item.get("bilingual_block_id"))
        source = source_context_for_item(item, source_by_id)
        source_available = bool(source) or (
            news_mode and bool(clean_inline(item.get("source_excerpt") or item.get("source_title") or item.get("source_url")))
        )
        profile_name, profile_entry = find_profile_entry(profile, concept)
        profile_label = profile_status(profile_entry)
        if profile_name and profile_name != concept:
            profile_label += f" / {profile_name}"
        evidence_rows.append(
            "<tr>"
            f"<td><a href=\"#item-{index:02d}\">{index:02d}</a></td>"
            f"<td>{h(short_concept(item, 80))}</td>"
            f"<td>{h(block_id or '无')}</td>"
            f"<td>{h(CONFUSION_LABELS.get(clean_inline(item.get('confusion_type')), clean_inline(item.get('confusion_type')) or '未指定'))}</td>"
            f"<td>{html_status_badge(clean_inline(item.get('status')) or 'unrated')}</td>"
            f"<td>{h(profile_label)}</td>"
            f"<td>{h('内嵌摘录' if news_mode and source_available else ('可用' if source_available else '缺失'))}</td>"
            "</tr>"
        )

    item_cards = []
    for index, item in enumerate(items, start=1):
        concept = clean_inline(item.get("concept") or item.get("selected_text") or "未命名反馈")
        status = clean_inline(item.get("status")) or "unrated"
        kind = clean_inline(item.get("annotation_kind")) or "unknown"
        confusion = clean_inline(item.get("confusion_type"))
        block_id = clean_inline(item.get("block_id") or item.get("bilingual_block_id"))
        source = source_context_for_item(item, source_by_id)
        glossary_entry = find_glossary_entry(glossary, concept)
        if glossary_entry and kind != "concept" and len(concept) > 80:
            glossary_entry = None
        profile_name, profile_entry = find_profile_entry(profile, concept)
        source_warning = ""
        if block_id and not source and not news_mode:
            source_warning = f'<p class="warning">source_map.json 中未找到 <code>{h(block_id)}</code>，本条解释使用 feedback 文本。</p>'
        profile_match = html_meta("profile 匹配项", profile_name) if profile_name and profile_name != concept else ""
        if news_mode:
            meaning_panel = news_signal_html(item, profile_entry, profile)
            reasoning_panel = news_reasoning_html(item, profile_entry)
            followup_panel = news_followup_html(item)
        else:
            meaning_panel = physical_meaning_html(item, source, glossary_entry, profile_entry, profile)
            reasoning_panel = math_physics_derivation_html(item, source, profile_entry)
            followup_panel = (
                '<details class="followup"><summary>可以继续追问</summary>'
                "<ul>"
                f"<li>请围绕 <code>{h(block_id or short_concept(item, 40))}</code> 再展开公式/物理意义。</li>"
                f"<li>把 <code>{h(short_concept(item, 40))}</code> 和 CETE 主线重新串起来。</li>"
                "</ul>"
                "</details>"
            )
        item_cards.append(
            f'<article class="item-card" id="item-{index:02d}">'
            '<header class="item-head">'
            f'<span class="item-number">{index:02d}</span>'
            f"<div><h3>{h(short_concept(item, 120))}</h3>"
            f'<div class="badges">{html_status_badge(status)}<span class="badge neutral">{h(CONFUSION_LABELS.get(confusion, confusion or "未指定"))}</span></div></div>'
            "</header>"
            '<dl class="meta-grid">'
            f'{html_meta("反馈状态", status_text(status))}'
            f'{html_meta("profile 状态", profile_status(profile_entry))}'
            f"{profile_match}"
            f'{html_meta("标注类型", kind)}'
            f'{html_meta("source block", block_id or "无")}'
            f'{html_meta("选中语言", item.get("selected_language") or "无")}'
            "</dl>"
            f"{source_warning}"
            f"{source_context_html(item, source)}"
            f"{meaning_panel}"
            f"{reasoning_panel}"
            f"{followup_panel}"
            "</article>"
        )

    warning_html = ""
    if warnings:
        warning_html = '<aside class="warning-box"><strong>输入提醒</strong><ul>' + "".join(f"<li>{h(w)}</li>" for w in warnings) + "</ul></aside>"

    mathjax_src = mathjax_script_src(mathjax_url)
    mathjax = ""
    if mathjax_src:
        mathjax = f"""
<script>
window.MathJax = {{
  tex: {{ inlineMath: [['$', '$'], ['\\\\(', '\\\\)']], displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']] }},
  chtml: {{ displayAlign: 'left', displayIndent: '0' }},
  options: {{ skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'] }}
}};
</script>
<script async src="{html_lib.escape(mathjax_src)}"></script>
"""

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{h(page_title)}</title>
<style>
:root {{
  color-scheme: light;
  --bg: #f6f7fb;
  --paper: #ffffff;
  --ink: #172033;
  --muted: #667085;
  --line: #d8deea;
  --soft: #eef4ff;
  --accent: #2454d6;
  --good: #0f766e;
  --warn: #a15c07;
  --bad: #b42318;
  --neutral: #475467;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
  line-height: 1.65;
}}
header.hero {{
  background: #111827;
  color: #fff;
  padding: 34px 24px;
}}
.hero-inner, main {{
  max-width: 1180px;
  margin: 0 auto;
}}
.kicker {{
  margin: 0 0 8px;
  color: #b6c2d6;
  font-size: 13px;
}}
h1 {{
  margin: 0;
  font-size: 32px;
  line-height: 1.2;
  letter-spacing: 0;
}}
.claim {{
  max-width: 920px;
  margin: 14px 0 0;
  color: #e5e7eb;
  font-size: 16px;
}}
.hero-grid {{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 22px;
}}
.hero-card, .panel, .item-card, .warning-box {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--paper);
}}
.hero-card {{
  background: rgba(255,255,255,0.08);
  border-color: rgba(255,255,255,0.2);
  padding: 14px;
}}
.hero-card span {{
  display: block;
  color: #cbd5e1;
  font-size: 12px;
}}
.hero-card strong {{
  display: block;
  margin-top: 5px;
  color: #fff;
  font-size: 18px;
  overflow-wrap: anywhere;
}}
main {{
  padding: 28px 20px 54px;
}}
section {{
  margin: 26px 0;
}}
.panel {{
  padding: 20px;
}}
h2 {{
  margin: 0 0 12px;
  font-size: 22px;
  line-height: 1.3;
  letter-spacing: 0;
}}
h3 {{
  margin: 0 0 8px;
  font-size: 18px;
  letter-spacing: 0;
}}
h4 {{
  margin: 0 0 8px;
  color: #0f172a;
}}
.stat-grid {{
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
  margin-top: 14px;
}}
.stat-card {{
  border: 1px solid var(--line);
  border-left-width: 4px;
  border-radius: 8px;
  padding: 12px;
  background: #fff;
}}
.stat-card span {{
  color: var(--muted);
  font-size: 12px;
}}
.stat-card strong {{
  display: block;
  font-size: 24px;
}}
.good {{ border-color: rgba(15,118,110,.35); color: var(--good); }}
.warn {{ border-color: rgba(161,92,7,.35); color: var(--warn); }}
.bad {{ border-color: rgba(180,35,24,.35); color: var(--bad); }}
.neutral {{ border-color: rgba(71,84,103,.35); color: var(--neutral); }}
.two-col {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}}
ul, ol {{
  margin: 8px 0 0;
  padding-left: 22px;
}}
li {{
  margin: 5px 0;
}}
.badge {{
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid currentColor;
  border-radius: 999px;
  padding: 2px 8px;
  background: #fff;
  font-size: 12px;
  white-space: nowrap;
}}
.table-wrap {{
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
}}
table {{
  width: 100%;
  border-collapse: collapse;
  background: #fff;
}}
caption {{
  caption-side: top;
  padding: 12px;
  color: var(--muted);
  text-align: left;
}}
th, td {{
  border-bottom: 1px solid #e5eaf2;
  padding: 10px;
  text-align: left;
  vertical-align: top;
  letter-spacing: 0;
}}
th {{
  background: #f8fafc;
  font-weight: 700;
}}
.item-card {{
  padding: 18px;
  margin: 16px 0;
}}
.item-head {{
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 12px;
  align-items: start;
}}
.item-number {{
  display: inline-flex;
  width: 36px;
  height: 36px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  font-weight: 700;
}}
.badges {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}}
.meta-grid {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 14px 0;
}}
.meta-grid div {{
  border: 1px solid #e5eaf2;
  border-radius: 6px;
  padding: 9px;
  background: #fbfcff;
}}
dt {{
  margin: 0 0 3px;
  color: var(--muted);
  font-size: 12px;
}}
dd {{
  margin: 0;
  overflow-wrap: anywhere;
}}
.source-panel, .explain-panel {{
  margin-top: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 14px;
  background: #fff;
}}
.compact-source {{
  padding: 0;
  background: #fbfcff;
  overflow: hidden;
}}
.source-anchor-details > summary {{
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  padding: 10px 12px;
  cursor: pointer;
  color: var(--ink);
  list-style: none;
}}
.source-anchor-details > summary::-webkit-details-marker {{
  display: none;
}}
.source-anchor-details > summary::before {{
  content: "▶";
  color: var(--accent);
  font-size: 11px;
}}
.source-anchor-details[open] > summary::before {{
  content: "▼";
}}
.summary-title {{
  flex: 0 0 auto;
  font-weight: 700;
}}
.summary-text {{
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--muted);
  font-size: 13px;
}}
.source-anchor-body {{
  border-top: 1px solid var(--line);
  padding: 10px 12px 12px;
}}
.source-id {{
  margin: 0 0 10px;
  color: var(--muted);
}}
.source-mini-meta {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin: 0 0 8px;
  color: var(--muted);
  font-size: 12px;
}}
.source-mini-meta span {{
  overflow-wrap: anywhere;
}}
.source-note, .section-note {{
  margin: 0 0 10px;
  color: var(--muted);
  font-size: 13px;
}}
.text-panel {{
  margin: 8px 0;
  border-left: 3px solid #c7d2fe;
  padding: 8px 10px;
  background: #f8faff;
}}
.text-panel.question {{ border-left-color: #f59e0b; background: #fffbeb; }}
.text-panel.translation {{ border-left-color: #22c55e; background: #f0fdf4; }}
.text-panel.selected {{ border-left-color: #2454d6; background: #eef4ff; }}
.text-panel.original {{ border-left-color: #64748b; background: #f8fafc; }}
.text-panel.excerpt {{ border-left-color: #8b5cf6; background: #f5f3ff; }}
.panel-label {{
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 2px;
}}
.text-panel p, .explain-panel p {{
  margin: 0;
}}
.context-details {{
  margin-top: 6px;
}}
.context-details summary, .followup summary {{
  cursor: pointer;
  color: var(--accent);
  font-weight: 600;
}}
.context-details p {{
  margin-top: 8px;
  max-height: 240px;
  overflow: auto;
  padding: 8px;
  border: 1px solid #e5eaf2;
  border-radius: 6px;
  background: #fff;
}}
.physical-panel {{
  border-left: 4px solid var(--accent);
}}
.physical-panel.deep {{
  background: #fbfdff;
}}
.physical-panel.anchor {{
  border-left-color: var(--good);
}}
.depth-note, .context-link, .formula-note {{
  color: var(--muted);
  font-size: 13px;
}}
.formula-panel {{
  margin-top: 12px;
  border: 1px solid #d7e3ff;
  border-radius: 8px;
  background: #f8fbff;
  padding: 12px;
}}
.derivation-panel {{
  border-left: 4px solid #1d4ed8;
  background: #f9fbff;
}}
.derivation-premise, .derivation-conclusion {{
  margin: 0;
}}
.derivation-steps {{
  margin-top: 12px;
  padding-left: 24px;
}}
.derivation-steps li {{
  margin: 8px 0;
}}
.derivation-conclusion {{
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 6px;
  background: #eef4ff;
}}
.formula-title {{
  margin-bottom: 6px;
  color: #1d4ed8;
  font-weight: 700;
  font-size: 13px;
}}
.math-display {{
  overflow-x: auto;
  padding: 10px 12px;
  border-radius: 6px;
  background: #ffffff;
  color: #0f172a;
  font-family: Cambria Math, "Times New Roman", serif;
  font-size: 18px;
  line-height: 1.45;
}}
.MathJax, mjx-container {{
  overflow-x: auto;
  overflow-y: hidden;
  max-width: 100%;
}}
.news-flow-panel {{
  border-color: #cbd8ea;
  background: #fbfcff;
}}
.news-flow-head {{
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 16px;
  align-items: start;
}}
.news-flow-head h2 {{
  margin-bottom: 4px;
}}
.news-flow-stats {{
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}}
.stat-chip {{
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  border: 1px solid currentColor;
  border-radius: 999px;
  padding: 3px 10px;
  background: #fff;
  font-size: 12px;
  font-weight: 700;
}}
.news-flow-map {{
  display: grid;
  grid-template-columns: minmax(150px, .7fr) minmax(360px, 2.1fr) minmax(170px, .8fr) minmax(190px, .9fr);
  gap: 12px;
  align-items: stretch;
  margin-top: 14px;
}}
.flow-stage {{
  position: relative;
  min-height: 178px;
  border: 1px solid #d6deea;
  border-radius: 8px;
  background: #fff;
  padding: 14px;
  box-shadow: 0 8px 18px rgba(15, 23, 42, .04);
}}
.flow-stage::after {{
  content: "→";
  position: absolute;
  top: 50%;
  right: -13px;
  width: 24px;
  height: 24px;
  border: 1px solid #d6deea;
  border-radius: 999px;
  background: #fbfcff;
  color: #475467;
  display: flex;
  align-items: center;
  justify-content: center;
  transform: translateY(-50%);
  font-size: 14px;
  font-weight: 700;
  z-index: 1;
}}
.flow-stage:last-child::after {{
  display: none;
}}
.flow-stage h3 {{
  margin: 6px 0 7px;
  font-size: 15px;
}}
.flow-stage p {{
  margin: 0;
  color: #475467;
  font-size: 13px;
  line-height: 1.55;
}}
.stage-index {{
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 30px;
  height: 24px;
  border-radius: 999px;
  background: #eef4ff;
  color: #2454d6;
  font-size: 12px;
  font-weight: 800;
}}
.stage-source {{
  border-top: 4px solid #2454d6;
}}
.stage-themes {{
  border-top: 4px solid #0f766e;
}}
.stage-mechanism {{
  border-top: 4px solid #a15c07;
}}
.stage-profile {{
  border-top: 4px solid #475467;
}}
.news-topic-grid {{
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 9px;
  margin-top: 12px;
}}
.news-topic-card {{
  border: 1px solid #d8deea;
  border-radius: 8px;
  background: #ffffff;
  padding: 10px;
  min-height: 86px;
}}
.news-topic-card.bad {{
  border-left: 4px solid var(--bad);
}}
.news-topic-card.warn {{
  border-left: 4px solid var(--warn);
}}
.news-topic-card.good {{
  border-left: 4px solid var(--good);
}}
.news-topic-card.neutral {{
  border-left: 4px solid var(--neutral);
}}
.topic-card-head {{
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: start;
}}
.topic-card-head strong {{
  overflow-wrap: anywhere;
  font-size: 13px;
  line-height: 1.35;
}}
.news-topic-card p {{
  margin: 8px 0 0;
  color: #667085;
  font-size: 12px;
}}
.topic-status-bar {{
  display: flex;
  height: 7px;
  margin-top: 9px;
  overflow: hidden;
  border-radius: 999px;
  background: #eef2f7;
}}
.topic-status-bar span {{
  display: block;
  min-width: 0;
}}
.bar-bad {{
  background: var(--bad);
}}
.bar-warn {{
  background: var(--warn);
}}
.bar-good {{
  background: var(--good);
}}
.news-flow-legend {{
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
  color: #667085;
  font-size: 12px;
}}
.news-flow-legend span {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
}}
.news-flow-legend i {{
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 999px;
}}
.legend-bad {{
  background: var(--bad);
}}
.legend-warn {{
  background: var(--warn);
}}
.legend-good {{
  background: var(--good);
}}
.flow-scroll {{
  overflow-x: auto;
  padding: 4px 0;
}}
.flow-diagram {{
  display: grid;
  grid-template-columns: repeat(13, max-content);
  gap: 8px;
  align-items: center;
  min-width: max-content;
}}
.flow-node {{
  width: 150px;
  min-height: 118px;
  border: 1px solid currentColor;
  border-radius: 8px;
  background: #fff;
  padding: 10px;
}}
.flow-node strong, .flow-node span, .flow-node em {{
  display: block;
}}
.flow-node strong {{
  color: #111827;
  font-size: 14px;
}}
.flow-node span {{
  margin-top: 5px;
  color: #475467;
  font-size: 12px;
  line-height: 1.45;
}}
.flow-node em {{
  margin-top: 8px;
  font-style: normal;
  font-size: 11px;
}}
.flow-arrow {{
  color: #667085;
  font-size: 24px;
}}
code {{
  padding: 1px 5px;
  border-radius: 4px;
  background: #eef2f7;
  font-family: Consolas, "Cascadia Mono", monospace;
  font-size: .92em;
}}
.warning, .warning-box {{
  color: #7a2e0e;
  background: #fff7ed;
  border-color: #fed7aa;
}}
.warning {{
  border-radius: 6px;
  padding: 8px 10px;
}}
.warning-box {{
  padding: 14px;
}}
.followup {{
  margin-top: 12px;
}}
footer {{
  margin-top: 28px;
  color: var(--muted);
  font-size: 13px;
}}
@page {{ size: A4; margin: 18mm 16mm; }}
@media (max-width: 900px) {{
  .hero-grid, .stat-grid, .two-col, .meta-grid {{ grid-template-columns: 1fr; }}
  .news-flow-head, .news-flow-map {{ grid-template-columns: 1fr; }}
  .news-flow-stats {{ justify-content: flex-start; }}
  .flow-stage::after {{
    content: "↓";
    top: auto;
    right: auto;
    bottom: -13px;
    left: 18px;
    transform: none;
  }}
  .flow-stage:last-child::after {{ display: none; }}
  .news-topic-grid {{ grid-template-columns: 1fr; }}
  h1 {{ font-size: 24px; }}
  header.hero {{ padding: 24px 16px; }}
  main {{ padding: 18px 12px 36px; }}
}}
@media print {{
  body {{ background: #fff; }}
  header.hero {{ background: #fff; color: #111827; border-bottom: 1px solid var(--line); }}
  .claim, .kicker, .hero-card span, footer {{ color: #475467; }}
  .hero-card {{ background: #fff; border-color: var(--line); }}
  .hero-card strong {{ color: #111827; }}
  .item-card, .panel, .source-panel, .explain-panel, table {{ break-inside: avoid; }}
}}
</style>
{mathjax}
</head>
<body>
<header class="hero">
  <div class="hero-inner">
    <p class="kicker">Read Feedback Skill · Profile-aware explanation report</p>
    <h1>{h(page_title)}</h1>
    <p class="claim">{h(report_claim)}</p>
    <div class="hero-grid">
      <div class="hero-card"><span>Feedback items</span><strong>{len(items)}</strong></div>
      <div class="hero-card"><span>Needs explanation</span><strong>{len(explain_items)}</strong></div>
      <div class="hero-card"><span>Profile</span><strong>{h('loaded' if profile else 'missing')}</strong></div>
      <div class="hero-card"><span>Generated</span><strong>{h(generated)}</strong></div>
    </div>
  </div>
</header>
<main>
  <section class="panel" id="metadata">
    <h2>生成信息</h2>
    <dl class="meta-grid">
      {html_meta("feedback", feedback_path)}
      {html_meta("reader directory", reader_dir)}
      {html_meta("profile", profile_path if profile else "未加载")}
      {html_meta("source_map", source_map_value)}
      {html_meta("HTML role", html_role)}
      {html_meta("Profile mutation", "不会修改 .agents")}
    </dl>
    {warning_html}
  </section>

  <section class="panel" id="boundary">
    <h2>个人知识边界快照</h2>
    <p>{h(boundary_text)}</p>
    <div class="stat-grid">
      {''.join(status_cards)}
    </div>
    <div class="two-col">
      <div>
        <h3>已知锚点</h3>
        <ul>{known_html}</ul>
      </div>
      <div>
        <h3>需要优先解释</h3>
        <ul>{explain_html}</ul>
      </div>
    </div>
  </section>

  {flow_section}

  {route_section}

  <section id="evidence" class="panel">
    <h2>证据矩阵</h2>
    <p>表格用于快速定位每条反馈的概念、source block、问题类型、profile 状态和 source_map 可用性。</p>
    <div class="table-wrap">
      <table>
        <caption>Feedback item matrix. Source 可用表示该 block 能从 source_map.json 找到上下文。</caption>
        <thead>
          <tr><th>#</th><th>Concept / annotation</th><th>Block</th><th>Question type</th><th>Feedback</th><th>Profile</th><th>Source</th></tr>
        </thead>
        <tbody>
          {''.join(evidence_rows)}
        </tbody>
      </table>
    </div>
  </section>

  <section id="items">
    <h2>逐条解析</h2>
    {''.join(item_cards)}
  </section>

  {next_questions_section}

  <footer>Generated by read-feedback-skill. This HTML is self-contained except optional MathJax loading for formula rendering.</footer>
</main>
</body>
</html>
"""


def analysis_task_for_item(item: dict[str, Any]) -> str:
    confusion = clean_inline(item.get("confusion_type"))
    if confusion == "math_step":
        return (
            "Reconstruct the mathematical derivation. Identify every symbol, the premise used before the step, "
            "the algebraic or variational move, why the implication is valid, and what remains an assumption."
        )
    if confusion == "algorithm_step":
        return (
            "Explain the algorithmic mechanism. Separate inputs, state variables, update rule, stopping condition, "
            "output, and how the step follows from the paper's theory."
        )
    if confusion == "evidence":
        return (
            "Analyze the evidence chain. Explain what the figure/table measures, what comparison is being made, "
            "what claim it supports, and what limitations or alternative interpretations remain."
        )
    if confusion == "paper_usage":
        return (
            "Explain the paper-specific role. Do not stop at a textbook definition; show how this concept functions "
            "inside the paper's claim, method, or experiment."
        )
    if confusion == "relation":
        return (
            "Build the relationship graph. Show how this item connects to upstream assumptions and downstream "
            "algorithm/evidence claims."
        )
    if confusion == "assumption":
        return (
            "Audit the assumption. State where it enters, why the paper needs it, what breaks if it is false, "
            "and whether experiments actually test it."
        )
    if confusion == "term_definition":
        return (
            "Define the term only as a starting point, then connect it to the local derivation or research claim."
        )
    return (
        "Infer the right analysis mode from context. Answer what it is, why it matters here, how it connects to "
        "the paper's reasoning, and what the user should verify next."
    )


def related_source_blocks(item: dict[str, Any], source_by_id: dict[str, dict[str, Any]], limit: int = 4) -> list[dict[str, Any]]:
    concept = clean_inline(item.get("concept") or item.get("selected_text"))
    if not concept:
        return []
    folded = concept.casefold()
    tokens = {
        token.casefold()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", concept)
        if len(token) >= 3
    }
    phrases = {folded}
    abbreviations = re.findall(r"\(([A-Za-z0-9_-]{2,12})\)", concept)
    phrases.update(abbrev.casefold() for abbrev in abbreviations)
    if "schrödinger" in folded or "schrodinger" in folded:
        tokens.add("schr")
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for block_id, block in source_by_id.items():
        text = clean_inline(
            " ".join(
                str(block.get(key) or "")
                for key in ("original_text", "translation", "caption", "label", "title")
            )
        )
        if not text:
            continue
        text_key = text.casefold()
        score = 0
        for phrase in phrases:
            if phrase and phrase in text_key:
                score += 8
        for token in tokens:
            if token and token in text_key:
                score += 2
        if score:
            scored.append((score, block_id, block))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [block for _, _, block in scored[:limit]]


def build_research_context_pack(
    feedback_path: Path,
    feedback: dict[str, Any],
    reader_dir: Path,
    profile_path: Path | None,
    profile: dict[str, Any] | None,
    source_map_path: Path | None,
    source_by_id: dict[str, dict[str, Any]],
    glossary: dict[str, dict[str, Any]],
    warnings: list[str],
) -> str:
    items = list(feedback.get("items", []) or [])
    title = clean_inline(feedback.get("paper_title")) or reader_dir.name.replace("_reader", "")
    lines: list[str] = []
    lines.append(f"# {title} - Research Deep-Dive Context Pack")
    lines.append("")
    lines.append("This file is not the final explanation. It is the source-grounded workspace for writing the final research/derivation report.")
    lines.append("")
    lines.append("## Metadata")
    lines.append("")
    lines.append(bullet("feedback", str(feedback_path), 300))
    lines.append(bullet("reader directory", str(reader_dir), 300))
    lines.append(bullet("profile", str(profile_path) if profile else "not loaded", 300))
    lines.append(bullet("source_map", str(source_map_path) if source_by_id else "not loaded", 300))
    lines.append(bullet("feedback items", len(items), 80))
    if warnings:
        lines.append(bullet("warnings", "; ".join(warnings), 500))
    lines.append("")
    lines.append("## Required Final Report Behavior")
    lines.append("")
    lines.append("- Reconstruct the paper's research logic before answering isolated concepts.")
    lines.append("- For every math or algorithm item, write a step-by-step derivation or mechanism analysis.")
    lines.append("- For evidence items, connect plots/tables to the exact claim they support and state limitations.")
    lines.append("- Mark unsupported inferences explicitly; do not invent claims beyond feedback/source_map/profile evidence.")
    lines.append("- Write for this user's knowledge boundary: use known items as anchors and spend depth on unknown/learning facets.")
    lines.append("- Final deliverables should be `feedback_research_deep_dive.md` and `feedback_research_deep_dive.html`.")
    lines.append("")
    lines.append("## Paper-Level Research Questions To Reconstruct")
    lines.append("")
    lines.append("1. What problem is the paper trying to solve?")
    lines.append("2. What exact claim does the algorithm make, and under what assumptions?")
    lines.append("3. What is the core derivation chain from physical equation to executable algorithm?")
    lines.append("4. Which figures/tables are evidence for which claims?")
    lines.append("5. What should the user understand first to make the paper readable?")
    lines.append("")
    lines.append("## Feedback Item Dossiers")
    lines.append("")
    for index, item in enumerate(items, start=1):
        concept = clean_inline(item.get("concept") or item.get("selected_text") or "Unnamed feedback")
        block_id = clean_inline(item.get("block_id") or item.get("bilingual_block_id"))
        source = source_context_for_item(item, source_by_id)
        glossary_entry = find_glossary_entry(glossary, concept)
        profile_name, profile_entry = find_profile_entry(profile, concept)
        page = clean_inline(source.get("page") or source.get("caption_page"))
        source_type = clean_inline(source.get("type"))
        lines.append(f"### {index:02d}. {short_concept(item, 140)}")
        lines.append("")
        lines.append(bullet("analysis assignment", analysis_task_for_item(item), 700))
        lines.append(bullet("feedback status", status_text(clean_inline(item.get("status")) or "unrated"), 160))
        lines.append(bullet("profile status", profile_status(profile_entry), 220))
        if profile_name and profile_name != concept:
            lines.append(bullet("profile match", profile_name, 180))
        lines.append(bullet("annotation kind", clean_inline(item.get("annotation_kind")) or "unknown", 120))
        lines.append(bullet("question type", CONFUSION_LABELS.get(clean_inline(item.get("confusion_type")), clean_inline(item.get("confusion_type")) or "unspecified"), 160))
        lines.append(bullet("source block", block_id or "missing", 120))
        if page or source_type:
            lines.append(bullet("source location", f"page={page or 'unknown'}, type={source_type or 'unknown'}", 160))
        if glossary_entry:
            lines.append(bullet("glossary translation", glossary_entry.get("translation") or "", 220))
            lines.append(bullet("glossary note", glossary_entry.get("note") or "", 300))
        lines.append("")
        lines.append("#### User Feedback")
        lines.append("")
        lines.append(bullet("user question", item.get("user_question"), 900))
        lines.append(bullet("user note", item.get("note"), 900))
        lines.append(bullet("selected text", item.get("selected_text"), 1200))
        lines.append(bullet("selected language", item.get("selected_language"), 120))
        lines.append("")
        lines.append("#### Source Context")
        lines.append("")
        lines.append(bullet("original context", item.get("original_context") or source.get("original_text"), 1800))
        lines.append(bullet("translation context", item.get("translation_context") or source.get("translation"), 1800))
        lines.append(bullet("feedback/source excerpt", item.get("source_excerpt"), 1400))
        if clean_inline(source.get("image_path")):
            lines.append(bullet("image/table asset", source.get("image_path"), 300))
        if not source and block_id:
            lines.append(bullet("source warning", f"{block_id} was not found in source_map.json", 260))
        related_blocks = related_source_blocks(item, source_by_id)
        if related_blocks:
            lines.append("")
            lines.append("#### Related Source Blocks")
            lines.append("")
            for related in related_blocks:
                related_id = clean_inline(related.get("id") or related.get("caption_id") or "unknown")
                related_page = clean_inline(related.get("page") or related.get("caption_page"))
                label = related_id if not related_page else f"{related_id} / p.{related_page}"
                lines.append(bullet("related block", label, 160))
                lines.append(bullet("related original", related.get("original_text"), 1000))
                lines.append(bullet("related translation", related.get("translation"), 1000))
        if profile_entry:
            lines.append("")
            lines.append("#### Learner Profile Context")
            lines.append("")
            lines.append(bullet("learning needs", ", ".join(profile_entry.get("learning_needs", []) or []), 300))
            lines.append(bullet("latest user note", profile_entry.get("user_note"), 500))
            lines.append(bullet("existing ai explanation", profile_entry.get("ai_explanation"), 900))
        lines.append("")
        lines.append("#### Final Deep-Dive Requirements For This Item")
        lines.append("")
        lines.append("- Explain from first principles only as much as needed.")
        lines.append("- Then connect the explanation to this exact source block or feedback context.")
        lines.append("- If the item involves a formula, write the premise -> transformation -> conclusion chain.")
        lines.append("- If the item involves evidence, state the measured quantity, reference/baseline, supported claim, and limitation.")
        lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="Feedback JSON file or reader directory.")
    parser.add_argument("--feedback", help="Feedback JSON file exported from reader HTML.")
    parser.add_argument("--reader-dir", help="Reader bundle directory.")
    parser.add_argument("--profile", help="Learner profile JSON. Defaults to nearest .agents/reader-learner/knowledge_profile.json.")
    parser.add_argument("--source-map", help="source_map.json path. Defaults to <reader-dir>/source_map.json.")
    parser.add_argument("--output", help="Output Markdown path. Defaults to <reader-dir>/feedback_explanations.md.")
    parser.add_argument("--html-output", help="Output HTML path. Defaults to the Markdown output path with .html suffix.")
    parser.add_argument("--no-html", action="store_true", help="Only write Markdown; do not generate the HTML report.")
    parser.add_argument("--no-interactive-feedback", action="store_true", help="Do not attach the lean-html-skill feedback2 export panel to generated HTML.")
    parser.add_argument("--context-output", help="Output research context-pack Markdown path. Defaults to <reader-dir>/feedback_research_context.md.")
    parser.add_argument("--no-context", action="store_true", help="Do not write the research context pack.")
    parser.add_argument(
        "--mathjax-url",
        default="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js",
        help="MathJax script URL/path for HTML formula rendering. Use 'none' to disable.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    feedback_path = find_feedback_path(args.feedback or args.input).resolve()
    feedback = load_json(feedback_path)
    reader_dir = infer_reader_dir(feedback_path, feedback, args.reader_dir).resolve()

    profile_path = find_profile(reader_dir, args.profile)
    profile: dict[str, Any] | None = None
    warnings: list[str] = []
    if profile_path and profile_path.exists():
        profile = load_json(profile_path)
    else:
        if profile_path:
            warnings.append(f"profile not found: {profile_path}")
        else:
            warnings.append("profile not found")

    source_map_path = Path(args.source_map).resolve() if args.source_map else reader_dir / "source_map.json"
    source_by_id, glossary, source_warnings = load_source_map(source_map_path)
    warnings.extend(source_warnings)

    output_path = Path(args.output).resolve() if args.output else reader_dir / "feedback_explanations.md"
    report = build_report(
        feedback_path=feedback_path,
        feedback=feedback,
        reader_dir=reader_dir,
        profile_path=profile_path,
        profile=profile,
        source_map_path=source_map_path,
        source_by_id=source_by_id,
        glossary=glossary,
        warnings=warnings,
    )
    write_text(output_path, report)
    context_path: Path | None = None
    if not args.no_context:
        context_path = Path(args.context_output).resolve() if args.context_output else reader_dir / "feedback_research_context.md"
        context_pack = build_research_context_pack(
            feedback_path=feedback_path,
            feedback=feedback,
            reader_dir=reader_dir,
            profile_path=profile_path,
            profile=profile,
            source_map_path=source_map_path,
            source_by_id=source_by_id,
            glossary=glossary,
            warnings=warnings,
        )
        write_text(context_path, context_pack)
    html_path: Path | None = None
    if not args.no_html:
        html_path = Path(args.html_output).resolve() if args.html_output else output_path.with_suffix(".html")
        html_report = build_html_report(
            feedback_path=feedback_path,
            feedback=feedback,
            reader_dir=reader_dir,
            profile_path=profile_path,
            profile=profile,
            source_map_path=source_map_path,
            source_by_id=source_by_id,
            glossary=glossary,
            warnings=warnings,
            mathjax_url=args.mathjax_url,
        )
        write_html(html_path, html_report)
        if not args.no_interactive_feedback:
            warning = attach_lean_feedback_panel(html_path, feedback_path, reader_dir)
            if warning:
                warnings.append(warning)
    print(f"Wrote {output_path}")
    if context_path:
        print(f"Wrote {context_path}")
    if html_path:
        print(f"Wrote {html_path}")
    print(f"Items: {len(feedback.get('items', []) or [])}")
    print(f"Profile: {profile_path if profile else 'not loaded'}")
    print(f"Source map: {source_map_path if source_by_id else 'not loaded'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
