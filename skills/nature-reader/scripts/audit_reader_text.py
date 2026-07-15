#!/usr/bin/env python3
"""Audit PaperTrace reader text for UTF-8 and visible corruption failures."""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path
from typing import Iterable


MOJIBAKE_MARKERS = (
    "\ufffd",
    "\u951f\u65a4\u62f7",
    "ï¿½",
)


def audit_text(value: str) -> list[str]:
    issues: list[str] = []
    for marker in MOJIBAKE_MARKERS:
        if marker in value:
            issues.append(f"visible corruption marker present: {marker!r}")

    controls = sorted(
        {
            f"U+{ord(char):04X}"
            for char in value
            if unicodedata.category(char) == "Cc" and char not in "\n\r\t"
        }
    )
    if controls:
        issues.append("disallowed control characters present: " + ", ".join(controls))

    damaged_lines: list[int] = []
    for line_no, line in enumerate(value.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        question_count = stripped.count("?")
        if "????" in stripped or (question_count >= 8 and question_count / len(stripped) >= 0.15):
            damaged_lines.append(line_no)
    if damaged_lines:
        preview = ", ".join(str(line_no) for line_no in damaged_lines[:12])
        suffix = "..." if len(damaged_lines) > 12 else ""
        issues.append(f"question-mark replacement pattern on lines: {preview}{suffix}")
    return issues


def audit_path(path: Path) -> tuple[list[str], str]:
    try:
        value = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [f"file is not valid UTF-8: {exc}"], ""
    return audit_text(value), value


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    path = args.path.expanduser().resolve()
    if not path.is_file():
        print(json.dumps({"status": "fail", "path": str(path), "issues": ["file not found"]}, indent=2))
        return 2
    issues, value = audit_path(path)
    print(json.dumps({
        "status": "fail" if issues else "pass",
        "path": str(path),
        "characters": len(value),
        "issues": issues,
    }, ensure_ascii=False, indent=2))
    return 2 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
