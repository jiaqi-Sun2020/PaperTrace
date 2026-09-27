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
