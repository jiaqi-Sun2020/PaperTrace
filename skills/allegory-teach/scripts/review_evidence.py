"""Validate review provenance, not the semantic truth of model judgments."""
import hashlib
import json


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


def story_digest(story):
    return hashlib.sha256(json.dumps(story, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_review(story, review):
    failures = []
    if review.get("story_sha256") != story_digest(story):
        failures.append("review does not bind the current story and example")
    protocol = review.get("review_protocol_version")
    if protocol not in (None, 2):
        failures.append("unsupported review protocol version")
    if protocol == 2:
        if review.get("review_method") not in {"self", "independent"}:
            failures.append("review method must identify self or independent review")
        card = review.get("task_card")
        if not isinstance(card, dict):
            failures.append("new review requires a private task card")
        else:
            for key in TASK_CARD_KEYS:
                if not isinstance(card.get(key), str) or not card[key].strip():
                    failures.append("task card missing " + key)
    rows = review.get("rounds", [])
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows) or {r.get("id") for r in rows} != ROUNDS:
        return failures + ["three distinct review rounds are required"]
    if len(rows) != len(ROUNDS):
        failures.append("duplicate review rounds")
    source = json.dumps(story, ensure_ascii=False)
    narrative = json.dumps({"title": story.get("title"), "paragraphs": story.get("paragraphs")}, ensure_ascii=False)
    for row in rows:
        if protocol == 2:
            materials = row.get("materials_seen")
            if (not isinstance(materials, list)
                    or any(not isinstance(item, str) for item in materials)
                    or len(materials) != len(ROUND_MATERIALS[row["id"]])
                    or set(materials) != ROUND_MATERIALS[row["id"]]):
                failures.append(row["id"] + ": declared review materials do not match the round")
        if row.get("judgment") != "pass":
            failures.append(row.get("id", "unknown") + ": not reviewed or failed")
        for key in ("reviewed_text", "reason", "source_or_rule", "limitation"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                failures.append(row["id"] + ": missing " + key)
        quoted_surface = narrative if protocol == 2 and row["id"] == "story-completeness" else source
        quote = row.get("reviewed_text")
        if isinstance(quote, str) and quote and quote not in quoted_surface:
            failures.append(row["id"] + ": quoted text is absent from current case")
    return failures
