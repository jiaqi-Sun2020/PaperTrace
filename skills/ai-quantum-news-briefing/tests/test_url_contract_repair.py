"""Lossless reference URLs with explicitly versioned historical identity."""
from copy import deepcopy
from datetime import date
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import briefing_contract as contract
import news_delta as delta
from source_capture import make_capture, validate_capture
from test_daily_pipeline import ranking_fixture


class URLContractRepairTests(unittest.TestCase):
    def test_resource_components_are_preserved_and_distinct(self):
        urls = ["https://Example.org/a", "https://Example.org/a/", "https://Example.org/a//b",
                "https://Example.org/a?article=1", "https://Example.org/a?article=2",
                "https://Example.org/a#one", "https://Example.org/a#two", "https://Example.org/a?"]
        identities = []
        for url in urls:
            self.assertEqual(contract.source_reference_url(url), url)
            identity = contract.source_identity_url(url)
            self.assertEqual(contract.source_identity_url(identity), identity)
            identities.append(identity)
        self.assertEqual(len(set(identities)), len(urls))

    def test_legacy_meaning_is_unchanged(self):
        url = "https://Example.org/a//b/?q=1#anchor"
        self.assertEqual(contract.canonical_url(url), "https://example.org/a/b")
        self.assertEqual(contract.reference_url_for_item({"source_url": url}), "https://example.org/a/b")
        item = {"source_url": url, "source_url_contract_version": 2}
        self.assertEqual(contract.reference_url_for_item(item), url)
        self.assertEqual(contract.identity_url_for_item(item), "https://example.org/a//b/?q=1#anchor")

    def test_unsafe_and_credential_urls_rejected_without_echoing_secret(self):
        for url in ("http://example.org/a", "https://user:secret@example.org/a", "https://example.org:8080/a",
                    "https://example.org/a?%74oken=secret", "https://example.org/a?api-key=secret",
                    "https://example.org/a\n", "https://example.org/" + "a" * 1600):
            with self.subTest(url=url), self.assertRaises(ValueError) as result:
                contract.source_reference_url(url)
            self.assertNotIn("secret", str(result.exception))

    def test_future_and_ambiguous_versions_fail_closed(self):
        for version in (3, "2", 2.0, True, None):
            with self.subTest(version=version), self.assertRaises(ValueError):
                contract.reference_url_for_item({"source_url_contract_version": version, "source_url": "https://example.org/"})

    def test_generated_ids_do_not_collide_on_query_or_long_path(self):
        urls = ["https://example.org/" + "long/" * 80 + "?id=" + str(i) for i in range(3)]
        ids = [contract.story_id_for_item({"source_url": url, "source_url_contract_version": 2}) for url in urls]
        self.assertEqual(len(set(ids)), 3)
        self.assertEqual(contract.story_id_for_item({"story_id": "stable-old-story", "source_url_contract_version": 2}), "stable-old-story")

    def test_normalization_and_delta_preserve_reference_and_capture(self):
        raw, _ = ranking_fixture()
        raw["source_url_contract_version"] = 2
        for section in raw["sections"]:
            for item in section["items"]:
                item["source_url"] += "/?article=1#evidence"
                item["source_capture"] = make_capture(item, item["source_url"], item["source_url"].split("#")[0], 200,
                    ("<p>" + item["source_excerpt"] + "</p>").encode("utf-8"), "2026-07-10T01:00:00Z")
        original = deepcopy(raw)
        normalized = contract.normalize_briefing_config(raw)
        transformed, _, records = delta.transform_config(normalized, [], date(2026, 7, 10), 30, "full")
        again = contract.normalize_briefing_config(transformed)
        by_story = {item["story_id"]: item for section in original["sections"] for item in section["items"]}
        for section in again["sections"]:
            for item in section["items"]:
                before = by_story[item["story_id"]]
                self.assertEqual(item["source_url"], before["source_url"])
                self.assertEqual(item["source_capture"], before["source_capture"])
                self.assertEqual(validate_capture(item, item["source_capture"]), [])
        for record in records:
            self.assertEqual(record["source_url"], by_story[record["story_id"]]["source_url"])
            self.assertEqual(record["source_url_contract_version"], 2)
        self.assertEqual(raw, original)

    def test_query_difference_is_not_a_prior_url_match(self):
        item = {"story_id": "one", "source_url": "https://example.org/a?id=1", "source_url_contract_version": 2}
        prior = {"story_id": "two", "source_url": "https://example.org/a?id=2", "source_url_contract_version": 2}
        self.assertIsNone(delta.prior_for(item, [prior]))
