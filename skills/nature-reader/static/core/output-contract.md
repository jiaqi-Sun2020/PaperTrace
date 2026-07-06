# Output Contract

Prefer these outputs:

- `paper.md` for the full-paper Markdown artifact.
- `source_map.json` for stable source anchors.
- `translation_notes.md` for terminology, uncertainty, completion blockers, and layout notes.
- `assets/` for extracted figures, tables, page previews, or cropped snippets when needed.
- `reader_interactive.html` only after the translated Markdown bundle passes the final reader contract.

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

Rules:

- `**中文:**` is translation only. It must not contain summaries, reading scaffolds, terminology-only notes, `中文译意`, `非逐句精翻`, or `待忠实翻译`.
- `**注释:**` is the place for article logic, knowledge-point summaries, physical/mathematical role, figure notes, formula verification notes, and annotation guidance.
- Preserve formulas, citation markers, numbers, units, symbol names, and source order.
- If a block cannot be translated faithfully yet, keep it out of final HTML generation and record the reason in `translation_notes.md`.

## Pre-Response Verification

Before final response, verify:

- `paper.md` contains matching `**Original:**` and `**中文:**` block pairs.
- Every `**中文:**` block is a faithful translation of its matching `**Original:**` block, not a paragraph summary or reading scaffold.
- Every image/table link used in `paper.md` exists under `assets/`.
- Every figure/table in `assets/` has a corresponding Markdown block and source pointer.
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
