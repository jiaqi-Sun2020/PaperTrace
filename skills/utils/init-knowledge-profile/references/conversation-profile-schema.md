# Conversation Profile Schema

This skill writes intermediate files before mutating `knowledge_profile.json`.

## sources.jsonl

Each line is one source conversation/file:

```json
{
  "source_id": "chat-src-...",
  "source_kind": "chat_session",
  "title": "Conversation title",
  "path": "local file path",
  "url": "",
  "created_at": "",
  "collected_at": "2026-07-06T00:00:00+00:00",
  "event_ids": []
}
```

## events.jsonl

Each line is a compact evidence event:

```json
{
  "event_id": "chat-evt-...",
  "source_id": "chat-src-...",
  "source_title": "Conversation title",
  "source_path": "local file path",
  "role": "user|assistant|system|unknown",
  "turn_index": 1,
  "timestamp": "",
  "text": "bounded text excerpt",
  "text_sha1": "...",
  "contains_sensitive_skip": false
}
```

Keep event text bounded. The source file remains the audit trail.

## profile_candidates.json

```json
{
  "candidate_version": 1,
  "generated_from": "init-knowledge-profile",
  "items": [
    {
      "candidate_id": "cand-...",
      "type": "concept_status|learning_preference|research_interest|workflow_preference|project_rule|writing_style",
      "label": "first principles explanation",
      "status": "learning",
      "confidence": 0.7,
      "evidence_event_ids": ["chat-evt-..."],
      "source_ids": ["chat-src-..."],
      "note": "short reason"
    }
  ]
}
```

## profile_patch.json

```json
{
  "patch_version": 1,
  "generated_from": "init-knowledge-profile",
  "review_required": true,
  "operations": [],
  "reader_feedback_handoff": {
    "reader_feedback_version": 2,
    "source_kind": "chat_session",
    "items": []
  }
}
```

`reader_feedback_handoff.items` is used only for `concept_status` candidates so the existing `reader-learner` v2 importer remains the owner of concept/event/review updates.
