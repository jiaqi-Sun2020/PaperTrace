#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused regression tests for adaptive teaching decisions and safe handoffs."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
ADAPTIVE = ROOT / "skills" / "adaptive-teach" / "scripts" / "adaptive_teach.py"
READER = ROOT / "skills" / "reader-learner" / "scripts"
sys.path.insert(0, str(ADAPTIVE.parent)); sys.path.insert(0, str(READER))
from adaptive_teach import build_feedback, select  # noqa: E402
from profile_v2 import empty_profile_v2, save_json, load_json  # noqa: E402


def concept(concept_id: str, label: str, status: str, **extra: object) -> dict:
    value = {"concept_id": concept_id, "label": label, "status": status, "source_ids": ["src-test"], "event_ids": [], "stats": {}, "last_seen_at": ""}
    value.update(extra)
    return value


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="adaptive_teach_", dir=ROOT) as raw:
        base = Path(raw); profile_path, workspace = base / "profile.json", base / "workspace"
        profile = empty_profile_v2()
        profile["concepts"] = {
            "unknown-target": concept("unknown-target", "Unknown target", "unknown"),
            "exposure-only": concept("exposure-only", "Exposure only", "unrated"),
            "stuck": concept("stuck", "Repeated misconception", "learning"),
            "mastered": concept("mastered", "Mastered recall", "mastered"),
            "advanced": concept("advanced", "Advanced target", "unknown"),
            "blocker": concept("blocker", "Minimal blocker", "learning"),
        }
        profile["events"] = [
            {"event_id": "evt-1", "concept_id": "stuck", "status": "learning", "user_question": "same misconception"},
            {"event_id": "evt-2", "concept_id": "stuck", "status": "learning", "user_question": "same misconception again"},
        ]
        profile["sources"] = {"src-test": {"source_id": "src-test", "source_kind": "fixture", "title": "Fixture", "path": "", "url": "", "date_range": "", "event_ids": []}}
        profile["review_queue"] = [{"concept_id": "mastered", "due_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), "last_event_id": "evt-old"}]
        save_json(profile_path, profile)
        workspace.mkdir(); (workspace / "teaching-settings.json").write_text(json.dumps({"mission_relevance": {"unknown-target": 50, "advanced": 80}, "prerequisites": {"advanced": ["blocker"]}}, ensure_ascii=False), encoding="utf-8")
        (workspace / "TEACHING-MISSION.md").write_text("# Teaching Mission\n- solve a research bottleneck\n", encoding="utf-8")
        settings = json.loads((workspace / "teaching-settings.json").read_text(encoding="utf-8"))

        ranking_a = select(profile, settings, datetime(2026, 7, 14, tzinfo=timezone.utc))
        ranking_b = select(profile, settings, datetime(2026, 7, 14, tzinfo=timezone.utc))
        if ranking_a != ranking_b: raise AssertionError("ranking was not deterministic")
        if select(profile, settings, datetime.now(timezone.utc), "exposure-only")["mode"] != "diagnose": raise AssertionError("exposure-only was not diagnostic")
        if select(profile, settings, datetime.now(timezone.utc), "mastered")["mode"] != "review": raise AssertionError("due mastered item was not review")
        prerequisite = select(profile, settings, datetime.now(timezone.utc), "advanced")
        if prerequisite["selected_concept_id"] != "blocker" or prerequisite["mode"] != "prerequisite": raise AssertionError("minimal blocker was not selected")
        if "repeated_confusion" not in select(profile, settings, datetime.now(timezone.utc), "stuck")["reason_codes"]: raise AssertionError("repeated misconception was missed")

        before = profile_path.read_bytes(); lesson_dir = base / "lesson"
        completed = subprocess.run([sys.executable, str(ADAPTIVE), "lesson", "--profile", str(profile_path), "--workspace", str(workspace), "--concept", "unknown-target", "--output-dir", str(lesson_dir)], capture_output=True, text=True, encoding="utf-8")
        if completed.returncode: raise AssertionError(completed.stderr or completed.stdout)
        if profile_path.read_bytes() != before: raise AssertionError("lesson generation mutated profile")
        if not (lesson_dir / "lesson_interactive.html").exists(): raise AssertionError("interactive lesson missing")
        if "lean-html-skill:feedback2:start" not in (lesson_dir / "lesson_interactive.html").read_text(encoding="utf-8"): raise AssertionError("lesson did not reuse lean HTML")

        selection = select(profile, settings, datetime.now(timezone.utc), "unknown-target")
        actual = {"evidence": [
            {"evidence_type": "self_report", "prompt_used": False, "observed_performance": "Claims to know it.", "confidence": 1.0},
            {"evidence_type": "direct_application", "prompt_used": False, "observed_performance": "Applied the distinction to a new example.", "confidence": 0.8},
        ], "proposed_status_change": "learning", "misconception": "", "unresolved_question": ""}
        handoff = build_feedback(profile, selection, actual, datetime.now(timezone.utc))
        if "direct_application" not in handoff["proposed_review_schedule"]["reason"]: raise AssertionError("actual performance did not outrank self-report")
        feedback_path = base / "teaching_feedback.json"; feedback_path.write_text(json.dumps(handoff, ensure_ascii=False), encoding="utf-8")
        invalid = dict(handoff); invalid["evidence"] = []
        invalid_path = base / "invalid.json"; invalid_path.write_text(json.dumps(invalid), encoding="utf-8")
        bad = subprocess.run([sys.executable, str(ADAPTIVE), "import-feedback", "--profile", str(profile_path), "--feedback", str(invalid_path)], capture_output=True, text=True, encoding="utf-8")
        if bad.returncode == 0 or profile_path.read_bytes() != before: raise AssertionError("invalid feedback changed profile")
        ok = subprocess.run([sys.executable, str(ADAPTIVE), "import-feedback", "--profile", str(profile_path), "--wiki", str(base / "wiki"), "--feedback", str(feedback_path)], capture_output=True, text=True, encoding="utf-8")
        if ok.returncode: raise AssertionError(ok.stderr or ok.stdout)
        imported = load_json(profile_path)
        if "unknown-target" not in imported["concepts"] or len(imported["concepts"]) != len(profile["concepts"]): raise AssertionError("teaching import did not preserve the stable concept ID")
        if not any(event.get("event_type") == "teaching_feedback" for event in imported["events"]): raise AssertionError("teaching provenance missing")
        if not any(row.get("concept_id") == "unknown-target" for row in imported["review_queue"]): raise AssertionError("teaching schedule missing")
        if not list(base.glob("profile.json.*.bak")): raise AssertionError("profile backup missing")
        if "\ufffd" in (lesson_dir / "lesson.md").read_text(encoding="utf-8"): raise AssertionError("UTF-8 replacement character")
    print("adaptive-teach passed: deterministic ranking, evidence distinction, no-write lesson, strict handoff, backup import, and UTF-8.")
    return 0


if __name__ == "__main__": raise SystemExit(main())
