import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from plos_source import (ENDPOINT, build_query_url, fetch_plos_row,
                         plos_evidence_failures, MAX_TOTAL_BYTES)


def document(number=1, **changes):
    item = {"id": "10.1371/journal.pone.%07d" % number, "title": "AI study %d" % number,
            "publication_date": "2026-10-01T00:00:00Z", "journal": "PLOS ONE",
            "article_type": "Research Article", "doc_type": "full",
            "abstract": ["First original paragraph.", "Second original paragraph."],
            "subject": ["/Computer and information sciences/Artificial intelligence/Machine learning"]}
    item.update(changes)
    return item


class MockRequests:
    def __init__(self, docs, mutate=None, transport=None):
        self.docs = docs
        self.mutate = mutate
        self.transport = transport
        self.calls = []

    def __call__(self, url, timeout, attempts):
        index = len(self.calls)
        self.calls.append((url, timeout, attempts))
        offset = int(parse_qs(urlsplit(url).query)["start"][0])
        payload = {"response": {"numFound": len(self.docs), "start": offset,
                                 "docs": copy.deepcopy(self.docs[offset:offset + 100])}}
        if self.mutate:
            self.mutate(payload, index)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        evidence = {"query_url": url, "final_url": url, "status_code": 200,
                    "response_hash": hashlib.sha256(body).hexdigest(),
                    "retrieved_at": "2026-10-02T01:00:00+00:00"}
        if self.transport:
            self.transport(evidence, index)
        return evidence, body


class PlosSourceTests(unittest.TestCase):
    source = {"source_id": "plos-ai", "url": ENDPOINT, "maximum_attempts": 2}

    def collect(self, request):
        return fetch_plos_row({"source_id": "plos-ai", "coverage_window": "2026-10-01"},
                              self.source, {"2026-10-01"}, 7, request)

    def assertFailure(self, row, reason=None):
        self.assertEqual(row["result"], "degraded")
        self.assertFalse(row["plos_query_evidence"]["query_complete"])
        self.assertTrue(plos_evidence_failures(row))
        if reason:
            self.assertIn(reason, row["plos_query_evidence"]["failure_reason"])

    def test_query_exact_half_open_shanghai_window_and_scope(self):
        query = parse_qs(urlsplit(build_query_url("2026-10-01")).query)
        self.assertIn("publication_date:[2026-09-30T16:00:00Z TO 2026-10-01T16:00:00Z}", query["q"][0])
        self.assertEqual(query["fq"], ["doc_type:full", 'article_type:"Research Article"'])
        self.assertEqual(query["rows"], ["100"])
        self.assertEqual(query["sort"], ["publication_date asc,id asc"])

    def test_preserves_fields_without_topic_filter_and_replays(self):
        original = document(title="No keyword in title", extra_field="preserved")
        request = MockRequests([original])
        row = self.collect(request)
        self.assertEqual(row["result"], "checked")
        self.assertEqual(plos_evidence_failures(row), [])
        self.assertEqual(len(request.calls), 2)
        self.assertTrue(all(call[1:] == (7, 2) for call in request.calls))
        match = row["matches"][0]
        for key, value in original.items():
            self.assertEqual(match[key], value)
        self.assertEqual(match["description"], "\n".join(original["abstract"]))
        self.assertEqual(match["published_at"], original["publication_date"])
        self.assertEqual(match["date_semantics"], "publisher_index_publication_date")

    def test_zero_is_complete_query_without_publisher_completeness(self):
        request = MockRequests([])
        row = self.collect(request)
        self.assertEqual(row["window_status"], "empty")
        self.assertEqual(row["candidate_count"], 0)
        self.assertEqual(row["coverage_claim"], "discovery_only")
        self.assertFalse(row["window_evidence"]["publisher_day_coverage_complete"])
        self.assertEqual(len(request.calls), 2)
        self.assertEqual(plos_evidence_failures(row), [])

    def test_full_pagination_two_passes(self):
        request = MockRequests([document(index) for index in range(101)])
        row = self.collect(request)
        self.assertEqual(row["candidate_count"], 101)
        self.assertEqual([parse_qs(urlsplit(call[0]).query)["start"][0] for call in request.calls],
                         ["0", "100", "0", "100"])
        self.assertEqual(plos_evidence_failures(row), [])

    def test_half_open_date_boundary_and_timezone(self):
        for stamp in ["2026-10-01T16:00:00Z", "2026-09-30T15:59:59Z", "2026-10-01T00:00:00", "2026-10-01"]:
            with self.subTest(stamp=stamp):
                self.assertFailure(self.collect(MockRequests([document(publication_date=stamp)])))
        row = self.collect(MockRequests([document(publication_date="2026-09-30T16:00:00Z")]))
        self.assertEqual(row["candidate_count"], 1)

    def test_wrong_article_type_doc_type_subject_and_doi(self):
        cases = [{"article_type": "Correction"}, {"doc_type": "figure"},
                 {"subject": ["/Physics/Quantum physics"]}, {"id": "10.1103/invalid"},
                 {"abstract": "not a list"}, {"subject": [5]}, {"title": ""}]
        for changes in cases:
            with self.subTest(changes=changes):
                self.assertFailure(self.collect(MockRequests([document(**changes)])))

    def test_redirect_and_query_scope_rejected(self):
        for key, value in [("final_url", "https://evil.example/search"),
                           ("final_url", "https://api.plos.org/other"),
                           ("query_url", ENDPOINT), ("status_code", 403)]:
            with self.subTest(key=key, value=value):
                self.assertFailure(self.collect(MockRequests([], transport=lambda e, i: e.update({key: value}))))

    def test_failed_body_hash_rejected(self):
        self.assertFailure(self.collect(MockRequests([], transport=lambda e, i: e.update(response_hash="a" * 64))),
                           "plos_response_hash_mismatch")

    def test_total_changes_across_pages(self):
        def mutate(payload, index):
            if index == 1:
                payload["response"]["numFound"] = 102
                payload["response"]["docs"].append(document(101))
        self.assertFailure(self.collect(MockRequests([document(i) for i in range(101)], mutate)), "plos_total_changed")

    def test_short_page_and_bad_offset(self):
        for key, value in [("docs", []), ("start", 1), ("numFound", True), ("numFound", -1)]:
            with self.subTest(key=key):
                self.assertFailure(self.collect(MockRequests([document()], lambda p, i: p["response"].update({key: value}))))

    def test_duplicate_id_and_order(self):
        self.assertFailure(self.collect(MockRequests([document(), document()])), "plos_duplicate_identity")
        self.assertFailure(self.collect(MockRequests([document(2), document(1)])), "plos_sort_order_invalid")

    def test_recheck_catches_changed_content_and_count(self):
        for kind in ("content", "count"):
            def mutate(payload, index):
                if index:
                    if kind == "content":
                        payload["response"]["docs"][0]["abstract"] = ["Changed"]
                    else:
                        payload["response"].update(numFound=0, docs=[])
            with self.subTest(kind=kind):
                self.assertFailure(self.collect(MockRequests([document()], mutate)), "plos_query_changed_during_recheck")

    def test_response_header_metadata_can_change(self):
        row = self.collect(MockRequests([document()], lambda p, i: p.update(responseHeader={"status": 0, "QTime": i})))
        self.assertEqual(plos_evidence_failures(row), [])

    def test_partial_or_inexact_responses_fail_closed(self):
        mutations = [lambda p, i: p.update(responseHeader={"status": 0, "partialResults": True}),
                     lambda p, i: p.update(responseHeader={"status": 1}),
                     lambda p, i: p["response"].update(numFoundExact=False)]
        for mutation in mutations:
            self.assertFailure(self.collect(MockRequests([], mutation)), "plos_partial_response")

    def test_page_and_byte_budget(self):
        self.assertFailure(self.collect(MockRequests([], lambda p, i: p["response"].update(numFound=2001))),
                           "plos_total_invalid_or_limit")
        row = self.collect(MockRequests([document(abstract=["x" * (MAX_TOTAL_BYTES // 2)])]))
        self.assertFailure(row, "plos_response_byte_limit")

    def test_request_exception_retains_failure(self):
        def timeout(*args):
            raise TimeoutError("collection_deadline")
        row = self.collect(timeout)
        self.assertFailure(row, "collection_deadline")

    def test_missing_second_pass_cannot_be_promoted(self):
        row = self.collect(MockRequests([]))
        del row["plos_query_evidence"]["pages"][0]["recheck"]
        self.assertTrue(plos_evidence_failures(row))

    def test_forged_empty_and_mutated_projection_rejected(self):
        row = self.collect(MockRequests([document()]))
        row.update(matches=[], candidate_count=0, window_status="empty")
        self.assertIn("plos_candidates_mismatch", plos_evidence_failures(row))
        row = self.collect(MockRequests([document()]))
        row["matches"][0]["description"] = "Invented"
        self.assertIn("plos_candidates_mismatch", plos_evidence_failures(row))

    def test_raw_response_and_transport_tampering_rejected(self):
        for part in ("primary", "recheck"):
            row = self.collect(MockRequests([]))
            row["plos_query_evidence"]["pages"][0][part]["raw_response_utf8"] += " "
            self.assertIn("plos_response_hash_mismatch", plos_evidence_failures(row))

    def test_forged_completeness_rejected(self):
        row = self.collect(MockRequests([]))
        row["window_evidence"]["publisher_day_coverage_complete"] = True
        self.assertIn("plos_window_evidence_mismatch", plos_evidence_failures(row))

    def test_date_window_and_target_must_match(self):
        row = fetch_plos_row({"coverage_window": "2026-10-01"}, self.source, {"2026-10-02"}, 7, MockRequests([]))
        self.assertFailure(row, "plos_target_days_mismatch")

    def test_multi_day_window(self):
        request = MockRequests([document(publication_date="2026-09-30T00:00:00Z"), document(2)])
        row = fetch_plos_row({"coverage_window": "2026-09-30..2026-10-01"}, self.source,
                             {"2026-09-30", "2026-10-01"}, 7, request)
        self.assertEqual(row["candidate_count"], 2)
        self.assertEqual(plos_evidence_failures(row), [])

    def test_non_json_failure_retains_diagnostic_body(self):
        def request(url, timeout, attempts):
            body = b"<html>maintenance</html>"
            return {"query_url": url, "final_url": url, "status_code": 200,
                    "response_hash": hashlib.sha256(body).hexdigest(),
                    "retrieved_at": "2026-10-02T01:00:00+00:00"}, body
        row = self.collect(request)
        self.assertFailure(row)
        self.assertEqual(row["retrieval_status"], "success")
        self.assertEqual(row["parse_status"], "error")
        self.assertIn("maintenance", row["plos_query_evidence"]["failed_response"]["raw_response_utf8_prefix"])
        self.assertIn("maintenance", row["plos_query_evidence"]["pages"][0]["primary"]["raw_response_utf8"])

    def test_http_failure_separated_from_parse_failure(self):
        row = self.collect(MockRequests([], transport=lambda e, i: e.update(status_code=403)))
        self.assertFailure(row, "plos_http_status_invalid")
        self.assertEqual(row["retrieval_status"], "blocked")
        self.assertEqual(row["parse_status"], "not_attempted")
        self.assertEqual(row["plos_query_evidence"]["failed_response"]["transport"]["status_code"], 403)

    def test_boolean_summary_values_cannot_impersonate_integers(self):
        for key in ("version", "num_found", "response_bytes"):
            row = self.collect(MockRequests([document()]))
            row["plos_query_evidence"][key] = True
            self.assertTrue(plos_evidence_failures(row))
        row = self.collect(MockRequests([]))
        row["window_evidence"]["publisher_day_coverage_complete"] = 0
        self.assertTrue(plos_evidence_failures(row))
        row = self.collect(MockRequests([]))
        row["quarantined_count"] = False
        self.assertTrue(plos_evidence_failures(row))

    def test_numeric_boolean_metadata_is_invalid(self):
        for mutate in [lambda p, i: p.update(responseHeader={"status": 0, "partialResults": 0}),
                       lambda p, i: p["response"].update(numFoundExact=1)]:
            self.assertFailure(self.collect(MockRequests([], mutate)), "plos_partial_response")

    def test_matching_response_params_accept_scalar_singleton_and_fq_order(self):
        def mutate(payload, index):
            params = parse_qs(urlsplit(build_query_url("2026-10-01")).query)
            if index:
                params = {key: values if key == "fq" else values[0] for key, values in params.items()}
                params["fq"].reverse()
            payload["responseHeader"] = {"status": 0, "params": params}
        row = self.collect(MockRequests([], mutate))
        self.assertEqual(row["result"], "checked")
        self.assertEqual(plos_evidence_failures(row), [])

    def test_response_params_conflicting_empty_query_is_not_healthy(self):
        def mutate(payload, index):
            payload["responseHeader"] = {"status": 0, "params": {
                "q": "id:other", "fq": "article_type:Correction", "rows": "0"}}
        self.assertFailure(self.collect(MockRequests([], mutate)), "plos_response_params_scope_mismatch")

    def test_response_params_reject_each_missing_conflicting_or_duplicate_field(self):
        for key in ("q", "fq", "fl", "wt", "start", "rows", "sort"):
            for kind in ("missing", "conflicting", "duplicate", "numeric"):
                def mutate(payload, index):
                    params = parse_qs(urlsplit(build_query_url("2026-10-01")).query)
                    if kind == "missing":
                        del params[key]
                    elif kind == "conflicting":
                        params[key] = ["incorrect"]
                    elif kind == "duplicate":
                        params[key] += params[key]
                    else:
                        params[key] = 0
                    payload["responseHeader"] = {"status": 0, "params": params}
                with self.subTest(key=key, kind=kind):
                    self.assertFailure(self.collect(MockRequests([], mutate)), "plos_response_params_")

    def test_response_params_reject_undeclared_query_options(self):
        def mutate(payload, index):
            params = parse_qs(urlsplit(build_query_url("2026-10-01")).query)
            params["defType"] = "edismax"
            payload["responseHeader"] = {"status": 0, "params": params}
        self.assertFailure(self.collect(MockRequests([], mutate)), "plos_response_params_scope_mismatch")

    def test_recheck_response_params_independently_checked(self):
        def mutate(payload, index):
            if index:
                params = parse_qs(urlsplit(build_query_url("2026-10-01")).query)
                params["q"] = "id:other"
                payload["responseHeader"] = {"status": 0, "params": params}
        self.assertFailure(self.collect(MockRequests([], mutate)), "plos_response_params_scope_mismatch")

    def test_cached_replay_rejects_conflicting_params_even_with_updated_hash(self):
        row = self.collect(MockRequests([]))
        page = row["plos_query_evidence"]["pages"][0]["recheck"]
        payload = json.loads(page["raw_response_utf8"])
        params = parse_qs(urlsplit(build_query_url("2026-10-01")).query)
        params["q"] = "id:other"
        payload["responseHeader"] = {"status": 0, "params": params}
        raw = json.dumps(payload, ensure_ascii=False)
        row["plos_query_evidence"]["response_bytes"] += len(raw.encode("utf-8")) - len(page["raw_response_utf8"].encode("utf-8"))
        page["raw_response_utf8"] = raw
        page["transport"]["response_hash"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        self.assertEqual(plos_evidence_failures(row), ["plos_response_params_scope_mismatch"])


if __name__ == "__main__":
    unittest.main()
