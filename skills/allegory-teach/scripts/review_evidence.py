"""Validate review provenance, not the semantic truth of model judgments."""
import hashlib
import json


ROUNDS = {"story-completeness", "semantic-and-source", "cross-surface-and-display"}


def story_digest(story):
    return hashlib.sha256(json.dumps(story, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_review(story, review):
    failures = []
    if review.get("story_sha256") != story_digest(story):
        failures.append("review does not bind the current story and example")
    rows = review.get("rounds", [])
    if not isinstance(rows, list) or {r.get("id") for r in rows} != ROUNDS:
        return failures + ["three distinct review rounds are required"]
    if len(rows) != len(ROUNDS):
        failures.append("duplicate review rounds")
    source = json.dumps(story, ensure_ascii=False)
    for row in rows:
        if row.get("judgment") != "pass":
            failures.append(row.get("id", "unknown") + ": not reviewed or failed")
        for key in ("reviewed_text", "reason", "source_or_rule", "limitation"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                failures.append(row["id"] + ": missing " + key)
        if row.get("reviewed_text") and row["reviewed_text"] not in source:
            failures.append(row["id"] + ": quoted text is absent from current case")
    return failures
