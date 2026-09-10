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
        selected, job, state_path, report_path = builder.load_or_create_job(
            pdf_dir=source_root, reader_root=output_root, discovered=rows, max_papers=1, resume=False,
        )
        if [row["filename"] for row in selected] != ["Alpha.PDF"]:
            raise AssertionError("max-papers did not freeze the deterministic directory prefix")
        if not state_path.is_file() or report_path.exists() or job.get("status") != "active":
            raise AssertionError("directory selection did not persist a valid resumable job state")
        try:
            state_path.relative_to(output_root / builder.JOB_DIR_NAME)
        except ValueError as exc:
            raise AssertionError("job state escaped the generated reader-root job directory") from exc

        (source / "zeta.pdf").write_bytes(b"zeta-v2")
        changed_rows = builder.discover_pdfs(source_root)
        changed_snapshot = builder.build_input_snapshot(source_root, changed_rows)
        if snapshot["source_set_sha256"] == changed_snapshot["source_set_sha256"]:
            raise AssertionError("changed PDF hash did not change the in-memory source-set identity")

        resumed, resumed_job, _, _ = builder.load_or_create_job(
            pdf_dir=source_root, reader_root=output_root, discovered=changed_rows, max_papers=1, resume=True,
        )
        if resumed[0]["sha256"] != selected[0]["sha256"] or resumed_job.get("attempts") != 2:
            raise AssertionError("resume did not preserve and heartbeat the frozen selected PDF")

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
