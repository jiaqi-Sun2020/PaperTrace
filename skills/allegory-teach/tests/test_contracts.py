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
                "no-variable-renaming-disguise",
                "dual-spine-coupling",
                "worked-example-not-fable",
                "causal-completeness-before-brevity",
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
            "greenhouse",
            "dyehouse",
            "温室",
            "染坊",
            "ledger",
            "shopkeeper",
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

    def test_fable_requires_governing_rule_origin_before_calculation(self) -> None:
        skill = self.read("SKILL.md")
        story = self.read("references/story-output-contract.md")
        story_flat = " ".join(story.split())
        payload = json.loads(self.read("tests/regression_cases.json"))
        truncation = next(
            case
            for case in payload["cases"]
            if case["id"] == "mathematical-truncation"
        )
        nonmathematical = next(
            case
            for case in payload["cases"]
            if case["id"] == "nonmathematical-state-transition"
        )

        self.assertIn("A visible rule is not yet an explained rule", skill)
        self.assertIn("## Governing-rule origin gate", story)
        self.assertIn("Before the first calculation, update, transition", story_flat)
        self.assertIn("source of the governing rule", story_flat)
        self.assertIn(
            "The delayed reveal may continue to hide the concept name",
            story_flat,
        )
        self.assertIn(
            "the derivation or plain-language source of the checked-coordinate rule",
            truncation["must_preserve"],
        )
        self.assertIn(
            "introducing a calculation rule as an unexplained machine habit",
            truncation["must_avoid"],
        )
        self.assertIn(
            "making the story checkable only after the debrief supplies the missing derivation",
            truncation["must_avoid"],
        )
        self.assertIn(
            "the protocol or constraint that licenses the transition",
            nonmathematical["must_preserve"],
        )
        self.assertIn("decorative formula", nonmathematical["must_avoid"])
        self.assertIn(
            "Do not manufacture a formula or formal derivation",
            story_flat,
        )

    def test_story_or_bridge_value_gate_repairs_then_falls_back(self) -> None:
        skill = " ".join(self.read("SKILL.md").split())
        bridge = " ".join(self.read("references/bridge-mode-contract.md").split())
        daily = " ".join(self.read("references/daily-briefing-interface.md").split())
        self.assertIn("Story-or-Bridge value gate", skill)
        self.assertIn("A fable is valid only when its actions teach the mechanism", skill)
        self.assertIn("perform one repair pass", skill)
        self.assertIn("downgrade transparently", skill)
        self.assertIn("A good Bridge Mode explanation is preferable to a weak fable", bridge)
        self.assertIn("inspect the remaining academic items in descending rank order", daily)
        self.assertIn('selection_basis="explicit_override"', daily)

    def test_fable_requires_action_coupled_dual_spines(self) -> None:
        story = " ".join(self.read("references/story-output-contract.md").split())
        self.assertIn("Story-value and dual-spine gate", story)
        self.assertIn("actor goal -> real limit or missing information", story)
        self.assertIn("technical objective -> governing-rule source", story)
        self.assertIn("The actor must do more than read values and report arithmetic", story)
        self.assertIn("story action -> technical operation -> why it is required", story)

    def test_complete_story_precedes_brevity(self) -> None:
        skill = " ".join(self.read("SKILL.md").split())
        story = " ".join(self.read("references/story-output-contract.md").split())
        daily = " ".join(self.read("references/daily-briefing-interface.md").split())
        self.assertIn("Complete the story and technical causal spines before compressing", skill)
        self.assertIn("no total word, paragraph, or mechanism paragraph limit", story)
        self.assertIn("transport safety boundary, not to the whole story", story)
        self.assertIn("transport boundary, not a total story-length budget", daily)
        self.assertIn("Never truncate", story)

    def test_worked_example_is_not_a_fable_by_scenery(self) -> None:
        contract = " ".join(
            self.read("references/worked-example-contract.md").split()
        )
        self.assertIn("Do not confuse a worked example with a fable", contract)
        self.assertIn("given values -> apply rule -> calculate result -> compare result", contract)
        self.assertIn("does not turn a worked example into a Fable Mode story", contract)


if __name__ == "__main__":
    unittest.main()
