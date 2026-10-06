"""Feed-window diagnostics must not manufacture a covered empty day."""
import hashlib
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import academic_venue_sweep as sweep
from academic_sources import sources_by_id, row_is_healthy


class FeedWindowDiagnosticsTests(unittest.TestCase):
    def collect(self, days, source_id="nature-machine-learning"):
        source = sources_by_id()[source_id]
        row = next(r for r in sweep.build_plan_v4(["machine learning"], "2026-10-02")["rows"]
                   if r["source_id"] == source_id)
        if source_id == "openreview":
            body = json.dumps({"notes": []}).encode()
        else:
            body = ("<rss><channel>" + "".join(
                '<item><title>machine learning</title><link>https://www.nature.com/articles/test</link>'
                '<pubDate>' + d + 'T00:00:00Z</pubDate></item>' for d in days) + "</channel></rss>").encode()
        evidence = dict(query_url=source["url"], final_url=source["url"], status_code=200,
                        response_hash=hashlib.sha256(body).hexdigest(), retrieved_at="2026-10-02T16:30:00Z")
        with patch.object(sweep, "_request_source_with_retry", return_value=(evidence, body)):
            return sweep._fetch_v4_row(row, source, ["machine learning"], {"2026-10-02"}, 1)

    def test_newer_target_is_unproven_not_an_empty_day(self):
        row = self.collect(["2026-09-30", "2026-10-01"])
        self.assertFalse(row_is_healthy(row))
        self.assertEqual(row["window_evidence"]["classification_basis"], "target_after_feed")
        self.assertEqual(row["window_evidence"]["observed_latest_date"], "2026-10-01")
        self.assertFalse(row["window_evidence"]["publisher_day_coverage_complete"])

    def test_older_target_has_a_distinct_diagnostic(self):
        row = self.collect(["2026-10-03", "2026-10-04"])
        self.assertFalse(row_is_healthy(row))
        self.assertEqual(row["window_evidence"]["classification_basis"], "target_before_feed")

    def test_matched_feed_preserves_candidates(self):
        row = self.collect(["2026-10-01", "2026-10-02"])
        self.assertTrue(row_is_healthy(row))
        self.assertEqual(row["candidate_count"], 1)
        self.assertEqual(row["window_evidence"]["classification_basis"], "dated_items_in_window")

    def test_unscoped_empty_api_is_not_healthy(self):
        row = self.collect([], "openreview")
        self.assertFalse(row_is_healthy(row))
        self.assertEqual(row["window_status"], "unknown")
        self.assertEqual(row["window_evidence"]["classification_basis"], "no_dated_items")


if __name__ == "__main__":
    unittest.main()
