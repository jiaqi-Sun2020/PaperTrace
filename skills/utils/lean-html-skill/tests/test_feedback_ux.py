from __future__ import annotations

import sys
import re
import shutil
import subprocess
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from feedback_ux import feedback_ux_runtime_script, feedback_ux_styles
from lean_html import feedback_html


class FeedbackUXContractTests(unittest.TestCase):
    def test_runtime_exposes_autosave_selection_and_undo(self) -> None:
        runtime = feedback_ux_runtime_script()
        self.assertIn('data-papertrace-feedback-ux="v1"', runtime)
        self.assertIn("createAutosave", runtime)
        self.assertIn("createSelectionToolbar", runtime)
        self.assertIn("createUndo", runtime)
        self.assertIn("if (!pending) return null", runtime)
        self.assertIn("settings.delay", runtime)
        self.assertIn('root.document.addEventListener("selectionchange", scheduleReconcile)', runtime)
        self.assertIn("else hide()", runtime)
        self.assertIn("interactingWithToolbar", runtime)
        self.assertIn("selectingInRoot", runtime)

    def test_styles_keep_toolbar_accessible_on_narrow_screens(self) -> None:
        styles = feedback_ux_styles()
        self.assertIn(".papertrace-selection-toolbar", styles)
        self.assertIn("min-height: 44px", styles)
        self.assertIn(".papertrace-save-indicator", styles)
        self.assertIn(".papertrace-undo-indicator", styles)
        self.assertIn("var(--reader-status-saved-bg", styles)
        self.assertIn("var(--reader-status-learning-bg", styles)
        self.assertIn("var(--reader-status-unknown-bg", styles)
        self.assertIn("var(--reader-danger-bg", styles)

    def test_generic_feedback_fragment_uses_autosave_without_legacy_button(self) -> None:
        fragment = feedback_html(
            {
                "export_filename": "feedback.json",
                "items": [],
                "source": {"title": "Contract fixture"},
            },
            "default",
        )
        self.assertIn("PaperTraceFeedbackUX.createAutosave", fragment)
        self.assertIn("lean-html-selection-toolbar", fragment)
        self.assertIn("visibilitychange", fragment)
        self.assertNotIn("Save mark", fragment)
        self.assertNotIn('id="lean-html-save"', fragment)
        node = shutil.which("node")
        if node:
            scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", fragment, re.S)
            self.assertGreaterEqual(len(scripts), 2)
            for script in scripts:
                checked = subprocess.run(
                    [node, "--check", "-"],
                    input=script,
                    text=True,
                    encoding="utf-8",
                    capture_output=True,
                )
                self.assertEqual(checked.returncode, 0, checked.stderr)


if __name__ == "__main__":
    unittest.main()
