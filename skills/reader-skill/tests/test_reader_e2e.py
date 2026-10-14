#!/usr/bin/env python3
"""End-to-end formal-reader v3 contract test.

The detailed fixture lives with the completion-state tests so the same run
exercises resume, stale invalidation, progress isolation, preflight, canonical
compilation, formal HTML rendering, and adversarial audit in one pipeline.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
V3_TEST = ROOT / "skills" / "reader-skill" / "tests" / "test_completion_state_v3.py"


def main() -> int:
    result = subprocess.run(
        [sys.executable, str(V3_TEST)], cwd=ROOT,
        text=True, encoding="utf-8", errors="replace", capture_output=True,
    )
    if result.returncode:
        raise AssertionError(f"formal-reader v3 E2E failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")
    # Inspect current generated runtime rather than an unrelated historical HTML.
    sys.path.insert(0, str(ROOT / 'skills' / 'reader-skill' / 'scripts'))
    from markdown_reader_to_html import css
    from reader_html_contract import feedback_interaction_issues
    from feedback_ux import feedback_ux_runtime_script
    failures = feedback_interaction_issues('<style>' + css() + '</style>' + feedback_ux_runtime_script() + '''
    function repaintFeedback() {}
    function afterSuccessfulExport() {
      persistRecoveryNow();
  }''')
    if failures:
        raise AssertionError(f'current feedback/layout contract regressed: {failures}')
    print("reader-skill v3 E2E passed: resumable completion, formal render, and adversarial audit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
