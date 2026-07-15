# Reading workflow

Run these eight steps for any paper-reading job. The object inventory is completed before translation; validation happens once the whole bundle is ready, not as a sequence of user-visible partial handoffs.

## 1. Identify the source and paper type

The source-format fragment loaded for this job covers how to extract from the specific input. At a high level, also identify the paper type so you know how tightly to couple text, figures, and captions:

- discovery or mechanism paper
- methods or algorithm paper
- resource or dataset paper
- conference paper
- review or perspective

## 2. Build a full-document source map before translating

If the user provides a full paper, process the entire document. Do not stop at the abstract, introduction, or a few representative pages unless the user explicitly asks for a preview.

Create stable IDs for source blocks:

- `S001`, `S002`, ... for body text
- `C001`, `C002`, ... for captions
- `F001`, `F002`, ... for figures
- `T001`, `T002`, ... for tables
- `A001`, `A002`, ... for algorithms, procedures, and pseudocode
- `R001`, `R002`, ... for bibliography-only source blocks

For each block, capture: page number, block type, original text, translation, reading-order index, nearby figure or table references, first substantive figure/table mention when applicable, and confidence level when extraction is uncertain.

Keep the source map stable so later questions can point back to the same IDs. For long papers, add a page index so the reader can jump across the whole document without losing location.

Create `reader_wiki/object_inventory.json` from the immutable source-map objects before authoring content. It is the only mutable record for tight-crop paths, source-page bounding boxes, semantic-table representation, and algorithm/pseudocode representation. Do not add derived crop paths to `source_map.json` after extraction.

## 3. Translate conservatively

Translate every extractable substantive block with these rules:

- write faithful Chinese translation in `**中文:**`; do not write paragraph summaries, reader hints, or terminology lists there
- write logic hints, physical/mathematical interpretation, formula checks, and annotation guidance in `**注释:**`
- preserve technical terms unless a standard Chinese equivalent is clearly better
- keep gene names, protein names, formulas, model names, and symbols intact
- have the current-session primary model directly author every Chinese translation, block-specific note, and LaTeX reconstruction; do not delegate these semantic fields to local/third-party translators, secondary models, or scripts
- keep citations, superscripts, subscripts, and numeric values unchanged
- do not collapse methods details into vague prose
- keep paragraph order and section order unless the user asks for restructuring
- mark uncertain text instead of guessing when OCR or layout extraction is weak
- keep the source's paragraph form; do not convert dense prose into bullet-point keywords
- do not silently skip Methods, limitations, data availability, code availability, competing interests, or extended captions
- if the paper is too long for one pass, write `paper.md` incrementally by page/section and mark pending blocks rather than switching to summary mode

Bibliography is not an extractable bilingual block: preserve every `R###` item with the `Reference list (original only)` shape. Never place a Chinese translation field beside a reference-list item.

If a sentence contains multiple claims, keep the translation readable but do not split away the original evidence chain. Build the Terminology Ledger (`../../../_shared/core/terminology-ledger.md`) as you translate so recurring terms stay consistent across the whole document.

Before considering a section final, remove generic note scaffolds. `**注释:**` must be specific to the section, figure, table, formula, or claim; it must not repeat a template such as "this block locates original text/formula/table" or generic instructions to annotate in HTML.

Before completion, record the required current-session authorship declarations in `translation_notes.md` exactly as specified by `SKILL.md`. A missing declaration, any external translation backend, or an incomplete directly-authored field list is a hard failure.

## 4. Normalize Original layout before semantic completion

Run mechanical Original-layout normalization before the direct semantic pass. It may repair PDF line wrapping but must not import LaTeX from the Chinese column or overwrite reviewed Original text. Reconstruct every formula-source block's LaTeX directly in `Original`; after the completion ledger exists, no normalizer may mutate `paper.md`.

## 5. Extract and place figures, tables, and algorithms/pseudocode near the relevant discussion

Crop each figure/table into `assets/` and place it near its first substantive mention, keeping the caption attached with both original and Chinese caption text. Render every algorithm/procedure/pseudocode as matched original and Chinese numbered steps, not a prose summary. Record the exact representation and provenance in `reader_wiki/object_inventory.json`. For the full placement and tight-crop rules, and the object-card shapes, open `references/figure-extraction.md`.

Do not treat a caption-only text block, image-object list, or prose algorithm summary as a completed source object. The final `paper.md` must contain a visual figure card, semantic/tight-crop table card, and structured algorithm/pseudocode card for every registered object.

## 6. Generate the internal Markdown evidence file

Build a full-paper `paper.md` as an internal pipeline artifact. It must include:

- metadata header
- a short page/section index
- page-level or section-level divisions for long papers
- paragraph-level original/Chinese pairs for all extractable substantive text
- figure and table blocks placed near the relevant discussion
- full algorithm/pseudocode blocks placed near the relevant discussion
- original-only bibliography blocks for `R###`
- source anchors on every substantive text, figure, caption, and table block
- a terminology table for recurring technical terms (from the Terminology Ledger)
- a short `阅读提示` / `critical reading notes` section only after the bilingual body, not as a replacement for it
- short uncertainty notes only when extraction is weak

Do not add an interactive Q&A panel or follow-up widget to Markdown. Do not report `paper.md` or the bundle as the result of an HTML request. Browser output belongs to the validated `reader_interactive.html` step after the Markdown bundle is fully translated and structurally complete.

## 7. Preflight, generate, and audit the final interactive HTML

Run `preflight_reader_bundle.py`, the completion ledger, normalized reader compilation, HTML converter, and publishing adversarial audit in sequence. Preflight must show that every registered figure, table, algorithm/pseudocode, bibliography shape, and formula has its required evidence before HTML is attempted. The pipeline succeeds only when `<reader-dir>/reader_interactive.html` exists and the adversarial audit exits zero. A passing bundle or ledger is intermediate state, not a deliverable.

## 8. Answer follow-up questions with source grounding

When the user asks a question after the file is created, answer from the paper, not from memory, and cite exact block IDs and page numbers. For the full grounding rules, open `references/grounding-rules.md`.
