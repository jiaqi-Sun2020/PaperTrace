"""Cross-stage mutation and interruption attacks on source optimization."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import academic_venue_sweep as s
import orchestrate_daily as o
from academic_sources import load_registry,row_is_healthy
from test_dated_source import collect
from test_automatic_expansion import academic,social,DAY
import test_feed_window_diagnostics as feed_tests


class OptimizationAdversarialTests(unittest.TestCase):
    def test_feed_date_bracket_cannot_prove_empty(self):
        row=feed_tests.FeedWindowDiagnosticsTests().collect(["2026-10-01","2026-10-03"])
        self.assertFalse(row_is_healthy(row));self.assertEqual(row["window_status"],"unknown")

    def test_one_source_registry_change_recollects_only_that_source(self):
        plan=s.build_plan_v4(["quantum"],"2026-10-01")
        plan["rows"]=[r for r in plan["rows"] if r["source_id"] in {"aps-prx-dated","crossref-nmi-dated"}]
        calls=[]
        def fetch(row,*args):calls.append(row["source_id"]);return collect(row["source_id"])
        with tempfile.TemporaryDirectory() as d,patch.object(s,"_fetch_v4_row",side_effect=fetch):
            checkpoint=Path(d)/"cache.json"
            s.fetch_evidence_v4(copy.deepcopy(plan),checkpoint=checkpoint);calls.clear()
            registry=load_registry();next(r for r in registry["sources"] if r["source_id"]=="aps-prx-dated")["label"]="Updated label"
            with patch.object(s,"load_registry",return_value=registry):s.fetch_evidence_v4(copy.deepcopy(plan),checkpoint=checkpoint)
            self.assertEqual(calls,["aps-prx-dated"])

    def prepare(self,news):
        paths=o.collection_paths(DAY,news)
        o.atomic_json(paths["academic"],academic());o.atomic_json(paths["social"],social("2026-10-01",7))
        o._repair_packet(DAY)
        return paths

    def test_late_arrival_annex_preserves_dates_and_remains_unreviewed(self):
        with tempfile.TemporaryDirectory() as d,patch.object(o,"NEWS_ROOT",Path(d)/"news"):
            paths=self.prepare(o.NEWS_ROOT);source,target,window=o.late_arrival_paths(DAY,o.NEWS_ROOT)
            o.atomic_json(source,academic(window))
            with patch.object(o,"inspect",return_value={"phase":"late_arrival_pending","date":DAY}),patch.object(o,"inspect_network",side_effect=AssertionError("network")):
                o._recheck_late_arrivals(DAY)
            packet=o.load_json(target);self.assertEqual(packet["query_window"],"2026-09-29..2026-10-01")
            self.assertEqual(packet["semantic_review_status"],"not_reviewed")
            self.assertEqual(o.load_json(paths["academic"])["date_range"],"2026-10-01")

    def test_attempt_started_is_durable_before_network_denial(self):
        with tempfile.TemporaryDirectory() as d,patch.object(o,"NEWS_ROOT",Path(d)/"news"),patch.object(o,"with_network_preflight",side_effect=lambda state,**kwargs:{**state,"phase":"environment_blocked","network_preflight":{"status":"blocked"}}):
            state=o._collect(DAY)
            self.assertEqual(state["phase"],"environment_blocked")
            self.assertEqual(len(list((o.NEWS_ROOT/"_automation/collection_attempts"/DAY).glob("*.started.json"))),1)

    def test_source_backup_is_content_addressed_and_not_duplicated(self):
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/"source.json";target.write_text('{"old":true}',encoding='utf-8')
            o._backup_source(target);o._backup_source(target)
            saved=list((target.parent/".source_backups").glob("*.json"));self.assertEqual(len(saved),1)
            self.assertEqual(saved[0].read_bytes(),target.read_bytes())

    def test_record_retains_both_attempts_and_latest_order(self):
        with tempfile.TemporaryDirectory() as d:
            news=Path(d)/"news"
            for started,observed in [("2026-10-02T02:00:00+00:00","2026-10-02T02:01:00+00:00"),("2026-10-02T01:00:00+00:00","2026-10-02T03:00:00+00:00")]:
                state={"date":DAY,"phase":"collection_pending","collection_attempt":{"started_at":started,"observed_at":observed,"phase":"collection_pending"}}
                o._record(state,True,news_root=news)
            self.assertEqual(len(list((news/"_automation/collection_attempts"/DAY).glob("*.json"))),2)
            current=o.load_json(news/"_automation"/("orchestration_state_"+DAY+".json"))
            self.assertEqual(current["last_collection_attempt"]["started_at"],"2026-10-02T02:00:00+00:00")

    def test_new_collection_contract_cannot_be_downgraded_by_unknown_version(self):
        with tempfile.TemporaryDirectory() as d,patch.object(o,"NEWS_ROOT",Path(d)/"news"):
            p=o.collection_paths(DAY,o.NEWS_ROOT)["academic"];raw=academic();raw["source_coverage_version"]=True;o.atomic_json(p,raw)
            with self.assertRaises(o.CollectionError):o.read_source(p,"academic",DAY)


if __name__=="__main__":unittest.main()
