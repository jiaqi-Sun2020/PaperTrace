#!/usr/bin/env python3
"""Raw materialization and v3 non-formal completion boundary tests."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MATERIALIZER = ROOT / "skills" / "nature-reader" / "scripts" / "materialize_reader_markdown.py"
COMPLETER = ROOT / "skills" / "nature-reader" / "scripts" / "complete_reader_bundle.py"


def source_map() -> dict:
    return {
        "paper": {"title": "Materialization Fixture", "source_type": "fixture", "page_count": 1, "source_pdf_sha256": "b" * 64},
        "blocks": [
            {"id": "S001", "page": 1, "type": "paragraph", "original_text": "A source-grounded claim."},
            {"id": "R001", "page": 1, "type": "reference", "original_text": "[1] Original reference."},
        ],
        "pages": [], "figures": [], "tables": [], "algorithms": [],
    }


def run(script: Path, reader: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(script), str(reader)], cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="materialize_v3_", dir=ROOT) as temporary:
        reader = Path(temporary) / "reader"
        reader.mkdir()
        source_path = reader / "source_map.json"
        source_path.write_text(json.dumps(source_map(), ensure_ascii=False, indent=2), encoding="utf-8")
        source_before = source_path.read_bytes()

        materialized = run(MATERIALIZER, reader)
        if materialized.returncode:
            raise AssertionError(materialized.stderr)
        markdown = (reader / "paper.md").read_text(encoding="utf-8")
        if "[translation-required]" not in markdown or "**Reference list (original only):**" not in markdown:
            raise AssertionError("raw materialization did not preserve draft/reference boundaries")
        if source_path.read_bytes() != source_before:
            raise AssertionError("materializer mutated immutable source_map.json")

        completion = run(COMPLETER, reader)
        if completion.returncode != 1 or '"pipeline_status": "completion_required"' not in completion.stdout:
            raise AssertionError(f"v3 completion did not remain pending\n{completion.stdout}\n{completion.stderr}")
        for path in (
            reader / "reader_wiki" / "completion_run_state.json",
            reader / "reader_wiki" / "completion_blocks" / "block--S001.json",
            reader / "reader_progress.html",
        ):
            if not path.exists():
                raise AssertionError(f"missing v3 pending artifact: {path.name}")
        if (reader / "reader_interactive.html").exists():
            raise AssertionError("pending completion wrote a formal reader_interactive.html")
        progress = (reader / "reader_progress.html").read_text(encoding="utf-8")
        if "INCOMPLETE / NOT FORMAL" not in progress or "downloadFeedback" in progress:
            raise AssertionError("progress HTML violates non-formal isolation")

    print("materialization/v3 pending boundary tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
