#!/usr/bin/env python3
"""Materialize the bundled bilingual demo templates safely."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = SKILL_ROOT / "assets"


def html_filename(value: str) -> str:
    candidate = Path(value)
    if candidate.name != value or candidate.suffix.lower() != ".html":
        raise argparse.ArgumentTypeError("use a plain .html filename without directories")
    return value


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
        shutil.copyfile(source, temp_path)
        os.replace(temp_path, destination)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create Chinese and English demo HTML files from demo-skill assets."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Destination directory (default: current directory).",
    )
    parser.add_argument("--zh-name", type=html_filename, default="demo.html")
    parser.add_argument("--en-name", type=html_filename, default="demo-en.html")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace existing destination files atomically.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.zh_name.casefold() == args.en_name.casefold():
        print("Chinese and English output filenames must differ.", file=sys.stderr)
        return 2
    output_dir = args.output_dir.expanduser().resolve()
    pairs = (
        (ASSET_DIR / "demo.html", output_dir / args.zh_name),
        (ASSET_DIR / "demo-en.html", output_dir / args.en_name),
    )

    missing_assets = [str(source) for source, _ in pairs if not source.is_file()]
    if missing_assets:
        print("Missing bundled template(s): " + ", ".join(missing_assets), file=sys.stderr)
        return 2

    existing = [str(destination) for _, destination in pairs if destination.exists()]
    if existing and not args.force:
        print(
            "Refusing to overwrite existing file(s): " + ", ".join(existing),
            file=sys.stderr,
        )
        print("Choose another output directory or pass --force explicitly.", file=sys.stderr)
        return 1

    for source, destination in pairs:
        atomic_copy(source, destination)
        print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
