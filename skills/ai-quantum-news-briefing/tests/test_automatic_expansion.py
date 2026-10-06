"""Expansion is recoverable input preparation, never semantic approval."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import orchestrate_daily as o
from academic_sources import family_gate
from daily_delivery_policy import policy_snapshot
from test_dated_source import collect
from test_release_protocol import daily_evidence

DAY="2026-10-02"


def academic(window="2026-10-01"):
    rows=[collect("aps-prx-dated",window=window),collect("crossref-nmi-dated",window=window)]
    return dict(academic_search_version=4,source_coverage_version=2,date_range=window,rows=rows,
                family_gate=family_gate(rows,require_query=True))


def social(day,count=0):
    window=daily_evidence(day)["social_search"]["ai_hot_window"]
    window.update(inside_window_count=count,retrieved_count=count)
    return dict(ai_hot_window=window,sections=[dict(items=[dict(id="S%d"%i,title="Original",published_at=day+"T12:00:00+08:00") for i in range(count)])])


class ExpansionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.news=Path(self.temp.name)/"news"
        p=patch.object(o,"NEWS_ROOT",self.news);p.start();self.addCleanup(p.stop)
        self.paths=o.collection_paths(DAY,self.news)
        o.atomic_json(self.paths["academic"],academic());o.atomic_json(self.paths["social"],social("2026-10-01"))
        o._repair_packet(DAY)

    def fill(self):
        paths=o.expansion_paths(DAY,self.news)
        o.atomic_json(paths["academic"],academic("2026-09-18..2026-10-01"))
        for kind,path in paths.items():
            if kind.startswith("social_"):o.atomic_json(path,social(kind[7:]))

    def test_empty_proven_day_requests_expansion_not_shortfall(self):
        state=o.inspect(DAY)
        self.assertEqual(state["phase"],"expansion_pending")
        self.assertEqual(state["packet_status"],"valid")
        self.assertEqual(state["delivery_policy"],policy_snapshot())

    def test_cached_recovery_is_offline_idempotent_and_unreviewed(self):
        self.fill();before={k:p.read_bytes() for k,p in self.paths.items()}
        with patch.object(o,"inspect_network",side_effect=AssertionError("network")),patch.object(o.subprocess,"run",side_effect=AssertionError("collector")):
            self.assertEqual(o._expand(DAY)["phase"],"expansion_ready")
            path=o.expansion_paths(DAY,self.news)["packet"];data=path.read_bytes()
            self.assertEqual(o._expand(DAY)["phase"],"expansion_ready")
            self.assertEqual(path.read_bytes(),data)
        packet=json.loads(data);self.assertEqual(packet["semantic_review_status"],"not_reviewed")
        self.assertEqual(packet["shortfall_status"],"not_approved")
        self.assertEqual(before,{k:p.read_bytes() for k,p in self.paths.items()})

    def test_future_packet_preserved(self):
        target=o.expansion_paths(DAY,self.news)["packet"];o.atomic_json(target,{"version":99})
        before=target.read_bytes()
        with patch.object(o,"inspect_network",side_effect=AssertionError("network")):
            self.assertEqual(o._expand(DAY)["phase"],"expansion_incompatible")
        self.assertEqual(target.read_bytes(),before)

    def test_source_change_invalidates_expansion_packet(self):
        self.fill();o._expand(DAY)
        p=o.expansion_paths(DAY,self.news)["social_2026-09-30"]
        o.atomic_json(p,social("2026-09-30",1))
        self.assertEqual(o.inspect(DAY)["phase"],"expansion_pending")
        self.assertEqual(o.inspect(DAY)["expansion_packet_status"],"stale")

    def test_only_missing_collector_runs_with_separate_window_checkpoint(self):
        self.fill();p=o.expansion_paths(DAY,self.news)["social_2026-09-30"];p.unlink();calls=[]
        def run(command,**kwargs):
            calls.append(command);o.atomic_json(Path(command[command.index("--output")+1]),social("2026-09-30"))
            return SimpleNamespace(returncode=0)
        with patch.object(o,"with_network_preflight",side_effect=lambda s,**k:{**s,"network_preflight":{"status":"ready"}}),patch.object(o.subprocess,"run",side_effect=run):
            self.assertEqual(o._expand(DAY)["phase"],"expansion_ready")
        self.assertEqual(len(calls),1);self.assertEqual(calls[0][calls[0].index("--coverage-date")+1],"2026-09-30")
        self.assertIn("expansion",calls[0][calls[0].index("--checkpoint")+1])

    def test_write_interruption_retains_existing_packet(self):
        self.fill();o._expand(DAY)
        target=o.expansion_paths(DAY,self.news)["packet"];before=target.read_bytes()
        o.atomic_json(o.expansion_paths(DAY,self.news)["social_2026-09-30"],social("2026-09-30",1))
        original=o.atomic_json
        def fail(path,value):
            if path==target:raise PermissionError("injected")
            return original(path,value)
        with patch.object(o,"atomic_json",side_effect=fail):
            with self.assertRaises(PermissionError):o._expand(DAY)
        self.assertEqual(target.read_bytes(),before)

    def test_policy_change_invalidates_daily_packet(self):
        old=policy_snapshot();new=copy.deepcopy(old);new["sha256"]="b"*64
        with patch.object(o,"policy_snapshot",return_value=new):
            self.assertEqual(o.inspect(DAY)["phase"],"authoring_packet_pending")

    def test_expansion_never_replaces_later_staging_phase(self):
        with patch.object(o,"inspect",return_value={"phase":"staged","date":DAY}),patch.object(o,"inspect_network",side_effect=AssertionError("network")):
            self.assertEqual(o._expand(DAY)["phase"],"staged")

    def test_social_truncation_points_to_daily_and_expansion_sources(self):
        self.fill()
        o.atomic_json(self.paths["social"],social("2026-10-01",101))
        snapshot=o.expansion_snapshot(DAY,self.news)
        packet=o.project_expansion(DAY,self.news,snapshot)
        self.assertEqual(packet["candidate_counts"]["social"]["total"],101)
        self.assertEqual(packet["candidate_counts"]["social"]["emitted"],100)
        self.assertEqual(packet["candidate_counts"]["social"]["truncated"],1)
        self.assertIn("daily_source_inputs",packet["candidate_counts"]["social"]["full_sources"])

    def test_explicit_expansion_preserves_existing_authored_phase(self):
        self.fill()
        with patch.object(o,"inspect",return_value={"phase":"candidate_ready","date":DAY}):
            result=o._expand(DAY)
        self.assertEqual(result["phase"],"candidate_ready")
        self.assertTrue(o.expansion_paths(DAY,self.news)["packet"].is_file())


if __name__=="__main__":unittest.main()
