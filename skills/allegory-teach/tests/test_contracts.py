import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
REFERENCES_DIR = SKILL_DIR / "references"


class AllegoryTeachContractTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (SKILL_DIR / relative_path).read_text(encoding="utf-8")

    def test_regression_cases_are_property_based(self) -> None:
        payload = json.loads(self.read("tests/regression_cases.json"))
        self.assertEqual(payload["version"], 1)
        cases = payload["cases"]
        self.assertEqual(
            {case["id"] for case in cases},
            {
                "mathematical-truncation",
                "nonmathematical-state-transition",
                "direct-case-is-sufficient",
                "undefined-metaphor",
                "cognitive-overload",
                "multiple-relations",
                "delayed-reveal",
            },
        )
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertIn(case["mode"], {"bridge", "fable"})
                self.assertTrue(case["concept"])
                self.assertTrue(case["expected_device"])
                self.assertTrue(case["must_preserve"])
                self.assertTrue(case["must_avoid"])
                self.assertNotIn("required_story_terms", case)

    def test_production_contracts_contain_no_fixed_regression_story(self) -> None:
        production = "\n".join(
            [
                self.read("SKILL.md"),
                *(
                    path.read_text(encoding="utf-8")
                    for path in sorted(REFERENCES_DIR.glob("*.md"))
                ),
            ]
        )
        for forbidden in (
            "## Regression case",
            "## Fully worked",
            "mountain city",
            "Carleman linearization",
            "spectral gap",
            "\\dot{x}=x+x^2",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, production)

    def test_two_hard_gates_and_five_comprehension_checks_are_explicit(self) -> None:
        skill = self.read("SKILL.md")
        story = self.read("references/story-output-contract.md")
        self.assertIn(
            "Technical correctness and beginner\ncomprehensibility are independent hard gates",
            skill,
        )
        for gate in (
            "Plain-Language Gate",
            "Self-Explanation Test",
            "Cognitive Compression Test",
            "Literal Reconstruction Test",
            "Predicted Follow-up Test",
        ):
            with self.subTest(gate=gate):
                self.assertIn(gate, skill)
                self.assertIn(gate, story)

    def test_bridge_analogy_is_conditional(self) -> None:
        bridge = self.read("references/bridge-mode-contract.md")
        self.assertIn("Need-an-analogy decision", bridge)
        self.assertIn("optional local analogy", bridge)
        self.assertIn("concrete case already repairs the bridge", bridge)

    def test_factual_return_uses_decoding_order(self) -> None:
        for relative_path in (
            "SKILL.md",
            "references/story-output-contract.md",
            "references/daily-briefing-interface.md",
        ):
            with self.subTest(relative_path=relative_path):
                text = self.read(relative_path)
                self.assertIn("1 -> 2 -> 3 -> 4", text)
                self.assertNotIn("1 -> 3 -> 4 -> 2", text)

    def test_worked_example_avoids_duplicate_story_run(self) -> None:
        contract = self.read("references/worked-example-contract.md")
        self.assertIn("one-example-one-job discipline", contract)
        self.assertIn("must not retell the story", contract)
        self.assertIn("Concrete domain cases belong in `tests/regression_cases.json`", contract)


if __name__ == "__main__":
    unittest.main()
