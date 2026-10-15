"""Validate review provenance, not the semantic truth of model judgments."""
import hashlib
import json
import re
from datetime import datetime


ROUNDS = {"story-completeness", "semantic-and-source", "cross-surface-and-display"}
TASK_CARD_KEYS = (
    "teaching_question", "source_task_and_constraint", "learner_bridge",
    "actor_goal_and_success", "shortcut_and_limit", "decisive_rule_and_action",
    "counterfactual_and_boundary",
)
ROUND_MATERIALS = {
    "story-completeness": {"title", "paragraphs"},
    "semantic-and-source": {"story", "debrief", "source"},
    "cross-surface-and-display": {"story", "worked_example", "html"},
}
TRACE_KINDS = {"physical_quantity", "representation_label", "control_event", "knowledge_state", "other_state"}
CLAIM_CLASSES = {"source_fact", "derivation", "teaching_assumption"}
DISPLAY_CHECKS = {"responsive_reading", "formula_links_keyboard", "print_layout"}


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def _validate_v3(story, rounds, pending_display=False):
    """Check review evidence shape and anchoring, never its semantic truth."""
    failures = []
    by_id = {row["id"]: row for row in rounds}
    paragraphs = story.get("paragraphs")
    narrative = "\n".join([str(story.get("title") or ""),
                           *(part for part in paragraphs if isinstance(part, str))]
                          if isinstance(paragraphs, list) else [str(story.get("title") or "")])
    first = by_id["story-completeness"]
    trace = first.get("literal_trace")
    quotes = []
    if not isinstance(trace, list) or not trace or any(not isinstance(edge, dict) for edge in trace):
        failures.append("story-completeness: literal_trace requires decisive story transitions")
    else:
        for index, edge in enumerate(trace):
            prefix = f"story-completeness: literal_trace[{index}]"
            for key in ("story_quote", "tracked_object", "before", "trigger", "operation", "after", "rule_origin"):
                if not _nonempty(edge.get(key)):
                    failures.append(f"{prefix} missing {key}")
            kind = edge.get("kind")
            if not isinstance(kind, str) or kind not in TRACE_KINDS:
                failures.append(f"{prefix} has invalid kind")
            quote = edge.get("story_quote")
            if _nonempty(quote):
                quotes.append(quote)
                if quote not in narrative:
                    failures.append(f"{prefix} quote is absent from the narrative")
        if len(quotes) != len(set(quotes)):
            failures.append("story-completeness: literal_trace quotes must be distinct")
    counterfactual = first.get("counterfactual")
    if not isinstance(counterfactual, dict) or any(not _nonempty(counterfactual.get(key))
            for key in ("changed_condition", "predicted_result", "reason")):
        failures.append("story-completeness: counterfactual must change a condition and predict its result")

    second = by_id["semantic-and-source"]
    mappings = second.get("technical_edges")
    if not isinstance(mappings, list) or not mappings or any(not isinstance(edge, dict) for edge in mappings):
        failures.append("semantic-and-source: technical_edges are required")
    else:
        mapped_quotes = []
        for index, edge in enumerate(mappings):
            prefix = f"semantic-and-source: technical_edges[{index}]"
            for key in ("story_quote", "technical_operation", "source_anchor", "scope_and_nonconclusion"):
                if not _nonempty(edge.get(key)):
                    failures.append(f"{prefix} missing {key}")
            claim_class = edge.get("claim_class")
            if not isinstance(claim_class, str) or claim_class not in CLAIM_CLASSES:
                failures.append(f"{prefix} has invalid claim_class")
            if _nonempty(edge.get("story_quote")):
                mapped_quotes.append(edge["story_quote"])
        if len(mapped_quotes) != len(set(mapped_quotes)) or set(mapped_quotes) != set(quotes):
            failures.append("semantic-and-source: technical_edges must map each literal_trace quote once")

    third = by_id["cross-surface-and-display"]
    alignment = third.get("example_alignment")
    example = story.get("worked_example")
    if not isinstance(example, dict):
        example = {}
    if not isinstance(alignment, dict):
        failures.append("cross-surface-and-display: example_alignment is required")
    else:
        for key in ("question", "observable", "step_quote", "result", "consistency_reason"):
            if not _nonempty(alignment.get(key)):
                failures.append(f"cross-surface-and-display: example_alignment missing {key}")
        for key in ("question", "observable", "result"):
            if _nonempty(alignment.get(key)) and alignment[key] != example.get(key):
                failures.append(f"cross-surface-and-display: example_alignment {key} differs from worked_example")
        if _nonempty(alignment.get("step_quote")) and alignment["step_quote"] not in json.dumps(example.get("steps") or [], ensure_ascii=False):
            failures.append("cross-surface-and-display: example_alignment step_quote is absent from worked_example")

    for row in rounds:
        if row.get("unresolved") != [] and not (pending_display and row["id"] == "cross-surface-and-display"):
            failures.append(f"{row['id']}: unresolved findings must be cleared before pass")
    return failures


def story_digest(story):
    return hashlib.sha256(json.dumps(story, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def _display_evidence(row, html_sha256, allow_pending):
    """Only typed actual-display incompleteness can precede preview transport."""
    failures = []
    display = row.get("display_review")
    pending = allow_pending and row.get("judgment") == "pending"
    if display is None and not pending:
        return [], False  # Historical complete records retain their meaning.
    if (not isinstance(display, dict) or type(display.get("version")) is not int or display["version"] != 1
            or set(display) != {"version", "status", "html_sha256", "checks"}
            or not isinstance(display.get("html_sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", display["html_sha256"])
            or (html_sha256 is not None and display["html_sha256"] != html_sha256)):
        return ["cross-surface-and-display: invalid or stale typed display evidence"], False
    checks = display.get("checks")
    if (not isinstance(checks, list) or len(checks) != len(DISPLAY_CHECKS)
            or any(not isinstance(check, dict) or not isinstance(check.get("id"), str) for check in checks)
            or {check["id"] for check in checks} != DISPLAY_CHECKS):
        return ["cross-surface-and-display: all display checks are required"], False
    cross = row.get("cross_surface_checks")
    if (not isinstance(cross, dict) or set(cross) != {"judgment", "reason"}
            or cross.get("judgment") != "pass" or not _nonempty(cross.get("reason"))):
        failures.append("cross-surface-and-display: pre-display case and surface checks must pass")
    if pending:
        unresolved = row.get("unresolved")
        if (not isinstance(unresolved, list) or len(unresolved) != 1
                or not isinstance(unresolved[0], dict) or set(unresolved[0]) != {"kind", "reason"}
                or unresolved[0].get("kind") != "actual_display_pending" or not _nonempty(unresolved[0].get("reason"))
                or display.get("status") != "pending"
                or any(set(check) != {"id", "status"} or check.get("status") != "pending" for check in checks)):
            failures.append("cross-surface-and-display: only actual display pending is allowed before preview")
    else:
        if display.get("status") != "pass":
            failures.append("cross-surface-and-display: actual display has not passed")
        for check in checks:
            evidence = check.get("evidence")
            valid = (set(check) == {"id", "status", "evidence"} and check.get("status") == "pass"
                     and isinstance(evidence, dict) and set(evidence) == {"type", "reference", "environment", "observed_at"}
                     and evidence.get("type") in ("actual_browser", "human_acceptance")
                     and _nonempty(evidence.get("reference")) and _nonempty(evidence.get("environment")))
            try:
                stamp = datetime.fromisoformat(str((evidence or {}).get("observed_at") or "").replace("Z", "+00:00"))
                valid = valid and bool(stamp.tzinfo)
            except (ValueError, TypeError, AttributeError):
                valid = False
            if not valid:
                failures.append("cross-surface-and-display: missing actual evidence for " + check["id"])
    return failures, pending and not failures


def validate_review(story, review):
    """Formal review: no preview exemption is accepted by this public entry point."""
    return _validate_review(story, review)


def validate_review_for_preview(story, review, *, html_sha256):
    """Protocol-3 preview only; preserve all content and correspondence checks."""
    if (not isinstance(review, dict) or type(review.get("review_protocol_version")) is not int
            or review["review_protocol_version"] != 3
            or not isinstance(html_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", html_sha256)):
        return ["preview requires protocol-3 review and exact HTML identity"]
    return _validate_review(story, review, allow_display_pending=True, html_sha256=html_sha256)


def _validate_review(story, review, allow_display_pending=False, html_sha256=None):
    failures = []
    if not isinstance(story, dict) or not isinstance(review, dict):
        return ["story and review must be objects"]
    if review.get("story_sha256") != story_digest(story):
        failures.append("review does not bind the current story and example")
    protocol = review.get("review_protocol_version")
    if protocol not in (None, 2, 3):
        failures.append("unsupported review protocol version")
    if protocol in (2, 3):
        if review.get("review_method") not in ("self", "independent"):
            failures.append("review method must identify self or independent review")
        card = review.get("task_card")
        if not isinstance(card, dict):
            failures.append("new review requires a private task card")
        else:
            for key in TASK_CARD_KEYS:
                if not isinstance(card.get(key), str) or not card[key].strip():
                    failures.append("task card missing " + key)
    rows = review.get("rounds", [])
    if (not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get("id"), str)
                                          for row in rows) or {r["id"] for r in rows} != ROUNDS):
        return failures + ["three distinct review rounds are required"]
    if len(rows) != len(ROUNDS):
        failures.append("duplicate review rounds")
        return failures
    source = json.dumps(story, ensure_ascii=False)
    narrative = json.dumps({"title": story.get("title"), "paragraphs": story.get("paragraphs")}, ensure_ascii=False)
    third = next(row for row in rows if row["id"] == "cross-surface-and-display")
    display_failures, pending = _display_evidence(third, html_sha256, allow_display_pending)
    failures.extend(display_failures)
    for row in rows:
        if protocol in (2, 3):
            materials = row.get("materials_seen")
            if (not isinstance(materials, list)
                    or any(not isinstance(item, str) for item in materials)
                    or len(materials) != len(ROUND_MATERIALS[row["id"]])
                    or set(materials) != ROUND_MATERIALS[row["id"]]):
                failures.append(row["id"] + ": declared review materials do not match the round")
        if row.get("judgment") != "pass" and not (pending and row["id"] == "cross-surface-and-display"):
            failures.append(row.get("id", "unknown") + ": not reviewed or failed")
        for key in ("reviewed_text", "reason", "source_or_rule", "limitation"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                failures.append(row["id"] + ": missing " + key)
        quoted_surface = narrative if protocol in (2, 3) and row["id"] == "story-completeness" else source
        quote = row.get("reviewed_text")
        if isinstance(quote, str) and quote and quote not in quoted_surface:
            failures.append(row["id"] + ": quoted text is absent from current case")
    if protocol == 3:
        failures.extend(_validate_v3(story, rows, pending_display=pending))
    return failures
