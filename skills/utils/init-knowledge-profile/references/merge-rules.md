# Merge Rules

Apply patches cautiously.

## Concept Candidates

Concept candidates are converted to a reader-feedback-shaped handoff and imported through `reader-learner` logic.

Rules:

- `unrated` is safe for exposure-only.
- Do not downgrade `known` or `mastered` because of a hard local question.
- `unknown` and `learning` should create review queue entries.
- Every imported item must carry source/event evidence.

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

## Backup

Use `--backup` when applying to a live profile. Backups should be timestamped beside the profile.
