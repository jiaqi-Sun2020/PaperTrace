import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from review_evidence import ROUNDS, ROUND_MATERIALS, TASK_CARD_KEYS, story_digest, validate_review


class ReviewEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.story = {"paragraphs": ["One supported action."], "worked_example": {"result": "bounded result"}}
        self.review = {"story_sha256": story_digest(self.story), "rounds": [
            {"id": name, "judgment": "pass", "reviewed_text": "One supported action.",
             "reason": "The action matches the stated rule.", "source_or_rule": "declared protocol",
             "limitation": "This checks provenance, not semantic truth."} for name in sorted(ROUNDS)]}

    def test_complete_review(self):
        self.assertEqual(validate_review(self.story, self.review), [])

    def test_changed_story_invalidates_unchanged_example_review(self):
        self.story["paragraphs"] = ["A different case."]
        self.assertTrue(validate_review(self.story, self.review))

    def test_changed_example_invalidates_review(self):
        self.story["worked_example"]["result"] = "stronger claim"
        self.assertTrue(validate_review(self.story, self.review))

    def test_phantom_quote_and_missing_evidence_fail(self):
        for key, value in (("reviewed_text", "every hundred objects"), ("source_or_rule", ""),
                           ("judgment", "unreviewed")):
            review = copy.deepcopy(self.review)
            review["rounds"][0][key] = value
            self.assertTrue(validate_review(self.story, review))

    def test_missing_round_fails(self):
        self.review["rounds"].pop()
        self.assertTrue(validate_review(self.story, self.review))

    def test_malformed_review_reports_failure_instead_of_crashing(self):
        self.review["rounds"][0]["reviewed_text"] = 42
        self.assertTrue(any("missing reviewed_text" in failure for failure in validate_review(self.story, self.review)))

    def test_new_review_requires_task_card_method_and_blind_first_round(self):
        self.story.update(title="A choice with a cost", concept_definition="The formal answer.")
        review = copy.deepcopy(self.review)
        review["story_sha256"] = story_digest(self.story)
        review["review_protocol_version"] = 2
        review["review_method"] = "self"
        review["task_card"] = {key: "A concrete, source-grounded decision." for key in TASK_CARD_KEYS}
        for row in review["rounds"]:
            row["materials_seen"] = sorted(ROUND_MATERIALS[row["id"]])
        self.assertEqual(validate_review(self.story, review), [])

        missing_card = copy.deepcopy(review)
        del missing_card["task_card"]["teaching_question"]
        self.assertIn("task card missing teaching_question", validate_review(self.story, missing_card))

        unblinded = copy.deepcopy(review)
        first = next(row for row in unblinded["rounds"] if row["id"] == "story-completeness")
        first["reviewed_text"] = "The formal answer."
        first["materials_seen"] = ["title", "paragraphs", "concept_definition"]
        failures = validate_review(self.story, unblinded)
        self.assertTrue(any("review materials" in failure for failure in failures))
        self.assertTrue(any("quoted text is absent" in failure for failure in failures))

        mislabeled = copy.deepcopy(review)
        mislabeled["review_method"] = "blind independent certification"
        self.assertTrue(any("review method" in failure for failure in validate_review(self.story, mislabeled)))

    def test_v3_requires_a_literal_trace_source_mapping_and_example_alignment(self):
        self.story = {
            "title": "A bounded choice", "paragraphs": ["A fourth item arrives; the four labels stop at three."],
            "worked_example": {"question": "What is recorded?", "observable": "The stored count.",
                               "steps": [{"action": "Compare four with the largest label."}],
                               "result": "The chosen saturation rule records three."},
        }
        quote = self.story["paragraphs"][0]
        review = copy.deepcopy(self.review)
        review.update(story_sha256=story_digest(self.story), review_protocol_version=3,
                      review_method="self", task_card={key: "A bounded decision." for key in TASK_CARD_KEYS})
        for row in review["rounds"]:
            row.update(materials_seen=sorted(ROUND_MATERIALS[row["id"]]), reviewed_text=quote, unresolved=[])
            if row["id"] == "story-completeness":
                row["literal_trace"] = [{"story_quote": quote, "tracked_object": "item count",
                    "kind": "representation_label", "before": "three items; label three",
                    "trigger": "a fourth item arrives", "operation": "look for label four",
                    "after": "four items, no matching label", "rule_origin": "only four labels exist"}]
                row["counterfactual"] = {"changed_condition": "add a fifth label",
                    "predicted_result": "four can be recorded", "reason": "the missing label now exists"}
            elif row["id"] == "semantic-and-source":
                row["technical_edges"] = [{"story_quote": quote,
                    "technical_operation": "finite encoding excludes the next count",
                    "source_anchor": "source statement on finite representation",
                    "claim_class": "teaching_assumption",
                    "scope_and_nonconclusion": "saturation is optional, not caused by capacity alone"}]
            else:
                row["example_alignment"] = {"question": self.story["worked_example"]["question"],
                    "observable": self.story["worked_example"]["observable"],
                    "step_quote": self.story["worked_example"]["steps"][0]["action"],
                    "result": self.story["worked_example"]["result"],
                    "consistency_reason": "The example states its chosen overflow rule."}
        self.assertEqual(validate_review(self.story, review), [])
        for mutate, expected in (
            (lambda value: value["story-completeness"].pop("literal_trace"), "literal_trace"),
            (lambda value: value["story-completeness"]["literal_trace"][0].update(kind="count-or-height"), "invalid kind"),
            (lambda value: value["story-completeness"]["literal_trace"][0].update(kind=[]), "invalid kind"),
            (lambda value: value["story-completeness"]["literal_trace"][0].update(story_quote="phantom event"), "quote is absent"),
            (lambda value: value["semantic-and-source"].pop("technical_edges"), "technical_edges"),
            (lambda value: value["semantic-and-source"]["technical_edges"][0].update(claim_class={}), "invalid claim_class"),
            (lambda value: value["cross-surface-and-display"]["example_alignment"].update(observable="A different result."), "observable differs"),
            (lambda value: value["story-completeness"].update(unresolved=["the event has no rule"]), "unresolved findings"),
        ):
            with self.subTest(expected=expected):
                damaged = copy.deepcopy(review)
                mutate({row["id"]: row for row in damaged["rounds"]})
                self.assertTrue(any(expected in failure for failure in validate_review(self.story, damaged)))
