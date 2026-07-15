#!/usr/bin/env python3
"""Directory-selected batch input contract tests."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "skills" / "reader-skill" / "scripts"
NATURE_SCRIPTS = ROOT / "skills" / "nature-reader" / "scripts"
for path in (SCRIPTS, NATURE_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def load_builder():
    path = SCRIPTS / "build_formal_reader_batch.py"
    spec = importlib.util.spec_from_file_location("directory_batch_builder", path)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load directory batch builder")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    builder = load_builder()
    with tempfile.TemporaryDirectory(prefix="reader_source_") as source_tmp, tempfile.TemporaryDirectory(prefix="reader_output_", dir=ROOT) as output_tmp:
        source = Path(source_tmp)
        (source / "zeta.pdf").write_bytes(b"zeta-v1")
        (source / "Alpha.PDF").write_bytes(b"alpha-v1")
        (source / "ignore.txt").write_text("not a PDF", encoding="utf-8")
        output = Path(output_tmp)

        source_root, output_root = builder.validate_roots(source, output)
        rows = builder.discover_pdfs(source_root)
        if [row["filename"] for row in rows] != ["Alpha.PDF", "zeta.pdf"]:
            raise AssertionError("directory PDF discovery is not deterministic case-insensitive filename order")
        snapshot = builder.build_input_snapshot(source_root, rows)
        if snapshot["expected_count"] != 2 or snapshot["papers"] != rows:
            raise AssertionError("directory input snapshot does not preserve exact paths/hashes/order")
        if (output_root / ".reader_pipeline_runs").exists() or (output_root / "reader_batch_state.json").exists():
            raise AssertionError("input discovery persisted forbidden batch metadata")

        (source / "zeta.pdf").write_bytes(b"zeta-v2")
        changed_rows = builder.discover_pdfs(source_root)
        changed_snapshot = builder.build_input_snapshot(source_root, changed_rows)
        if snapshot["source_set_sha256"] == changed_snapshot["source_set_sha256"]:
            raise AssertionError("changed PDF hash did not change the in-memory source-set identity")

        nested = source / "nested"
        nested.mkdir()
        (nested / "legacy.pdf").write_bytes(b"legacy")
        if len(builder.discover_pdfs(source_root)) != 2:
            raise AssertionError("non-recursive directory selection included a nested PDF")

        try:
            builder.validate_roots(ROOT, output)
        except ValueError:
            pass
        else:
            raise AssertionError("project-local PDF directory bypassed read-only source/output isolation")

    print("directory batch input tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
