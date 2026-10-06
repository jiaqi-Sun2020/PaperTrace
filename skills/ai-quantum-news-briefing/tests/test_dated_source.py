"""Offline adversarial proofs for bounded calendar-date source queries."""
import copy
import hashlib
import json
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import dated_source as dated
import academic_venue_sweep as sweep
from academic_sources import sources_by_id, row_is_healthy, family_gate
from audit_briefing_config import academic_search_venues


def doc(source, day="2026-10-01", number=1):
    if source["adapter"] == "aps_harvest":
        return dict(id="10.1103/test%d" % number, type="article", title={"value": "Quantum test"},
                    journal={"id": source["journal_code"]}, date=day, abstract={"value": "Original abstract"})
    return {"DOI": source["doi_prefix"] + "/test%d" % number, "type": "journal-article", "title": ["Original paper"],
            "ISSN": [source["issn"]], "published-online": {"date-parts": [[int(p) for p in day.split("-")]]},
            "abstract": "Original abstract"}


def collect(source_id="crossref-quantum-dated", docs=None, window="2026-10-01", mutation=None):
    source = sources_by_id()[source_id]
    row = next(r for r in sweep.build_plan_v4(["quantum"], window)["rows"] if r["source_id"] == source_id)
    docs = [] if docs is None else docs
    counter = [0]
    def request(url, *_):
        counter[0] += 1
        cursor = parse_qs(urlsplit(url).query).get("cursor", ["*"])[0]
        page = 0 if cursor == "*" else int(cursor)
        data = docs[page*dated.PAGE_SIZE:(page+1)*dated.PAGE_SIZE]
        payload = {"data": data} if source["adapter"] == "aps_harvest" else {
            "status": "ok", "message-type": "work-list", "message": {"items": data, "total-results": len(docs),
                                                                         "next-cursor": str(page+1)}}
        if mutation:
            mutation(payload, counter[0])
        body = json.dumps(payload, ensure_ascii=False).encode()
        stamp = (date.fromisoformat(window[-10:]) + timedelta(days=1)).isoformat() + "T01:00:00Z"
        e = dict(query_url=url, final_url=url, status_code=200, response_hash=hashlib.sha256(body).hexdigest(), retrieved_at=stamp)
        return e, body
    first, last = dated.window_days(window)
    days = {(first + timedelta(days=i)).isoformat() for i in range((last-first).days+1)}
    return dated.fetch_dated_row(row, source, days, 1, request)


class DatedSourceTests(unittest.TestCase):
    def test_proven_empty_for_each_provider(self):
        for source_id in ("aps-prx-dated", "crossref-quantum-dated", "crossref-nmi-dated"):
            with self.subTest(source=source_id):
                r = collect(source_id)
                self.assertTrue(row_is_healthy(r))
                self.assertEqual(r["window_status"], "empty")
                self.assertFalse(r["window_evidence"]["publisher_day_coverage_complete"])

    def test_positive_retains_raw_record_and_calendar_precision(self):
        for source_id in ("aps-prx-dated", "crossref-quantum-dated"):
            s = sources_by_id()[source_id]; original = doc(s)
            r = collect(source_id, [original])
            self.assertTrue(row_is_healthy(r))
            self.assertEqual(r["matches"][0]["source_record"], original)
            self.assertEqual(r["matches"][0]["published_at"], "2026-10-01")
            self.assertEqual(r["matches"][0]["date_precision"], "day")

    def test_complete_multipage(self):
        source = sources_by_id()["crossref-quantum-dated"]
        r = collect(docs=[doc(source, number=i) for i in range(101)])
        self.assertTrue(row_is_healthy(r))
        self.assertEqual(len(r["dated_query_evidence"]["pages"]), 2)
        self.assertEqual(r["candidate_count"], 101)

    def test_duplicate_wrong_journal_type_date_and_identity_fail(self):
        source = sources_by_id()["crossref-quantum-dated"]
        cases = [[doc(source), doc(source)], [{**doc(source), "ISSN": ["bad"]}],
                 [{**doc(source), "type": "posted-content"}], [doc(source, "2026-10-02")],
                 [{**doc(source), "DOI": "10.1103/wrong"}]]
        for records in cases:
            self.assertFalse(row_is_healthy(collect(docs=records)))

    def test_raw_hash_query_summary_projection_and_scope_tampering(self):
        good = collect()
        changes = [lambda r: r["evidence"].update(status_code=True),
                   lambda r: r["dated_query_evidence"].update(query_complete=True, raw_count=1),
                   lambda r: r["dated_query_evidence"].update(scope_id="other"),
                   lambda r: r["dated_query_evidence"]["pages"][0]["primary"].update(raw_response_utf8="{}"),
                   lambda r: r.update(matches=[{}], candidate_count=1),
                   lambda r: r["window_evidence"].update(publisher_day_coverage_complete=True)]
        for mutate in changes:
            r=copy.deepcopy(good);mutate(r);self.assertFalse(row_is_healthy(r))

    def test_second_read_change_never_passes(self):
        def mutate(p, call):
            if call == 2:
                p["message"]["total-results"] = 1
        self.assertFalse(row_is_healthy(collect(mutation=mutate)))

    def test_precision_quarantine_is_not_reported_as_zero_query(self):
        s = sources_by_id()["crossref-quantum-dated"]
        raw = doc(s);raw["published-online"]["date-parts"] = [[2026,10]]
        r=collect(docs=[raw]);self.assertTrue(row_is_healthy(r))
        self.assertEqual(r["candidate_count"],0);self.assertEqual(r["quarantined_count"],1)
        self.assertEqual(r["window_status"],"matched")
        self.assertEqual(r["dated_query_evidence"]["raw_count"],1)

    def test_date_window_is_exact_calendar_query_not_fake_instant(self):
        s=sources_by_id()["aps-prx-dated"]
        p=parse_qs(urlsplit(dated.query_url(s,"2026-10-01..2026-10-04")).query)
        self.assertEqual(p["from"],["2026-10-01"]);self.assertEqual(p["until"],["2026-10-04"])
        self.assertEqual(p["date"],["published"]);self.assertEqual(p["set"],["openaccess"])

    def test_new_gate_accepts_queries_and_rejects_feed_flag(self):
        rows=[collect("aps-prx-dated"),collect("crossref-nmi-dated")]
        gate=family_gate(rows, require_query=True)
        self.assertEqual(gate["status"],"pass")
        ledger=dict(academic_search_version=4,source_coverage_version=2,date_range="2026-10-01",rows=rows,family_gate=gate)
        self.assertEqual(academic_search_venues({"academic_search":ledger},coverage_contract_version=3)[3],[])
        from evidence_fixtures import evidenced_row
        fake=evidenced_row(dict(source_id="aps-pra",result="checked",retrieval_status="success",parse_status="success",window_status="matched"))
        self.assertEqual(family_gate([fake,rows[1]],require_query=True)["missing_families"],["quantum_publisher"])

    def test_future_contract_rejected(self):
        ledger=dict(academic_search_version=4,source_coverage_version=99,date_range="2026-10-01",rows=[collect()])
        self.assertTrue(academic_search_venues({"academic_search":ledger},coverage_contract_version=3)[3])


if __name__ == "__main__":
    unittest.main()
