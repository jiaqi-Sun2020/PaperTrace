# PaperTrace Agent Entry

Before changing this repository, read these canonical project rules in order:

1. `.agents/AGENTS.md`
2. `.agents/PROJECT_CONTEXT.md`
3. `.agents/README.md`

For the persistent human-facing knowledge layer, also read `skills/reader-learner/references/visible-wiki-schema.md`.

The `.agents/wiki/` directory is a curated, source-traceable Obsidian knowledge layer. Raw papers, reader bundles, feedback/events, pipeline data, and `.agents/reader-learner/knowledge_profile.json` remain outside it. Do not move or overwrite those source-layer records when editing the visible wiki.

`skills/adaptive-teach` is the explicit-invocation teaching decision layer. It reads the schema-v2 profile to analyze weakness/evidence gaps/due reviews, select one topic, create short teaching sessions and lesson artifacts, compute a transparent review proposal, and create teaching-feedback handoffs. It does not own profile schema, normalization, atomic mutation, PDF readers, news collection, Visible Wiki projection, or the shared HTML shell. `reader-learner` remains the sole owner of profile facts and imports teaching feedback through its safe pipeline.

## Natural-Language PDF-to-HTML Trigger

Treat a request of the following form as an explicit end-to-end implementation request, not as an extraction preview:

> 阅读当前项目下的 readme 和 .agents，根据 PAPER 的 pipeline 将 `<PDF-folder>` 下的 PDF 生成对应的可交互 HTML，一篇一篇来。

The request authorizes creating and completing reader bundles inside this repository. The agent must:

0. Treat this trigger as an explicit persistence request. When the Codex goal
   tools are available, create or continue one unbudgeted active goal for the
   selected PDF set before the first implementation command. The goal remains
   active while `final_response_allowed` is false and may be marked complete
   only after the audited formal HTML contract passes. A progress update is
   commentary, never a final response.

1. Discover the supplied PDFs and process them in a deterministic order.
2. Finish one paper completely—faithful block-level Chinese, block-specific notes, LaTeX reconstruction, inspectable figure/table/algorithm cards, `reader_wiki`, `reader_interactive.html`, and adversarial audit—before beginning the next.
3. Continue automatically after each audited pass. “一篇一篇来” controls sequencing; it does **not** mean “finish one extraction and wait for another user message”.
4. Never report a materialized draft, a failed completion ledger, or a preview HTML as the requested result. Bootstrap markers, rotated text, missing figure crops, and absent third-party translation tooling are direct Codex completion work, not terminal blockers.
5. Stop only for an unreadable/unavailable source, an ambiguous overwrite of an existing completed bundle, or a validation failure that cannot be repaired from PDF evidence; report the exact paper and failed gate.

The batch controller creates no batch-history or root-level state file. After
every checkpoint, read the `agent_continuation_contract` embedded in its JSON
standard output and treat it as a fail-closed response boundary:

- The first implementation command must be
  `build_formal_reader_batch.py --agent-continuation`; do not begin by editing
  `paper.md` directly. If the current turn has not observed a controller
  contract, a final response is forbidden.

- If `final_response_allowed` is `false`, do not end the user turn, do not ask
  for “continue”, and do not report `reader_progress.html`; complete the named
  `active_paper` and rerun `next_command` in the same task.
- `pending`, `invalid`, missing crops, missing concepts, and failed formal
  validation are repair work and must have `terminal_blocker: null`.
- Only `status: complete` with `final_response_allowed: true`, or one of the
  three explicit terminal conditions above, permits a final response.
- Formal readers must be a deterministic prefix, followed by at most one
  active paper and untouched `queued` papers. Never initialize or modify a
  later paper while an earlier paper is incomplete.

For idempotent reruns: skip a same-source reader bundle only when its `reader_interactive.html` and adversarial audit already pass; resume an incomplete bundle in place; ask only when the existing bundle's immutable source evidence belongs to a different PDF.

`skills/nature-reader/scripts/complete_reader_bundle.py` is a strict **validation/ledger gate**. It does not translate, crop figures, or repair Markdown. Codex must complete `paper.md` and assets before invoking it.
