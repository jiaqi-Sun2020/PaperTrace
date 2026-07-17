# Output Contract

## Final deliverable

- `reader_interactive.html` is the only user-facing completion artifact for an interactive HTML request.
- Require `reader_wiki/structure_validation_report.json` and `reader_wiki/formal_artifact_manifest.json` to report `pass` before returning it.
- Never return a reader bundle, Markdown path, extraction ledger, or preview HTML as completion.

## Internal build and evidence artifacts

- `paper.md` for the full-paper Markdown artifact.
- `source_map.json` for stable source anchors.
- `translation_notes.md` for terminology, uncertainty, completion blockers, and layout notes.
- `assets/` for extracted figures, tables, page previews, or cropped snippets when needed.
- `reader_wiki/` for completion, normalization, concept, formula, object, and audit ledgers.

`source_map.json` is immutable evidence. `reader_wiki/object_inventory.json` is the mutable derived-object contract: it binds every figure, table, and algorithm/pseudocode ID to crop/representation provenance without mutating source evidence. `reader_wiki/preflight_manifest.json` must pass before formal HTML generation.

For PDF input, distinguish raw evidence from the completed bundle: `extract_pdf_bundle.py` produces the immutable source map, raw pages, source-page images, and embedded-image objects, then automatically materializes a UTF-8 working `paper.md` with explicit incomplete-state markers. `materialize_reader_markdown.py` provides the same no-overwrite transition for legacy bundles. Replace every marker with source-grounded content, run `audit_reader_text.py`, and only then run completion. Rebuild damaged text from source evidence; do not remove corruption markers or weaken validation.

Do not hide missing information. If source extraction, translation, OCR, formulas, figures, or tables are incomplete, record the blocker in `translation_notes.md` and continue the completion pass before HTML generation.

## Markdown Contract

Each substantive block should use:

```markdown
<a id="S001"></a>
**Source:** p.1 S001

**Original:** English source text.

**中文:** Faithful Chinese translation of the Original block.

**注释:** Optional paper logic, knowledge-point summary, formula check, figure note, or reader guidance.
```

Bibliography uses a separate original-only shape and is explicitly excluded from translation:

```markdown
<a id="R001"></a>
**Source:** p.12 R001

**Reference list (original only):** [1] Author, Title, Venue, Year.
```

Rules:

- `**中文:**` is translation only. It must not contain summaries, reading scaffolds, terminology-only notes, `中文译意`, `非逐句精翻`, or `待忠实翻译`.
- `**注释:**` is the place for article logic, knowledge-point summaries, physical/mathematical role, figure notes, formula verification notes, and annotation guidance.
- Preserve formulas, citation markers, numbers, units, symbol names, and source order.
- Preserve one-to-one presentation objects inside the pair: Original and
  Chinese must have identical ordered LaTeX component signatures, including
  inline/display kind. Field-local Markdown headings and one-sided math
  components are hard failures.
- Make each display an atomic logical formula. Split independent equations into separate displays; `split`/`multline` may only wrap one formula. Packed `\quad`/`\qquad`, `align`/`gather`, literal `\n`, and prose equations duplicated by a display are hard failures.
- Preserve a one-to-one mapping between substantive source-map rows and bilingual blocks. `**Source:**` must name exactly the block's own stable ID; ranges, overlaps, missing IDs, and summary compression are hard failures.
- Keep `**Original:**` source-faithful and reader-ready. Immutable raw extraction stays in `source_map.json`/`raw/pages`; formal Original repairs line breaks, columns, headings, lists, and formulas without paraphrase, synthesis, omission, or summary.
- Formula source blocks require LaTeX in Original as well as faithful Chinese. A combined formula count cannot hide an empty English formula layer.
- Normalize Original layout before semantic completion. No script may copy LaTeX from Chinese into Original, and no normalizer may mutate `paper.md` after a completion ledger exists.
- `R###` bibliography blocks must contain `Reference list (original only)` and must not contain `**中文:**`; the HTML renderer must show them as a single original-language panel.
- Full papers require a completion-authored `reader_wiki/concept_candidates.json`; reject equation labels, section numerals, layout words, generic uppercase matches, missing Chinese aliases, and template explanations.
- Validate PDF coverage independently at raw-page level; a source map cannot certify only itself.
- Every formal figure, table, and algorithm ID must have an immutable source-map row and a non-empty evidence hash.
- Every registered figure, table, and algorithm/pseudocode must also have a matching object-inventory row and Markdown card. Figure crops require a local asset and source-page bounding-box provenance; tables require `semantic_table` or `tight_crop`; algorithms require `latex_compiled_algorithm` with a complete source-language `.tex`, verified `.svg`, compile manifest, hashes, engine, and source-matching numbered-step count. Chinese may appear only in translations of actual comments.
- If a block cannot be translated faithfully yet, keep it out of final HTML generation and record the reason in `translation_notes.md`.
- Require `translation_notes.md` to declare `Content authorship: current-session-primary-model`, `External translation backend: none`, and the three directly authored fields `chinese_translation`, `block_specific_notes`, and `latex_reconstruction`. Formal completion fails without this product-neutral provenance.

## Pre-Response Verification

Before final response, verify:

- `reader_interactive.html` exists, is non-empty, and was generated after the latest internal bundle changes.
- `reader_wiki/structure_validation_report.json` has `status: pass`.
- the publishing adversarial audit exits zero and `reader_wiki/formal_artifact_manifest.json` has `formal_status: pass`.
- `paper.md` contains matching `**Original:**` and `**中文:**` block pairs.
- Every `**中文:**` block is a faithful translation of its matching `**Original:**` block, not a paragraph summary or reading scaffold.
- Every image/table link used in `paper.md` exists under `assets/`.
- Every figure/table in `assets/` has a corresponding Markdown block and source pointer.
- Every source-map figure, table, and algorithm/pseudocode object has exactly one completed Markdown card and an `object_inventory.json` row; do not let an empty source category bypass validation.
- PDF-derived figure-caption blocks include a visible extracted image or cropped figure asset near the caption when a reliable asset exists.
- Do not use a full PDF source-page image as the primary inline figure. Full page previews should remain provenance links, source indexes, or collapsible/source-check material.
- If no reliable crop exists, keep the caption and source-page link instead of embedding the whole PDF page as a figure substitute.
- Formula-heavy PDF-derived blocks include reconstructed LaTeX display math whenever enough context is available. Preserve extracted PDF text below the reconstruction as evidence, not as the only formula view.
- Formula-heavy PDF-derived blocks include a source-page image link or preview when extraction may have damaged fractions, superscripts, subscripts, spinor brackets, Greek symbols, or custom fonts.
- When a formula cannot be confidently reconstructed, mark it explicitly as not confidently reconstructed and point to the source page image for manual verification.
- When `**注释:**` is present, downstream HTML readers should display it as a separate horizontal notes column on wide screens.
- `source_map.json` parses as JSON and includes source block IDs.
- `translation_notes.md` records skipped, uncertain, incomplete, or low-confidence content that must be resolved before final HTML generation.

## Tooling Guidance

- If the input is a PDF, load the `pdf` extraction route first for selectable text, figures, page previews, and OCR guidance.
- If the user asks for a browser view, use the HTML reader layer only after the Markdown workflow is complete and validated.
- If the user wants citation-level grounding to original text, keep the source map explicit and do not lose page or block IDs.
