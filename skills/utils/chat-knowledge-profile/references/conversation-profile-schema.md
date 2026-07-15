# Conversation Profile Schema

This skill writes intermediate files before mutating `knowledge_profile.json`.
The intermediate layer is the durable audit surface: raw chats stay in local files, bounded
events preserve provenance, summaries provide navigation, and only reviewed patches reach
`reader-learner`.

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
  "model": "gpt-4o",
  "text": "bounded text excerpt",
  "text_sha1": "...",
  "contains_sensitive_skip": false
}
```

Keep event text bounded. The source file remains the audit trail.

## conversation_summaries.json

Inspired by Obsidian chat archives, each source gets a compact navigation record:

```json
{
  "summary_version": 1,
  "generated_from": "chat-knowledge-profile",
  "items": [
    {
      "source_id": "chat-src-...",
      "title": "Conversation title",
      "path": "local file path",
      "at_a_glance": "first user request or compact summary",
      "topic_tags": ["quantum-walk", "reader-learner"],
      "explicit_preferences": [],
      "open_questions": [],
      "action_like_requests": [],
      "models": ["gpt-4o"]
    }
  ]
}
```

Use summaries for browsing and review. Do not treat them as profile truth without candidate evidence.

## profile_candidates.json

```json
{
  "candidate_version": 1,
  "generated_from": "chat-knowledge-profile",
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
  "generated_from": "chat-knowledge-profile",
  "review_required": true,
  "operations": [],
  "reader_feedback_handoff": {
    "source_kind": "chat_session",
    "conversation_import_version": 1,
    "items": [
      {
        "concept": "QSVT",
        "concept_id": "qsvt",
        "concept_type": "term",
        "status": "unknown",
        "annotation_kind": "concept",
        "source_anchor": "chat-evt-...",
        "block_id": "chat-evt-...",
        "source_excerpt": "bounded user-authored evidence"
      }
    ]
  }
}
```

`reader_feedback_handoff.items` is used only for `concept_status` candidates so the existing `reader-learner` v2 importer remains the owner of concept/event/review updates. Chat imports are not Reader artifacts: omit `reader_feedback_version`, `reader_path`, and `bundle_provenance`; each item instead carries its bounded local `source` and `source_title` provenance.
