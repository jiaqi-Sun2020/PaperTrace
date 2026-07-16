---
name: nature-reader
description: Build the source-grounded bilingual evidence layer used to produce a final audited interactive HTML paper reader from PDF, DOI, arXiv, publisher HTML, or pasted text. Use whenever the user asks to read or translate a paper, make 中英文对照, 原文对照, 全文翻译, 全文翻译解读, generate an interactive paper HTML, extract figures/tables, or preserve exact source anchors. The bundle is an internal build state; when HTML is requested, continue through reader-skill and adversarial audit instead of reporting the bundle as the result.
---

# Nature Reader

This skill builds the internal source-grounded evidence layer that the HTML stage consumes. It owns extraction, faithful translation, block-specific notes, LaTeX reconstruction, and source mapping; it does not by itself complete an HTML-generation request.

## Final Pipeline Deliverable — Hard Contract

For a natural-language PDF-to-HTML request, establish persistence before
authoring. When Codex goal tools are available, create or resume one
unbudgeted goal covering the selected PDF set. Then make the first
implementation command the `reader-skill` batch controller with
`--agent-continuation`; do not edit `paper.md` before its first contract is
observed. Keep the goal active while `final_response_allowed` is false. An
incomplete-status sentence is commentary followed by more work, never a final
answer.

This skill participates only in **Primary Pipeline 1: Paper Reader HTML**. Keep it separate from **Pipeline 2: AI + Quantum Daily Briefing Release**, **Pipeline 3: Local Chat-to-Profile Import**, and **Pipeline 4: Adaptive Teaching Decision & Evidence Loop**. Paper extraction artifacts must never be routed through the daily-news publisher, chat-profile patch workflow, or teaching-decision workspace.

For a PDF-to-interactive-HTML request, the only user-facing completion artifact is:

```text
<reader-dir>/reader_interactive.html
```

The pipeline is complete only when that file exists, was generated from a passing normalized reader layer, and `tests/adversarial_html_audit.py` exits successfully. A passing extraction, completed `paper.md`, passing completion ledger, or populated `reader_wiki/` directory is not pipeline completion and must never be reported as the requested result.

Use the following files only as internal build/evidence state:

```text
paper_reader/
  paper.md
  source_map.json
  translation_notes.md
  assets/
  reader_wiki/
```

Do not stop, hand off, or ask the user to run the HTML step after these internal files pass. Continue directly through `reader-skill`, write `reader_interactive.html`, run the publishing adversarial audit, and return the HTML path.

## v3 Resumable Completion Override

The formal pipeline no longer trusts a single edited `paper.md` or a legacy
`completion_ledger.json`. Immutable extraction stays in `source_map.json`; all
completion is stored in independently schema-validated, atomic v3 records:

```text
reader_wiki/completion_blocks/<stable-id>.json
reader_wiki/completion_run_state.json
reader_wiki/object_inventory.json
reader_wiki/canonical_reader.md
```

Inventory must include prose, formulas, references, figures, tables, and
algorithms before a formal build. Figures require tight object crops and bbox
provenance; tables require a semantic table or tight crop; algorithms require
matched original/Chinese lines; references stay original-only. The helper
`complete_reader_bundle.py` only seeds/validates this state and may emit
`reader_progress.html`; it cannot create a formal HTML file or fabricate
translation/object content. Use the explicit-directory batch entry point in
`reader-skill` for formal rendering; it snapshots the selected directory's
current PDF paths and hashes under the D: output root.

The `paper.md` body must preserve source order and use stable source anchors:

```markdown
<a id="S001"></a>
**Source:** p.1 S001

**Original:** English source paragraph.

**中文:** Faithful Chinese translation of the Original block.

**注释:** Optional paper logic, knowledge-point summary, formula check, figure note, or reader guidance.
```

Bibliography is a distinct `R###` source type, not bilingual prose:

```markdown
<a id="R001"></a>
**Source:** p.12 R001

**Reference list (original only):** [1] Author, Title, Venue, Year.
```

## PDF Bootstrap and UTF-8 Gate

`scripts/extract_pdf_bundle.py` creates immutable raw evidence and automatically materializes a UTF-8 working `paper.md`. The draft preserves stable source anchors and writes explicit `[translation-required]` and `[block-note-required]` markers. It never creates `reader_interactive.html`, and the markers must fail formal completion.

For a legacy bundle containing `raw_source_manifest.json` but no `paper.md`, run `scripts/materialize_reader_markdown.py <reader-dir>`. It preserves `source_map.json` and refuses to overwrite an existing `paper.md` unless `--force` is explicitly supplied. Then perform the direct translation and structural-completion pass before invoking `complete_reader_bundle.py`.

On Windows, write Chinese Markdown through a UTF-8-safe path. Do not pipe Chinese literals through a default PowerShell code-page here-string into Python or another writer. Run `scripts/audit_reader_text.py <paper.md>` before completion. `complete_reader_bundle.py` enforces the same audit and rejects `U+FFFD`, disallowed controls, mojibake markers, and question-mark replacement patterns. Rebuild corrupted working text from the source map; do not retain it, weaken validation, or generate HTML from it.

## End-To-End Reader Contract

The successful end-to-end output for a paper is not just extracted text. It is:

```text
PDF/source
  -> full source extraction and stable block map
  -> faithful Chinese translation for every substantive Original block
  -> logic, knowledge-point, formula, figure, and reading guidance in 注释
  -> strict validation with no draft markers
  -> reader_interactive.html generated by reader-skill
```

`reader_interactive.html` is the final product and the only HTML artifact in the formal paper pipeline. It must not be produced from placeholder Chinese text, summary-only Chinese text, or reading scaffolds. If extraction or translation is incomplete, keep working on `paper.md` / `source_map.json`; do not generate a preview HTML or report an internal reader bundle as a substitute deliverable.

### Evidence-Coverage Hard Gate

Formal completion requires a one-to-one evidence chain, not merely non-empty bilingual fields:

- Give every substantive `Sxxx` / `Exxx` source row its own Markdown block with the same anchor. Coverage must be 100%; missing, duplicate, overlapping, or range-merged anchors fail completion.
- Keep immutable extraction in `source_map.json` and `raw/pages/`; do not expose line-broken PDF extraction verbatim as the formal `**Original:**`. The reader-facing Original must be a complete, source-faithful normalization: repair columns, paragraphs, dehyphenation, headings, lists, and formulas while preserving every claim and qualifier. Never summarize, paraphrase, or synthesize an English replacement.
- Every source row typed `equation_or_formula` / `formula` must contain reconstructed LaTeX in the Original column itself. LaTeX present only in `中文` does not satisfy completion.
- Mechanical Original normalization happens before semantic completion only. It may repair layout but may not import LaTeX from Chinese or overwrite reviewed Original text; it must refuse to run after a completion ledger exists.
- For a full paper, author `reader_wiki/concept_candidates.json` with paper-specific concepts, exact source anchors/evidence spans, Chinese aliases, types, and non-template explanation notes. Each concept must have one canonical Chinese alias plus the minimal controlled variants that actually occur in completed `中文` blocks (for example, `算符`/`算子` only when both forms are present). The alias list is an evidence-backed rendering vocabulary, not a synonym dump: every listed variant must be traceable to the paper translation, and every translated occurrence corresponding to an English-highlighted concept must be covered. Formula numbers, section numerals, layout tokens, and generic uppercase words are not concepts.
- Bind each completed block to the immutable source row with a source-evidence hash and an Original-fidelity check. An empty hash or low similarity fails completion. Independently compare source-map blocks against every raw PDF page; self-referential `N/N` block counts are insufficient.
- Require every `Fxxx`, `Txxx`, and `Axxx` card to exist in `source_map.json`. If extraction missed an object, repair or regenerate the extraction evidence before completion; never invent an unregistered formal object ID.
- Require an exact `reader_wiki/object_inventory.json` row for every `Fxxx`, `Txxx`, and `Axxx`. Figures need tight local crops plus source-page bbox provenance; tables need `semantic_table` or `tight_crop`; algorithms/pseudocode need `structured_steps` or `pseudocode_table` and matching original/Chinese numbered steps.
- Keep bibliography rows as `Rxxx` and render them original-only. Bibliography text must never be translated into `**中文:**`.
- Require `translation_notes.md` to describe the completed state. Any remaining draft, raw-evidence-only, completion-required, or placeholder status fails completion.
- Store bundle artifact paths in ledgers as bundle-relative paths. Moving a bundle must not leave a formal manifest pointing at a nonexistent previous directory.

Final readers must also satisfy the visual/math contract:

- Every substantive figure/table mentioned in `source_map.json` must appear as a figure/table card near the relevant prose, with a tight crop or semantic Markdown table, original caption, Chinese caption, and a concrete reading note. Every algorithm/procedure/pseudocode must appear as structured bilingual numbered steps, not a summary.
- Important formulas must be reconstructed as LaTeX display math (`\[...\]` or `$$...$$`). Noisy PDF text such as `QKT √ d`, `e−iHt`, or collapsed superscripts/subscripts is evidence only, not final formula rendering.
- Within every bilingual source block, Original and Chinese must contain the
  same ordered formula-component signatures, including inline versus display
  presentation. A formula styled only on one side is incomplete, not an
  explanatory enhancement. Markdown headings are forbidden inside `Original`
  and `中文` fields because they can break aligned panel boundaries.
- `**注释:**` must be block-specific. Do not leave template notes such as `逻辑位置：本文主题是...这一块用于定位原文...` or `标注建议：如果这里有不懂...`.

## Current-Session Content Authorship

The active primary model in the current user-facing session must directly author all semantic completion content: every block-level `**中文:**` translation, every block-specific `**注释:**`, and every reconstructed LaTeX expression. This rule is product-neutral and applies equally in Codex, Claude Code, or another agent environment.

Do not delegate these fields to an offline translator, external translation API, local model, secondary/subordinate model, or deterministic script. Extraction and validation tools may recover raw evidence, crop assets, verify contracts, compile ledgers, and render HTML; they must not fill or claim authorship of the final translation, notes, or LaTeX. If a user explicitly supplies machine-translated draft text, the active primary model must still review and directly rewrite every block before formal completion.

Every completed `translation_notes.md` must contain these exact machine-checkable declarations:

```text
Content authorship: current-session-primary-model
External translation backend: none
Directly authored fields: chinese_translation, block_specific_notes, latex_reconstruction
```

Missing tools such as Ollama, API SDKs, Argos Translate, DeepL, or other model backends are not a reason to stop, downgrade, or report the pipeline as blocked. They are not content authors in this formal workflow. The default path is:

```text
extract source blocks
  -> automatically materialize UTF-8 paper.md with explicit completion markers
  -> the current-session primary model translates every substantive Original block directly
  -> the current-session primary model writes block-specific notes and reconstructs LaTeX
  -> the current-session primary model updates paper.md while preserving immutable source_map.json
  -> update reader_wiki/object_inventory.json with every object crop/representation and provenance
  -> run scripts/audit_reader_text.py on paper.md
  -> run scripts/preflight_reader_bundle.py to expose all remaining object/formula/reference gates in one report
  -> run scripts/complete_reader_bundle.py when the bundle came from a draft extraction helper
  -> validate placeholders are gone
  -> generate reader_interactive.html with reader-skill strict mode
```

Completion pass command:

```powershell
python D:\AI\PaperTrace\skills\nature-reader\scripts\complete_reader_bundle.py <reader-dir>
```

This is a strict validation/ledger step, not a validation bypass. It runs and records the final preflight manifest, then refuses missing figure, table, algorithm/pseudocode, bibliography, or Original-side-LaTeX evidence. It does not remove placeholders, normalize PDF extraction noise, add LaTeX, emit object cards, or translate the paper. The current-session primary model must complete those tasks first, then let `reader-skill` / `reader_wiki_compile.py` decide whether formal HTML may be written.

A `status: pass` response from `complete_reader_bundle.py` certifies only the internal evidence layer. It is explicitly not a successful PDF-to-HTML pipeline result. Immediately run the HTML converter and adversarial audit.

If the paper is too large for one response, continue in batches within the same task and report batch progress. Do not end with partial extraction or preview HTML when the user requested a completed translated reader.

## Folder-Level End-to-End Requests

If the user asks to convert every PDF in a supplied folder to interactive HTML “一篇一篇来”, that sentence is complete execution authority for the entire folder. Process files in a deterministic order and complete one formal reader at a time; after its adversarial audit passes, immediately continue to the next file. Do not wait for a new user message between successful papers.

The bootstrap status `paper_md_materialized_completion_required` is expected, not a terminal result. The current-session primary model itself must replace every completion marker with faithful block-level Chinese, write specific notes, and reconstruct readable LaTeX before validation; tools may crop or semantically reconstruct source figures/tables under its supervision. `complete_reader_bundle.py` is deliberately a validator/ledger writer: it does **not** translate, author notes, reconstruct LaTeX, crop, synthesize cards, or mutate `source_map.json`. A failed ledger is therefore a signal to continue direct completion work, never a final handoff for an end-to-end request.

## Routing Protocol

Follow these steps every time the skill is invoked.

1. Read `manifest.yaml`.
2. Read every path listed under `always_load`.
3. Detect `source_format`:
   - `pdf-text`: selectable-text PDF. Default.
   - `scanned-pdf`: image-only or OCR-required PDF.
   - `html`: publisher or preprint HTML page.
   - `doi-arxiv`: bare DOI or arXiv link that must be resolved first.
   - `pasted-text`: pasted prose or notes with no retrievable original layout.
4. Read only the matching source-format fragment from `manifest.yaml`.
5. Build `paper.md`, `source_map.json`, `translation_notes.md`, and `assets/` according to the loaded fragments and core contract.

Do not apply the reading logic from memory alone. The static fragments are the durable instructions.

## Required Core Files

The manifest always loads:

- `../_shared/core/terminology-ledger.md`
- `static/core/principles.md`
- `static/core/workflow.md`
- `static/core/output-contract.md`

Read optional references only when needed:

- `references/figure-extraction.md`: figure/table cropping and placement.
- `references/output-spec.md`: exact field schema for `paper.md` and `source_map.json`.
- `references/grounding-rules.md`: follow-up answers with source citations.
- `references/article-anatomy.md`: argumentative function labels as reading aid.

## Non-Negotiable Rules

- `**中文:**` must be faithful translation, not a summary or reading scaffold.
- Put logic hints, knowledge summaries, formula checks, and annotation guidance in `**注释:**`.
- A complete PDF pipeline requires both translation and logic/knowledge notes. Text extraction plus placeholders is only an internal intermediate state and is not a completed reader.
- The current-session primary model is the direct author of translations, block-specific notes, and LaTeX reconstructions; do not delegate those fields or treat missing external translation models as blockers.
- Figures/tables must be extracted or reconstructed as inspectable cards; formulas must be rendered as LaTeX; generic template notes are invalid in final output.
- Do not merge multiple source blocks into one polished summary and claim the original ID range. Formal readers require block-level source fidelity and complete coverage.
- Preserve formulas, citation markers, units, source order, and page/block IDs.
- Do not switch to summary mode unless the user explicitly asks for a summary.
- Do not embed a full PDF source page as an inline figure substitute; use reliable extracted images or crops.
- If extraction or translation is incomplete, continue the direct completion pass; do not generate HTML until the bundle passes the final contract.
- Never call `paper.md`, `source_map.json`, `translation_notes.md`, `reader_wiki/`, or a passing completion ledger the final deliverable. For an HTML request, finish and report the audited `reader_interactive.html`.
- Do not mutate `.agents` or `knowledge_profile.json`.

## Relationship To Other Skills

- Use `reader-skill` after this skill to generate `reader_interactive.html` only when all substantive blocks have faithful Chinese translations and the visual/math contract is satisfied.
- Use `reader-learner` after feedback export to update the personal learner profile.
