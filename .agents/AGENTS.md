# Agent Instructions

- Project root: `C:\Users\SSS\Desktop\PAPER`
- Agent context directory: `.agents/`
- Learner memory directory: `.agents/reader-learner/`

## Operating Rules

- Treat this project as a local research-paper library plus a Codex skill chain for bilingual reading, AI/quantum news briefings, and learner-profile iteration.
- Treat AI/quantum daily briefings as a second entry point into the same learner-profile system, not as a separate memory store.
- Prefer verified repository files over chat history.
- Do not fabricate paper metadata, commands, skill behavior, or learner-profile facts.
- Preserve original PDFs and source reader bundles unless the user explicitly asks to reorganize or overwrite them.
- Keep the roles inside `.agents/` clear:
  - root Markdown files are project-agent documentation;
  - `reader-learner/knowledge_profile.json` is user learning data.
- Treat `reader-learner/knowledge_profile.json` as schema v2 learner memory: stable concept IDs belong in `concepts`, raw feedback belongs in `events`, source metadata belongs in `sources`, and scheduling belongs in `review_queue`.
- Do not store full selected text, long sentence excerpts, or user questions as concept keys.
- Use `reader-learner` scripts or explicit user direction before mutating `.agents/reader-learner/knowledge_profile.json`.
- Except for permitted personal learner-profile reads/updates, do not open, print, copy, summarize, upload, or modify any file that appears to contain keys, passwords, tokens, credentials, API secrets, certificates, private keys, cookies, or session data.
- Remember that interactive HTML feedback is not auto-persisted. It exists in page memory until the user clicks `Download feedback JSON` or `Copy feedback for Codex`.
- For document/code edits, keep changes tightly scoped and verify with the smallest relevant command.
- For generated reader outputs, report exact output paths and warnings.

## Project-Specific Boundaries

- PDF files and topic/year folders are source corpus data. Avoid bulk renames, moves, deletes, or compression without approval.
- `*_reader/` folders are generated reader bundles. They may be regenerated, but preserve `paper.md`, `source_map.json`, and `translation_notes.md` unless replacing them intentionally.
- Formal reader HTML must be generated from the normalized llm-wiki layer under `reader_wiki/`, not directly from dirty extraction text. The required middle-layer files are `reader_manifest.json`, `concept_ledger.json`, `formula_ledger.json`, `figure_table_ledger.json`, `algorithm_ledger.json`, `claim_contribution_ledger.json`, `annotation_metadata.json`, `structure_validation_report.json`, and `normalized_reader.md`.
- If `structure_validation_report.json` fails, do not write or report `reader_interactive.html`. Fix the bundle first.
- `skills/reader-skill` owns reader-specific Markdown parsing, translation validation, source anchors, and learner-profile annotation metadata; reusable HTML shell, feedback UI, and export controls should be delegated to `skills/utils/lean-html-skill`.
- `skills/reader-learner` owns learner profile mutation.
- `skills/reader-learner` must validate feedback schema, normalize concept names/aliases/notes, fail fast on mojibake/control characters/HTML fragments, and atomically replace `knowledge_profile.json` only after validation succeeds.
- `skills/read-feedback-skill` owns post-reading Markdown and HTML explanation reports from exported feedback and the updated learner profile.
- `skills/ai-quantum-news-briefing` owns AI/quantum briefings and may bridge explicit news feedback into `reader-learner`.
- `skills/utils/lean-html-skill` owns shared HTML shell/post-processing, reusable feedback UI, browser-memory/localStorage behavior, and feedback2 export controls. Prefer calling it when a domain skill needs reusable HTML/feedback UI, including future `reader-skill` HTML output work.
- `skills/utils/init-knowledge-profile` owns reviewable initialization/extension of the learner/person profile from exported GPT conversation files. It must use collect/extract/propose/apply stages and avoid direct unreviewed profile mutation.
- News explanation HTML should show the knowledge boundary as a layered map: `Source Claim -> Theme Clusters -> Mechanism / Evidence -> Profile Loop`, with category cards and status bars instead of one long horizontal node chain.
- For news briefings, never infer mastery from exposure alone. Use `unrated` for exposure-only keyword records, and use `known` / `mastered` / `learning` / `unknown` only when the user explicitly marks or states that status.
- For recurring daily briefings, use `news/_index/story_index.jsonl` and `skills/ai-quantum-news-briefing/scripts/news_delta.py` so the report is delta-first: expand only new/material-update stories, compress or skip recently seen stories, and keep category as an item tag rather than repeating full category sections.
- `skills/nature-reader` owns full-paper Markdown reader generation from source papers.
- Treat `reader_interactive.html` as a completed end-to-end reader artifact: every substantive `**Original:**` block must have faithful `**中文:**` translation, useful `**注释:**` logic/knowledge/formula/figure guidance, strict validation, feedback UI, and learner-profile annotations when available.
- Never generate or report HTML from extraction-only drafts, summaries, placeholders, or bypass flags. The paper pipeline has one formal HTML target: fully validated `reader_interactive.html`.
- When the user asks to regenerate, translate, or finish a formal paper reader, Codex must perform the translation pass directly. Do not search for or require local/third-party translation models, SDKs, packages, or services as the default path; missing translation tooling is not a blocker.
- A formal reader also requires inspectable figure/table cards, LaTeX-readable formulas, and block-specific notes. Caption-only figure text, raw PDF formula noise, whole-page screenshot links, image-object lists, or generic note scaffolds are draft artifacts.
- Algorithms are first-class paper objects like figures and tables. Do not summarize them; render a full algorithm card with original numbered steps and Chinese numbered steps.
- Source Page Index links are first-class navigation aids. Keep their `href` values as plain relative file paths such as `assets/source_pages/page-01.png`; math wrapping, concept highlighting, or HTML markup inside `href` is a hard failure.
- `Copy feedback for Codex` must not depend only on clipboard permission. The HTML must populate a visible fallback textarea with the export JSON whenever copy is requested.
- Every formal reader generation must pass the adversarial HTML audit before being reported as successful.
- `reader_feedback.json` files are handoff artifacts between reader HTML and `reader-learner`; they are not the long-term profile.

## Commands Worth Knowing

| Purpose | Command |
|---|---|
| Convert reader bundle to HTML | `python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\scripts\markdown_reader_to_html.py <reader-dir>` |
| Test reader end-to-end contract | `python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\tests\test_reader_e2e.py` |
| Audit generated reader HTML | `python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\tests\adversarial_html_audit.py <reader-dir>` |
| Convert news briefing to feedback HTML | `python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py --config <news_feedback_config.json> --output <briefing_reader.html>` |
| Build delta-first news config | `python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\news_delta.py apply --config <candidate_news_feedback_config.json> --output <delta_news_feedback_config.json> --date <YYYY-MM-DD> --days 7 --continuing-mode one-line --update-index` |
| Import HTML feedback | `python C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\import_reader_feedback.py --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json --feedback <reader_feedback.json>` |
| Import news feedback | `python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py --feedback <news_feedback.json> --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json` |
| Generate feedback explanations | `python C:\Users\SSS\Desktop\PAPER\skills\read-feedback-skill\scripts\build_feedback_explanation_report.py --feedback <reader_feedback.json> --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json` |
| Attach feedback2 HTML panel | `python C:\Users\SSS\Desktop\PAPER\skills\utils\lean-html-skill\scripts\lean_html.py attach-feedback --html <report.html> --feedback <reader_or_news_feedback.json>` |
| Initialize profile from chat sessions | `python C:\Users\SSS\Desktop\PAPER\skills\utils\init-knowledge-profile\scripts\init_knowledge_profile.py collect --input <chat_export_or_folder> --output C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions` |
| List learner profile | `python C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\update_learner_profile.py --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json list` |
| Review learner queue | `python C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\update_learner_profile.py --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json review` |
| Migrate learner profile to v2 | `python C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\migrate_knowledge_profile_v2.py --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json` |
| Validate reader-skill | `python C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\SSS\Desktop\PAPER\skills\reader-skill` |
| Validate reader-learner | `python C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\SSS\Desktop\PAPER\skills\reader-learner` |
| Validate read-feedback-skill | `python C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\SSS\Desktop\PAPER\skills\read-feedback-skill` |
| Validate ai-quantum-news-briefing | `python -X utf8 C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing` |
| Validate lean-html-skill | `python -X utf8 C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\SSS\Desktop\PAPER\skills\utils\lean-html-skill` |
| Validate init-knowledge-profile | `python -X utf8 C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\SSS\Desktop\PAPER\skills\utils\init-knowledge-profile` |

## Verification Expectations

- For Python script changes, run `python -m py_compile <script>`.
- For learner-profile schema changes, compile `profile_v2.py`, `import_reader_feedback.py`, `update_learner_profile.py`, and `migrate_knowledge_profile_v2.py`.
- For skill metadata/instruction changes, run `quick_validate.py` on the changed skill folder.
- For reader HTML changes, regenerate at least one reader bundle and check for:
  - `Original` and `中文` block counts;
  - image rendering or missing-image warnings;
  - feedback controls;
  - MathJax script when formula rendering is enabled;
  - learner profile annotations when a profile exists.
- For formal `reader_interactive.html`, also run `adversarial_html_audit.py <reader-dir>`. It must check Algorithm cards, Source Page Index link integrity, MathJax/formula rendering, concept mark metadata, feedback export fallback, and Save-mark panel closing.
- For reader pipeline changes, run `python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\tests\test_reader_e2e.py`; it must prove valid readers build and incomplete translation/structure fails.
- For reader-learner safety changes, run `python C:\Users\SSS\Desktop\PAPER\skills\reader-learner\tests\test_profile_safety.py`; it must prove UTF-8 JSON writes, schema validation, concept normalization, and fail-fast behavior.

## Approval Rules

Ask before:

- deleting or moving PDF corpus directories;
- overwriting `.agents/reader-learner/knowledge_profile.json` wholesale;
- running long OCR, large PDF extraction, model downloads, or network-heavy tasks;
- changing the semantics of learner status values.

Never open, print, copy, summarize, upload, or modify suspected credential material. This includes files or paths containing names such as `.env`, `secret`, `secrets`, `credential`, `credentials`, `token`, `password`, `passwd`, `apikey`, `api_key`, `private_key`, `id_rsa`, `.pem`, `.p12`, `.pfx`, cookies, or session stores.
