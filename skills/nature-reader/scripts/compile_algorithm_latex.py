#!/usr/bin/env python3
"""Compile one source-faithful Algorithm LaTeX file to PDF and SVG.

The algorithm body stays in the source language.  Chinese is permitted only
inside ``\\Comment{...}``, which represents translation of an actual algorithm
comment rather than a translated duplicate of the algorithm.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


CJK_RE = re.compile(r"[\u3400-\u9fff]")
COMMENT_RE = re.compile(r"\\Comment\{((?:[^{}]|\{[^{}]*\})*)\}")
STATE_RE = re.compile(r"(?m)^\s*\\State(?:x)?\b")
FATAL_LOG_MARKERS = ("Undefined control sequence", "LaTeX Error:", "Missing character:")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def strip_comment_bodies(text: str) -> tuple[str, list[str]]:
    comments: list[str] = []

    def replace(match: re.Match[str]) -> str:
        comments.append(match.group(1))
        return r"\Comment{}"

    return COMMENT_RE.sub(replace, text), comments


def validate_source(tex: str) -> tuple[int, int]:
    body_without_comments, comments = strip_comment_bodies(tex)
    if CJK_RE.search(body_without_comments):
        raise ValueError("Algorithm LaTeX contains Chinese outside \\Comment{...}")
    if "\\begin{algorithmic}" not in tex or "\\end{algorithmic}" not in tex:
        raise ValueError("Algorithm LaTeX must contain one algorithmic environment")
    if "\\Require" not in tex or "\\Ensure" not in tex:
        raise ValueError("Algorithm LaTeX must preserve Require and Ensure")
    state_count = len(STATE_RE.findall(tex))
    if state_count < 2:
        raise ValueError("Algorithm LaTeX must contain at least two numbered states")
    translated_comments = sum(1 for value in comments if CJK_RE.search(value))
    return state_count, translated_comments


def run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, encoding="utf-8", errors="replace", capture_output=True)


def compile_algorithm(tex_path: Path, output_dir: Path) -> dict[str, object]:
    tex_path = tex_path.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    tex = tex_path.read_text(encoding="utf-8")
    state_count, translated_comments = validate_source(tex)

    latexmk = shutil.which("latexmk")
    xelatex = shutil.which("xelatex")
    dvisvgm = shutil.which("dvisvgm")
    if not xelatex or not dvisvgm:
        raise RuntimeError("xelatex and dvisvgm are required for compiled Algorithm assets")

    build_dir = output_dir / ".algorithm-build" / tex_path.stem
    build_dir.mkdir(parents=True, exist_ok=True)
    if latexmk:
        compile_command = [
            latexmk, "-norc", "-xelatex", "-interaction=nonstopmode", "-halt-on-error",
            f"-outdir={build_dir}", str(tex_path),
        ]
        engine = "latexmk-xelatex"
    else:
        compile_command = [
            xelatex, "-interaction=nonstopmode", "-halt-on-error",
            f"-output-directory={build_dir}", str(tex_path),
        ]
        engine = "xelatex"
    compiled = run(compile_command, cwd=tex_path.parent)
    compile_log = (compiled.stdout or "") + "\n" + (compiled.stderr or "")
    if compiled.returncode != 0:
        raise RuntimeError("Algorithm LaTeX compilation failed:\n" + compile_log[-4000:])

    pdf_build = build_dir / f"{tex_path.stem}.pdf"
    log_build = build_dir / f"{tex_path.stem}.log"
    log_text = log_build.read_text(encoding="utf-8", errors="replace") if log_build.exists() else compile_log
    fatal_markers = [marker for marker in FATAL_LOG_MARKERS if marker in log_text]
    if fatal_markers:
        raise RuntimeError("Algorithm LaTeX log failed: " + ", ".join(fatal_markers))
    if not pdf_build.exists() or pdf_build.stat().st_size == 0:
        raise RuntimeError("Algorithm compiler produced no PDF")

    pdf_path = output_dir / f"{tex_path.stem}.pdf"
    svg_path = output_dir / f"{tex_path.stem}.svg"
    shutil.copy2(pdf_build, pdf_path)
    converted = run(
        [dvisvgm, "--pdf", "--page=1", "--no-fonts", f"--output={svg_path}", str(pdf_path)],
        cwd=output_dir,
    )
    if converted.returncode != 0 or not svg_path.exists() or svg_path.stat().st_size == 0:
        raise RuntimeError("Algorithm PDF-to-SVG conversion failed:\n" + ((converted.stdout or "") + (converted.stderr or ""))[-4000:])

    manifest = {
        "schema_version": 1,
        "contract": "latex-compiled-algorithm-v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "engine": engine,
        "tex_path": tex_path.name,
        "tex_sha256": sha256_file(tex_path),
        "pdf_path": pdf_path.name,
        "pdf_sha256": sha256_file(pdf_path),
        "svg_path": svg_path.name,
        "svg_sha256": sha256_file(svg_path),
        "numbered_states": state_count,
        "translated_comments": translated_comments,
        "status": "pass",
        "compile_status": "pass",
    }
    manifest_path = output_dir / f"{tex_path.stem}.compile.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tex", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir or args.tex.parent
    manifest = compile_algorithm(args.tex, output_dir)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
