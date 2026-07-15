#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Profile-backed teaching decisions.  This program never writes the profile directly."""
from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
READER_SCRIPTS = ROOT / "skills" / "reader-learner" / "scripts"
if str(READER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(READER_SCRIPTS))
from profile_v2 import load_json, validate_profile_shape  # noqa: E402
from import_teaching_feedback import validate_teaching_feedback  # noqa: E402

DEFAULT_PROFILE = ROOT / ".agents" / "reader-learner" / "knowledge_profile.json"
DEFAULT_WORKSPACE = ROOT / ".agents" / "adaptive-teach"
DEFAULT_SETTINGS = {
    "default_language": "zh-CN", "lesson_minutes": 15, "theory_practice_ratio": "40:60",
    "generate_html": True, "review_frequency": "standard", "allowed_local_material_roots": [],
    "sync_visible_wiki_after_import": True, "mission_relevance": {}, "prerequisites": {},
}
MISSION_TEMPLATE = """# Teaching Mission\n\n## 为什么学习\n- [请说明一个具体研究或实践结果]\n\n## 近期目标\n- [可在未来数周验证的结果]\n\n## 长期目标\n- [长期能力或研究目标]\n\n## 当前优先领域\n- [领域或项目]\n\n## 不在当前范围\n- [暂不学习的相邻主题]\n\n## 约束\n- 每次可用时间：15 分钟\n- 语言：中文（保留必要英文术语）\n\n## 成功标准\n- [可观察的应用或解释能力]\n"""


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def ensure_workspace(workspace: Path) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    for name in ("sessions", "lessons", "diagnostics", "references", "derived"):
        (workspace / name).mkdir(exist_ok=True)
    mission = workspace / "TEACHING-MISSION.md"
    if not mission.exists():
        write_new(mission, MISSION_TEMPLATE)
    settings = workspace / "teaching-settings.json"
    if not settings.exists():
        write_new(settings, dump(DEFAULT_SETTINGS))


def read_settings(workspace: Path) -> dict[str, Any]:
    settings = dict(DEFAULT_SETTINGS)
    path = workspace / "teaching-settings.json"
    if path.exists():
        loaded = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(loaded, dict):
            raise ValueError("teaching-settings.json must be an object")
        settings.update(loaded)
    return settings


def read_profile(path: Path) -> dict[str, Any]:
    profile = load_json(path)
    validate_profile_shape(profile)
    if int(profile.get("version") or 0) != 2:
        raise ValueError("adaptive-teach requires schema-v2 profile; migrate it with reader-learner first")
    return profile


def mission_summary(workspace: Path) -> str:
    path = workspace / "TEACHING-MISSION.md"
    if not path.exists():
        return "Mission is not initialized. Ask the six template questions before mission-driven teaching."
    lines = [line.strip("- ") for line in path.read_text(encoding="utf-8-sig").splitlines() if line.startswith("- ") and "[" not in line]
    return "; ".join(lines[:3]) or "Mission needs answers to the template questions."


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def event_evidence(profile: dict[str, Any], concept_id: str) -> list[dict[str, Any]]:
    return [item for item in profile.get("events", []) if isinstance(item, dict) and item.get("concept_id") == concept_id]


def candidate_for(profile: dict[str, Any], settings: dict[str, Any], concept_id: str, concept: dict[str, Any], date: datetime) -> dict[str, Any]:
    status = str(concept.get("status") or "unrated")
    events = event_evidence(profile, concept_id)
    reasons: list[str] = []
    evidence_refs = [str(event.get("event_id")) for event in events if event.get("event_id")]
    priority = 0
    mode = "diagnose"
    if status == "unknown":
        priority += 70; reasons.append("explicit_unknown"); mode = "teach"
    elif status == "learning":
        priority += 40; reasons.append("learning_needs_support"); mode = "teach"
    elif status == "unrated":
        priority += 15; reasons.append("insufficient_evidence"); mode = "diagnose"
    repeated = sum(1 for event in events if event.get("status") in {"unknown", "learning"} or event.get("user_question"))
    if repeated >= 2:
        priority += min(20, repeated * 5); reasons.append("repeated_confusion")
    due_rows = [row for row in profile.get("review_queue", []) if isinstance(row, dict) and row.get("concept_id") == concept_id and (parse_time(row.get("due_at")) or date) <= date]
    if due_rows and status in {"known", "mastered", "learning"}:
        priority += 60; reasons.append("review_due"); mode = "review" if status in {"known", "mastered"} else mode
        evidence_refs.extend(str(row.get("last_event_id")) for row in due_rows if row.get("last_event_id"))
    relevance = settings.get("mission_relevance", {}).get(concept_id, 0) if isinstance(settings.get("mission_relevance"), dict) else 0
    if isinstance(relevance, int) and relevance:
        priority += max(0, min(50, relevance)); reasons.append("mission_relevant")
    last_seen = parse_time(concept.get("last_seen_at"))
    if last_seen and date - last_seen < timedelta(days=2) and not due_rows:
        priority -= 15; reasons.append("recent_overpractice")
    return {"concept_id": concept_id, "concept_name": concept.get("label", concept_id), "status": status, "priority": priority,
            "mode": mode, "reason_codes": reasons or ["no_actionable_evidence"], "evidence_refs": sorted(set(evidence_refs)),
            "uncertainties": ["No independent recall or application evidence."] if status == "unrated" else [], "source_refs": list(concept.get("source_ids") or [])}


def rank(profile: dict[str, Any], settings: dict[str, Any], date: datetime) -> list[dict[str, Any]]:
    rows = [candidate_for(profile, settings, concept_id, concept, date) for concept_id, concept in profile.get("concepts", {}).items() if isinstance(concept, dict)]
    return sorted(rows, key=lambda item: (-item["priority"], item["concept_id"]))


def select(profile: dict[str, Any], settings: dict[str, Any], date: datetime, requested: str | None = None) -> dict[str, Any]:
    rows = rank(profile, settings, date)
    if requested:
        rows = [row for row in rows if row["concept_id"] == requested]
        if not rows: raise ValueError(f"Concept not found: {requested}")
    selected = dict(rows[0]) if rows else {"concept_id": "", "concept_name": "", "mode": "diagnose", "priority": 0, "reason_codes": ["empty_profile"], "evidence_refs": [], "uncertainties": ["Profile has no concepts."], "source_refs": []}
    prerequisites = settings.get("prerequisites", {}) if isinstance(settings.get("prerequisites"), dict) else {}
    blockers = prerequisites.get(selected["concept_id"], []) if isinstance(prerequisites.get(selected["concept_id"], []), list) else []
    for blocker in blockers:
        blocker_concept = profile.get("concepts", {}).get(blocker)
        if isinstance(blocker_concept, dict) and blocker_concept.get("status") in {"unknown", "learning"}:
            original = selected["concept_id"]
            selected = candidate_for(profile, settings, blocker, blocker_concept, date)
            selected["mode"] = "prerequisite"; selected["priority"] += 30
            selected["reason_codes"].append("prerequisite_blocker")
            selected["blocker_for"] = original
            break
    alternatives = [{"concept_id": row["concept_id"], "priority": row["priority"], "not_selected_because": ["lower_priority_or_not_the_minimal_blocker"]} for row in rank(profile, settings, date) if row["concept_id"] != selected["concept_id"]][:5]
    return {"generated_at": date.isoformat(), "profile_schema_version": 2, "mode": selected["mode"], "selected_concept_id": selected["concept_id"], "selected_concept_name": selected["concept_name"], "priority": selected["priority"], "reason_codes": selected["reason_codes"], "evidence_refs": selected["evidence_refs"], "source_refs": selected["source_refs"], "uncertainties": selected["uncertainties"], "alternatives": alternatives, **({"blocker_for": selected["blocker_for"]} if "blocker_for" in selected else {})}


def lesson_markdown(selection: dict[str, Any], minutes: int, mission: str) -> str:
    topic, mode = selection["selected_concept_name"], selection["mode"]
    activity = "用自己的话解释并举一个新例子" if mode != "review" else "不看资料写出定义、关键区别和一个应用"
    return f"""# {topic}：{mode} 微课程\n\n**任务目标（{minutes} 分钟）**：{activity}，并指出一个仍不确定的边界。\n\n## 与 Mission 的关系\n{mission}\n\n## 1. 先回忆（2 分钟）\n不查资料：写下 `{topic}` 的定义、它不是什么，以及它在当前研究/实践中解决什么问题。\n\n## 2. 最小理论（4 分钟）\n只核对你刚才缺失的一项：定义、关键机制、或与相邻概念的区别。不要把阅读过的内容当作掌握。\n\n## 3. 应用（5 分钟）\n在一个新的、具体场景中使用 `{topic}`；写出输入、判断步骤、结论，并说明一个会失败的反例。\n\n## 4. 主动回忆与迁移（3 分钟）\n合上资料后，向一位同行解释：如果条件改变，`{topic}` 的结论哪里仍成立、哪里不成立？\n\n## 即时自检\n- 无提示解释是否完整？\n- 是否使用提示？\n- 应用是否真的落到新案例？\n- 若错了，错误的 misconception 是什么？\n\n## 证据与下一步\n本课只引用 profile source refs：{', '.join(selection.get('source_refs') or ['（当前无可引用 source ref；先诊断）'])}。完成课程本身不更新画像；仅实际回答和表现可形成 teaching feedback。\n"""


def lesson_html(topic: str, markdown: str) -> str:
    body = "".join(f"<section class='item-card' id='lesson-{index}'><p>{html.escape(line)}</p></section>" for index, line in enumerate(markdown.splitlines()) if line and not line.startswith("#"))
    return f"<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(topic)} 微课程</title></head><body><main><h1>{html.escape(topic)} 微课程</h1>{body}</main></body></html>"


def build_lesson(profile: dict[str, Any], workspace: Path, output: Path, selection: dict[str, Any], settings: dict[str, Any]) -> dict[str, str]:
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()): raise FileExistsError(f"Output directory must be empty: {output}")
    mission = mission_summary(workspace)
    md = lesson_markdown(selection, int(settings.get("lesson_minutes", 15)), mission)
    lesson_path = output / "lesson.md"; write_new(lesson_path, md)
    diagnostic = {"session_mode": selection["mode"], "tasks": ["无提示定义", "关键区别", "简单应用"], "max_tasks": 3}
    write_new(output / "diagnostic.json", dump(diagnostic))
    write_new(output / "session_plan.json", dump(selection))
    feedback_template = {"teaching_feedback_version": 1, "state": "awaiting_actual_user_feedback", "session_id": output.name, "selected_concept_id": selection["selected_concept_id"], "selected_concept_name": selection["selected_concept_name"], "instruction": "Use build-feedback after recording actual performance; this template is not importable evidence."}
    write_new(output / "teaching_feedback.template.json", dump(feedback_template))
    result = {"lesson": str(lesson_path)}
    if settings.get("generate_html", True):
        base = output / "lesson_base.html"; write_new(base, lesson_html(selection["selected_concept_name"], md))
        feedback = {"reader_feedback_version": 2, "paper_title": f"Teaching lesson: {selection['selected_concept_name']}", "reader_path": str(output), "bundle_provenance": {key: {"path": "adaptive-teach://not-a-reader", "sha256": "0" * 64} for key in ("source_map", "completion_ledger", "reader_manifest", "structure_validation_report")}, "items": []}
        feedback_path = output / "lesson_feedback_seed.json"; write_new(feedback_path, dump(feedback))
        target = output / "lesson_interactive.html"
        lean = ROOT / "skills" / "utils" / "lean-html-skill" / "scripts" / "lean_html.py"
        completed = subprocess.run([sys.executable, str(lean), "attach-feedback", "--html", str(base), "--feedback", str(feedback_path), "--output", str(target)], check=False, capture_output=True, text=True, encoding="utf-8")
        if completed.returncode: raise RuntimeError(completed.stderr or completed.stdout)
        base.unlink(); feedback_path.unlink(); result["lesson_interactive"] = str(target)
    return result


def schedule_for(evidence: list[dict[str, Any]], status: str, date: datetime) -> dict[str, Any]:
    strongest = max(evidence, key=lambda item: ({"self_report": 1, "recognition": 2, "prompted_recall": 3, "unprompted_recall": 4, "direct_application": 5, "transfer": 6, "delayed_recall": 7, "misconception": 0}[item["evidence_type"]], item["confidence"]))
    strength = {"self_report": 0, "recognition": 1, "prompted_recall": 2, "unprompted_recall": 4, "direct_application": 5, "transfer": 7, "delayed_recall": 10, "misconception": -2}[strongest["evidence_type"]]
    if strongest["prompt_used"]: strength -= 2
    if strongest["evidence_type"] == "misconception": strength = -2
    days = 1 if strength <= 1 else 3 if strength <= 4 else 7 if strength <= 6 else 14
    return {"due_at": (date + timedelta(days=days)).isoformat(), "priority": max(20, min(100, 80 - strength * 5)), "reason": f"transparent spacing heuristic: {strongest['evidence_type']}, prompt_used={str(strongest['prompt_used']).lower()}"}


def build_feedback(profile: dict[str, Any], selection: dict[str, Any], actual: dict[str, Any], date: datetime) -> dict[str, Any]:
    evidence = actual.get("evidence")
    if not isinstance(evidence, list) or not evidence: raise ValueError("actual feedback needs non-empty evidence")
    status = actual.get("proposed_status_change") or profile["concepts"][selection["selected_concept_id"]].get("status", "unrated")
    payload = {"teaching_feedback_version": 1, "session_id": selection.get("session_id") or f"teach-{date.strftime('%Y%m%dT%H%M%S')}", "selected_concept_id": selection["selected_concept_id"], "selected_concept_name": selection["selected_concept_name"], "source_refs": selection.get("source_refs") or ["teaching-session"], "evidence": evidence, "misconception": actual.get("misconception", ""), "unresolved_question": actual.get("unresolved_question", ""), "proposed_status_change": status, "proposed_review_schedule": schedule_for(evidence, status, date), "confidence": max(float(item.get("confidence", 0)) for item in evidence), "provenance": "adaptive-teach"}
    validate_teaching_feedback(payload, profile)
    return payload


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["analyze", "next", "lesson", "run", "review", "validate-feedback", "build-feedback", "import-feedback"])
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE)); parser.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    parser.add_argument("--concept"); parser.add_argument("--output-dir"); parser.add_argument("--feedback"); parser.add_argument("--actual-feedback"); parser.add_argument("--wiki")
    parser.add_argument("--limit", type=int, default=20); parser.add_argument("--dry-run", action="store_true"); parser.add_argument("--json", action="store_true")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv); profile_path, workspace = Path(args.profile).resolve(), Path(args.workspace).resolve()
    profile = read_profile(profile_path)
    if args.command == "validate-feedback":
        validate_teaching_feedback(load_json(Path(args.feedback).resolve()), profile); print("teaching feedback is valid"); return 0
    if args.command == "import-feedback":
        feedback = Path(args.feedback).resolve(); validate_teaching_feedback(load_json(feedback), profile)
        pipeline = READER_SCRIPTS / "feedback_visible_wiki_pipeline.py"
        command = [sys.executable, str(pipeline), "teaching-feedback", "--profile", str(profile_path), "--feedback", str(feedback)]
        if args.wiki: command.extend(["--wiki", str(Path(args.wiki).resolve())])
        return subprocess.run(command, check=False).returncode
    if args.command == "review":
        settings = read_settings(workspace)
        candidates = {row["concept_id"]: row for row in rank(profile, settings, now())}
        rows = [row for row in profile.get("review_queue", []) if isinstance(row, dict)]
        rows.sort(key=lambda row: (-int(row.get("priority") or 0), row.get("due_at") or "", row.get("concept_id") or ""))
        for row in rows[:args.limit]:
            candidate = candidates.get(str(row.get("concept_id")), {})
            print(f"- P{row.get('priority', 0)} {row.get('concept_id')}: {candidate.get('mode', 'review')} | {', '.join(candidate.get('reason_codes', ['queued_review']))}")
        return 0
    ensure_workspace(workspace); settings = read_settings(workspace); selection = select(profile, settings, now(), args.concept)
    if args.command == "analyze":
        report = {"generated_at": now().isoformat(), "profile_schema_version": 2, "mission_summary": mission_summary(workspace), "candidates": rank(profile, settings, now())}
        target = workspace / "derived" / "weakness_report.json"
        if not target.exists() and not args.dry_run: write_new(target, dump(report))
        print(dump(report)); return 0
    if args.command == "next": print(dump(selection)); return 0
    if args.command == "build-feedback":
        actual = load_json(Path(args.actual_feedback).resolve()); payload = build_feedback(profile, selection, actual, now())
        target = Path(args.output_dir).resolve() / "teaching_feedback.json" if args.output_dir else workspace / "teaching_feedback.json"
        if not args.dry_run: write_new(target, dump(payload))
        print(dump(payload)); return 0
    output = Path(args.output_dir).resolve() if args.output_dir else workspace / "sessions" / f"teach-{now().strftime('%Y%m%dT%H%M%S')}"
    result = build_lesson(profile, workspace, output, selection, settings)
    write_new(output / "session_record.json", dump({"session_id": output.name, "mission": mission_summary(workspace), "selection": selection, "artifacts": result, "profile_import": "not_attempted", "uncertainties": selection["uncertainties"]}))
    print(dump({"selection": selection, "artifacts": result})); return 0


if __name__ == "__main__": raise SystemExit(main())
