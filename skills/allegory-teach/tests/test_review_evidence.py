import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from review_evidence import ROUNDS, story_digest, validate_review


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
