---
name: chat-knowledge-profile
description: Extract reviewable learner/person-profile signals from local ChatGPT/GPT/Claude/Deepseek conversation exports for PaperTrace. Use when the user wants to mine past AI chat sessions, summarize conversations, create Obsidian-style topic/navigation artifacts, identify concepts the user knows or struggles with, infer durable learning/research/workflow/writing preferences, or produce strict reader-learner feedback handoffs for .agents/reader-learner/knowledge_profile.json.
---

# Chat Knowledge Profile

## Purpose

Convert past AI conversations into compact, source-grounded learner-profile evidence without dumping raw chat history into `knowledge_profile.json`.

This skill owns **Primary Pipeline 3: Local Chat-to-Profile Import**. It is distinct from Pipeline 1 paper-reader HTML, Pipeline 2 daily-briefing release, and Pipeline 4 adaptive teaching decisions/evidence return. Its terminal operation is a human-reviewed `profile_patch.json` applied with backup through strict `reader-learner` validation; it does not generate paper/news/lesson HTML.

The design borrows only patterns, not code, from:

- ChatInsights: multi-platform chat export parsing, concept tracking, Obsidian-ready summaries, and optional training-pair extraction.
- gpt-obsidian: incremental imports, per-chat notes, topic tags/backlinks, monthly indexes, and import reports.

## First Principles

- Preserve provenance: every candidate must point to a local source and bounded event.
- Compile chats into evidence first, then infer profile signals.
- Treat exposure as `unrated`; infer `known`, `unknown`, `learning`, or `mastered` only from user-authored evidence.
- Produce strict `reader-learner` handoff items with `source_anchor`, `concept_type`, and stable concept labels.
- Prefer reviewable patches over direct mutation.
- Never import suspected credentials, tokens, passwords, cookies, private keys, certificates, or session stores.
- Do not overwrite `known` or `mastered` from a local question; append evidence and review context.

## Pipeline

```text
local chat exports
  -> collect          # sources.jsonl, events.jsonl, conversation_summaries.json
  -> extract          # profile_candidates.json
  -> propose          # reviewable profile_patch.json + reader_feedback_handoff
  -> apply --backup   # optional, after review; delegates concept updates to reader-learner
```

`sources.jsonl`, `events.jsonl`, `conversation_summaries.json`, `profile_candidates.json`, and an unapplied `profile_patch.json` are review intermediates. Do not report profile mutation as complete before human review and successful `apply --backup`; do not auto-apply merely because candidate extraction succeeded.

`sources.jsonl`, `events.jsonl`, `conversation_summaries.json`, `profile_candidates.json`, and an unapplied `profile_patch.json` are review intermediates. Do not report profile mutation as complete before human review and successful `apply --backup`; do not auto-apply merely because candidate extraction succeeded.

Use local files only. Save share URLs as `.txt`, `.md`, `.html`, or `.json` first.

## Commands

Run from the project root:

```powershell
cd D:\AI\PaperTrace
```

Collect local conversation files:

```powershell
python D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py collect --input <chat_export_or_folder> --output D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions
```

Extract reviewable candidates:

```powershell
python D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py extract --events D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\events.jsonl --output D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\profile_candidates.json
```

Propose a patch against the existing profile:

```powershell
python D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py propose --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json --candidates D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\profile_candidates.json --output D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\profile_patch.json
```

Apply only after review:

```powershell
python D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py apply --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json --patch D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\profile_patch.json --backup
```

## Inputs

Supported local inputs:

- `.txt`
- `.md`
- `.html`
- `.json`
- folders containing those files

The collector recognizes ChatGPT `mapping`, Claude `chat_messages`, and Deepseek-style `fragments` where present. It also accepts plain role-prefixed logs.

## Candidate Types

- `concept_status`: a concept plus `unknown`, `learning`, `known`, `mastered`, or `unrated`.
- `learning_preference`: explanation preferences such as first-principles, examples, math derivation, or concise actionable style.
- `research_interest`: durable research directions or recurring topics.
- `workflow_preference`: project workflow preferences and tool habits.
- `project_rule`: durable project rules confirmed by the user.
- `writing_style`: preferred output style for paper reading, reports, or explanations.

## Output Artifacts

- `sources.jsonl`: one local conversation/file per line.
- `events.jsonl`: bounded user/assistant/system evidence events.
- `conversation_summaries.json`: deterministic "At a Glance", topic tags, explicit preferences, decisions, questions, and action-like items per conversation.
- `profile_candidates.json`: conservative signals extracted from user-authored evidence.
- `profile_patch.json`: reviewable operations plus a strict `reader_feedback_handoff` envelope for `reader-learner`.

The handoff must pass `reader-learner` strict validation before `apply`. It uses `source_kind: chat_session` rather than a Reader-bundle envelope, so it carries bounded local chat provenance and never fabricates Reader `bundle_provenance` metadata.

## References

Read these when changing behavior:

- `references/conversation-profile-schema.md`: intermediate JSONL/JSON shapes.
- `references/extraction-rules.md`: conservative evidence-to-candidate rules.
- `references/merge-rules.md`: patch and apply rules for `knowledge_profile.json`.

## Validation

Run from `D:\AI\PaperTrace` after edits:

```powershell
python -m py_compile D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py
python D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\audit_chat_knowledge_profile.py
python C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\AI\PaperTrace\skills\utils\chat-knowledge-profile
```
