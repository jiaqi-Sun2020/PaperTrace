#!/usr/bin/env python3
"""Regression tests for the explicit reader-math boundary."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from formula_contract import atomic_formula_issues, bilingual_math_issues, source_math_evidence_issues, source_math_inventory_issues  # noqa: E402


class FormulaContractTests(unittest.TestCase):
    def test_explicit_inline_math_is_accepted(self) -> None:
        text = r"The inverse is \((K+\sigma_n^2 I)^{-1}\)."
        self.assertEqual(atomic_formula_issues(text, field="Original"), [])

    def test_raw_tex_in_ordinary_prose_is_rejected(self) -> None:
        issues = atomic_formula_issues(r"noise is \sigma_n^2", field="Original")
        self.assertTrue(any("raw TeX command" in issue for issue in issues), issues)

    def test_ascii_superscript_outside_math_is_rejected(self) -> None:
        issues = atomic_formula_issues("alpha=A^-1y", field="Chinese")
        self.assertTrue(any("subscript/superscript" in issue for issue in issues), issues)

    def test_pdf_layout_math_fragment_is_rejected(self) -> None:
        issues = atomic_formula_issues("estimate b\nK before inversion", field="Original")
        self.assertTrue(any("raw PDF math fragment" in issue for issue in issues), issues)

    def test_independent_display_formulas_cannot_be_packed(self) -> None:
        issues = atomic_formula_issues(r"\[a=b\qquad c=d\]", field="Original")
        self.assertTrue(any("multiple logical formulas" in issue for issue in issues), issues)

    def test_split_indexed_identifier_is_rejected(self) -> None:
        issues = source_math_evidence_issues("the score sensmarg\nij is large", field="Source evidence")
        self.assertTrue(any("split indexed identifier" in issue for issue in issues), issues)

    def test_unicode_pdf_math_glyph_is_rejected(self) -> None:
        issues = source_math_evidence_issues("the derivative ∂ei/∂Kij is used", field="Source evidence")
        self.assertTrue(any("Unicode mathematical glyph" in issue for issue in issues), issues)

    def test_source_evidence_detects_math_inside_a_paragraph(self) -> None:
        source = "Let the estimator default to b\nKij=c. Then ∂L/∂Kij controls coverage."
        issues = source_math_evidence_issues(source, field="Source evidence")
        self.assertTrue(any("detached accent/hat glyph" in issue for issue in issues), issues)
        self.assertTrue(any("Unicode mathematical glyph" in issue for issue in issues), issues)

    def test_source_math_inventory_requires_every_component_on_both_sides(self) -> None:
        metadata = {
            "source_math_inventory": {
                "contract": "source-math-inventory-v1",
                "status": "complete",
                "components": [
                    {"id": "eq1", "presentation": "display", "signature": r"x=y"},
                    {"id": "eq2", "presentation": "inline", "signature": r"A^{-1}"},
                ],
            },
        }
        original = r"\[x=y\] and \(A^{-1}\)"
        zh = r"\[x=y\] 与 \(A^{-1}\)"
        self.assertEqual(source_math_inventory_issues(metadata, original, zh, block_id="S012"), [])
        issues = source_math_inventory_issues(metadata, original, r"\[x=y\]", block_id="S012")
        self.assertTrue(any("Chinese math inventory count mismatch" in issue for issue in issues), issues)

    def test_exact_bilingual_contract_accepts_equivalent_delimiters(self) -> None:
        self.assertEqual(
            bilingual_math_issues(r"value \(A^{-1}\)", r"取值 $A^{-1}$", block_id="S004"),
            [],
        )

    def test_exact_bilingual_contract_rejects_missing_component(self) -> None:
        issues = bilingual_math_issues(r"value \(A^{-1}\)", "取逆矩阵", block_id="S004")
        self.assertTrue(any("count mismatch" in issue for issue in issues), issues)


if __name__ == "__main__":
    unittest.main()
