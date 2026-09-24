import json
import unittest
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
REFERENCES_DIR = SKILL_DIR / "references"
REPO_ROOT = Path(__file__).resolve().parents[3]


class AllegoryTeachContractTests(unittest.TestCase):
    def test_context_regression_coverage(self) -> None:
        # Coverage validation only: these fixtures require semantic evaluation,
        # not keyword-based certification of a generated story.
        cases = json.loads(self.read("tests/regression_cases.json"))["cases"]
        ids = [case["id"] for case in cases]
        self.assertEqual(len(ids), len(set(ids)))
        required = {
            "source-context-missing", "context-already-sufficient",
            "no-documented-baseline", "legitimate-cross-domain-reuse",
            "context-without-term-leakage", "memory-goal-not-evidence",
        }
        self.assertTrue(required.issubset(ids))
        for case in cases:
            if case["id"] in required:
                self.assertEqual(case["mode"], "fable")
                self.assertGreaterEqual(len(case["must_preserve"]), 2)
                self.assertGreaterEqual(len(case["must_avoid"]), 2)

    def read(self, relative_path: str) -> str:
        return (SKILL_DIR / relative_path).read_text(encoding="utf-8")

    def test_regression_cases_are_property_based(self) -> None:
        payload = json.loads(self.read("tests/regression_cases.json"))
        self.assertEqual(payload["version"], 1)
        cases = payload["cases"]
        self.assertTrue(
            {case["id"] for case in cases}.issuperset(
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
                "state-space-is-not-information-recovery",
                "unsupported-mechanism-detail",
                "operation-type-separation",
                "metric-identity-and-composition",
                "claim-strength-and-scope",
                "exit-at-evidence-boundary",
                "closed-story-world-language",
                "symbol-free-narrative",
                "narrative-perspective-lock",
                "story-native-metric-projection",
                "rule-origin-without-term-leakage",
                "terminology-restoration",
                "everyday-completeness-over-budget",
                "everyday-invented-apparatus",
                "everyday-recovery-boundary",
                "everyday-local-identifiability",
                "everyday-independent-technical-example",
            }),
        )
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertIn(case["mode"], {"bridge", "fable", "everyday"})
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
            "matched beats",
            "echo tunnel",
            "railway station",
            "档案库",
            "卡片柜",
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
        self.assertIn("The sealed narrative hides the concept name", story_flat)
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
        self.assertIn("Story-value repair gate", skill)
        self.assertIn("A fable is valid only when its actions teach the mechanism", skill)
        self.assertIn("perform one repair pass", skill)
        self.assertIn("without switching modes", " ".join(self.read("references/narrative-language-firewall.md").split()))
        self.assertIn("A good Bridge Mode explanation is preferable to a weak fable", bridge)
        self.assertIn("inspect remaining academic items in rank order", daily)
        self.assertIn('selection_basis="explicit_override"', daily)

    def test_fable_requires_action_coupled_dual_spines(self) -> None:
        story = " ".join(self.read("references/story-output-contract.md").split())
        self.assertIn("Story-value and dual-spine gate", story)
        self.assertIn("actor goal -> real limit or missing information", story)
        self.assertIn("technical objective -> governing-rule source", story)
        self.assertIn("The actor must do more than read values and report arithmetic", story)
        self.assertIn(
            "story action -> technical operation -> evidence level -> why it is required",
            story,
        )

    def test_complete_story_precedes_brevity(self) -> None:
        skill = " ".join(self.read("SKILL.md").split())
        story = " ".join(self.read("references/story-output-contract.md").split())
        daily = " ".join(self.read("references/daily-briefing-interface.md").split())
        self.assertIn("Complete the story and technical causal spines before compressing", skill)
        self.assertIn("no total word, paragraph, or mechanism paragraph limit", story)
        self.assertIn("transport safety boundary, not to the whole story", story)
        self.assertIn("never pass/fail thresholds", daily)
        self.assertIn("Never truncate", story)

    def test_worked_example_is_not_a_fable_by_scenery(self) -> None:
        contract = " ".join(
            self.read("references/worked-example-contract.md").split()
        )
        self.assertIn("Do not confuse a worked example with a fable", contract)
        self.assertIn("given values -> apply rule -> calculate result -> compare result", contract)
        self.assertIn("does not turn a worked example into a Fable Mode story", contract)

    def test_evidence_authority_and_semantic_conservation_are_fail_closed(self) -> None:
        skill = " ".join(self.read("SKILL.md").split())
        logic = " ".join(
            self.read("references/logic-chain-explanation.md").split()
        )
        story = " ".join(
            self.read("references/story-output-contract.md").split()
        )
        bridge = " ".join(
            self.read("references/bridge-mode-contract.md").split()
        )
        worked = " ".join(
            self.read("references/worked-example-contract.md").split()
        )

        self.assertIn("Authorize every causal edge", skill)
        self.assertIn("Evidence-authority and semantic-conservation gate", story)
        for contract in (skill, logic, story, bridge):
            with self.subTest(contract=contract[:40]):
                self.assertIn("rule or evidence source", contract)
                self.assertIn("conclusion not established", contract)
        self.assertIn("direct measurement or observation", story)
        self.assertIn("source author's mechanistic attribution", story)
        self.assertIn("analogy-only visualization", story)
        self.assertIn("then end the narrative", story)
        self.assertIn("Disclose in the factual debrief", story)
        self.assertIn("allowed state space does not by itself recover", skill)
        self.assertIn("post-selection discards trials", story)
        self.assertIn("component fidelity", story)

        self.assertIn("metric name -> numerator -> denominator", worked)
        self.assertIn("source-backed joint model", worked)
        self.assertIn("conditional-independence assumption", worked)
        self.assertIn("compatible sample space, target event, population", worked)
        self.assertIn("end-to-end task success", worked)

    def test_evidence_regressions_are_property_based_and_complete(self) -> None:
        payload = json.loads(self.read("tests/regression_cases.json"))
        cases = {case["id"]: case for case in payload["cases"]}
        expected = {
            "state-space-is-not-information-recovery",
            "unsupported-mechanism-detail",
            "operation-type-separation",
            "metric-identity-and-composition",
            "claim-strength-and-scope",
            "exit-at-evidence-boundary",
        }
        self.assertTrue(expected.issubset(cases))
        for case_id in expected:
            with self.subTest(case=case_id):
                case = cases[case_id]
                self.assertGreaterEqual(len(case["must_preserve"]), 4)
                self.assertGreaterEqual(len(case["must_avoid"]), 4)
                self.assertNotIn("required_story_terms", case)

    def test_daily_handoff_is_fable_with_legacy_boundary(self) -> None:
        daily = " ".join(self.read("references/daily-briefing-interface.md").split())
        self.assertIn('"version": 3', daily)
        self.assertIn("Versions 1, 2, 3 and 4 retain", daily)
        self.assertIn("Unknown or malformed versions are rejected", daily)
        self.assertNotIn('"explanation_mode":', daily)

    def test_fable_narrative_language_firewall_is_fail_closed(self) -> None:
        skill = " ".join(self.read("SKILL.md").split())
        story = " ".join(
            self.read("references/story-output-contract.md").split()
        )
        firewall = " ".join(
            self.read("references/narrative-language-firewall.md").split()
        )
        daily = " ".join(
            self.read("references/daily-briefing-interface.md").split()
        )

        self.assertIn("three surfaces separate", firewall)
        self.assertIn("narrative denylist", firewall)
        self.assertIn("story-world allowlist", firewall)
        self.assertIn("title and every narrative paragraph form a closed story world", skill)
        self.assertIn("audit the complete narrative", story.lower())
        self.assertIn("factual debrief owns the reveal", story)
        self.assertIn("never enter the sealed narrative", story)
        self.assertIn("Fable Mode", daily)
        self.assertIn("Formal technical teaching belongs after the reveal", skill)

    def test_story_metric_projection_preserves_data_identity(self) -> None:
        firewall = " ".join(
            self.read("references/narrative-language-firewall.md").split()
        )
        worked = " ".join(
            self.read("references/worked-example-contract.md").split()
        )
        daily = " ".join(
            self.read("references/daily-briefing-interface.md").split()
        )

        for text in (firewall, worked):
            with self.subTest(text=text[:40]):
                self.assertIn("underlying data identity", text)
                self.assertIn("approximate normalized", text)
        self.assertIn("not as the source's literal sample size", firewall)
        self.assertIn("hypothetical", self.read("references/everyday-analogy-contract.md"))
        self.assertIn("restores the exact source value", worked)

    def test_language_isolation_regressions_are_complete(self) -> None:
        payload = json.loads(self.read("tests/regression_cases.json"))
        cases = {case["id"]: case for case in payload["cases"]}
        expected = {
            "closed-story-world-language",
            "symbol-free-narrative",
            "narrative-perspective-lock",
            "story-native-metric-projection",
            "rule-origin-without-term-leakage",
            "terminology-restoration",
        }
        self.assertTrue(expected.issubset(cases))
        for case_id in expected:
            with self.subTest(case=case_id):
                case = cases[case_id]
                self.assertEqual(case["mode"], "fable")
                self.assertGreaterEqual(len(case["must_preserve"]), 4)
                self.assertGreaterEqual(len(case["must_avoid"]), 4)
                self.assertNotIn("required_story_terms", case)

    def test_daily_caller_uses_unbounded_paragraph_count(self) -> None:
        caller = " ".join((
            REPO_ROOT / "skills" / "ai-quantum-news-briefing" / "SKILL.md"
        ).read_text(encoding="utf-8").split())
        self.assertIn("at least two causally necessary background paragraphs", caller)
        self.assertIn("No total character, sentence, or paragraph-count cap", caller)
        self.assertNotIn("opening_story` with 2-6", caller)
        self.assertIn("narrative-language-firewall.md", caller)


    def test_all_new_entries_are_fable(self):
        skill = " ".join(self.read("SKILL.md").split())
        self.assertIn("All new invocations use Fable Mode", skill)
        self.assertNotIn("Bridge Mode is the default", skill)
        self.assertNotIn("Fable Mode is opt-in", skill)
        for name in ("bridge-mode-contract", "everyday-analogy-contract"):
            self.assertIn("Historical compatibility reference only", self.read("references/" + name + ".md"))

    def test_semantic_revision_checks_are_explicit(self):
        contract = self.read("references/logic-chain-explanation.md")
        for requirement in ("a basis is not its linear span", '"Not established" is not "impossible"',
                            "parallel, serial, conditional and feedback", "phantom story quantities",
                            "Missing evidence means unreviewed", "An unchanged example"):
            self.assertIn(requirement, contract)

if __name__ == "__main__":
    unittest.main()
