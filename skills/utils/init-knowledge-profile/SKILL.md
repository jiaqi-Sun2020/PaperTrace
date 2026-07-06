---
name: init-knowledge-profile
description: Initialize or extend PAPER learner/person knowledge profiles from exported ChatGPT or GPT conversation files. Use when the user wants to combine past AI chat sessions, ChatGPT exports, shared-conversation text, markdown, HTML, or JSON into .agents/reader-learner/knowledge_profile.json through reviewable sources, evidence events, candidate profile signals, patches, and safe backup-gated application.
---

# Init Knowledge Profile

## Purpose

Convert past GPT conversations into reviewable learner-profile evidence without dumping raw chat history into `knowledge_profile.json`.

Use the four-step pipeline:

```text
conversation files
  -> collect
  -> events.jsonl
  -> extract
  -> profile_candidates.json
  -> propose
  -> profile_patch.json
  -> apply
  -> .agents/reader-learner/knowledge_profile.json
```

## First Principles

- Preserve provenance: every candidate must point back to a source and event.
- Keep raw conversation text out of concept keys.
- Treat exposure as `unrated`, not `known`.
- Prefer reviewable patches over direct profile mutation.
- Never import suspected credentials, tokens, passwords, cookies, private keys, certificates, or session stores.
- Do not overwrite `known` or `mastered` with a local question; add evidence and review context instead.

## Commands

Run from the project root:

```powershell
cd C:\Users\SSS\Desktop\PAPER
```

Collect local conversation files:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\utils\init-knowledge-profile\scripts\init_knowledge_profile.py collect --input <chat_export_or_folder> --output C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions
```

Extract reviewable candidates:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\utils\init-knowledge-profile\scripts\init_knowledge_profile.py extract --events C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\events.jsonl --output C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_candidates.json
```

Propose a patch against the existing profile:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\utils\init-knowledge-profile\scripts\init_knowledge_profile.py propose --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json --candidates C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_candidates.json --output C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_patch.json
```

Apply only after review:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\utils\init-knowledge-profile\scripts\init_knowledge_profile.py apply --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json --patch C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_patch.json --backup
```

## Inputs

Supported local inputs:

- `.txt`
- `.md`
- `.html`
- `.json`
- folders containing those files

ChatGPT share URLs should be saved or copied locally first. Do not rely on web access for repeatable profile initialization.

## Candidate Types

- `concept_status`: a concept plus `unknown`, `learning`, `known`, `mastered`, or `unrated`.
- `learning_preference`: explanation preferences such as first-principles, examples, math derivation, or concise actionable style.
- `research_interest`: durable research directions or recurring topics.
- `workflow_preference`: project workflow preferences and tool habits.
- `project_rule`: durable project rules confirmed by the user.
- `writing_style`: preferred output style for paper reading, reports, or explanations.

## References

Read these when changing behavior:

- `references/conversation-profile-schema.md`: intermediate JSONL/JSON shapes.
- `references/extraction-rules.md`: conservative evidence-to-candidate rules.
- `references/merge-rules.md`: patch and apply rules for `knowledge_profile.json`.
