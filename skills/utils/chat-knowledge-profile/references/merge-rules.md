# Merge Rules

Apply patches cautiously.

## Concept Candidates

Concept candidates are converted to a reader-feedback-shaped handoff and imported through `reader-learner` logic.

Rules:

- `unrated` is safe for exposure-only.
- Do not downgrade `known` or `mastered` because of a hard local question.
- `unknown` and `learning` should create review queue entries.
- Every imported item must carry source/event evidence.
- Every handoff item must pass `reader-learner` strict validation before profile mutation.
- Do not apply a patch if a concept handoff lacks `source_anchor`, `concept_type`, or bounded source context.

## Person Profile Candidates

Non-concept candidates live under:

```json
"person_profile": {
  "learning_preferences": {},
  "research_interests": {},
  "workflow_preferences": {},
  "project_rules": {},
  "writing_style": {}
}
```

Each entry should include:

- `label`
- `confidence`
- `evidence_event_ids`
- `source_ids`
- `first_seen_at`
- `last_seen_at`
- `notes`

## Conflict Handling

If a patch conflicts with existing high-confidence data:

- do not overwrite silently;
- append evidence;
- set `review_required: true`;
- record the operation in `skipped_operations` if not applied.

## Incrementality

Use stable source/event/candidate ids so repeated imports are idempotent:

- source ids derive from local path and title;
- event ids derive from source id, turn index, and bounded text;
- candidate ids derive from type, label, and evidence event.

Repeated `apply` calls should append no duplicate concept events when the underlying chat export has not changed.

## Obsidian-Style Review Artifacts

`conversation_summaries.json` is a review aid similar to an Obsidian import report:

- use `at_a_glance` for quick triage;
- use `topic_tags` for navigation;
- use `explicit_preferences`, `open_questions`, and `action_like_requests` to decide whether a candidate should be kept;
- do not merge a summary-only claim without event evidence.

## Backup

Use `--backup` when applying to a live profile. Backups should be timestamped beside the profile.
