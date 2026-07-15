# Core Principles

Use this skill to turn a research paper into a complete Markdown reading artifact. The default output is a source-grounded Chinese-English paper reader, not a summary.

## Required Internal State and Final Output

Treat the Markdown bundle as internal evidence, not the PDF-to-HTML deliverable. When the request asks for interactive HTML, continue until `reader_interactive.html` exists and the publishing adversarial audit passes; only that audited HTML is the final user-facing artifact.

- Keep extractable prose, paragraph structure, section flow, equations, units, citation markers, and hedging.
- Show original text and faithful Chinese translation together at block level.
- Extract figures and tables as assets and place them near their first substantive mention or interpretation point.
- Keep captions attached to figures/tables with English caption text and faithful Chinese caption translation.
- Preserve stable page and block anchors for traceability.
- Write `paper.md`, `source_map.json`, `translation_notes.md`, and `assets/` by default.
- Use those files to generate and formally audit `reader_interactive.html`; do not stop or report success at the bundle stage.

## Translation Rule

Translate faithfully at paragraph/block level. The `**中文:**` field must be a translation of the matching `**Original:**` field.

The current-session primary model must directly author every block-level Chinese translation, block-specific note, and LaTeX reconstruction. Do not delegate those semantic fields to an offline translator, external API, local model, secondary model, or script. Tools may extract evidence, validate, compile, and render, but are not content authors. This is product-neutral and does not depend on a particular agent brand.

Do not put any of the following in `**中文:**`:

- paragraph summaries;
- "Chinese meaning" notes;
- reading scaffolds;
- terminology-only hints;
- paper-logic explanations;
- physical or mathematical commentary;
- annotation guidance;
- labels such as `中文译意`, `非逐句精翻`, or `待忠实翻译`.

Put interpretive material in `**注释:**` instead. If no faithful translation exists yet, label the bundle as draft in `translation_notes.md` and do not present it as a final bilingual reader.

Do not leave generic note scaffolds in final output. A note must say what this specific block does in the paper. Phrases like `这一块用于定位原文、公式、图表或实验论证` or generic feedback instructions are draft scaffolding and must be removed before final HTML.

Figures, tables, and formulas are first-class reading objects. Final output must include tight figure/table crops or semantic tables with translated captions, and formulas must be reconstructed as LaTeX display math rather than raw PDF extraction noise.

Formula rendering is bilingual evidence, not decoration. Within one source
block, Original and Chinese must expose the same ordered LaTeX components with
the same inline/display presentation. Keep headings outside the language
fields so both panels retain the same block boundary.

Formula rendering is bilingual evidence, not decoration. Within one source
block, Original and Chinese must expose the same ordered LaTeX components with
the same inline/display presentation. Keep headings outside the language
fields so both panels retain the same block boundary.

Formula rendering is bilingual evidence, not decoration. Within one source
block, Original and Chinese must expose the same ordered LaTeX components with
the same inline/display presentation. Keep headings outside the language
fields so both panels retain the same block boundary.

## Block Shape

Each substantive source block should have a stable anchor and a visible bilingual pair:

```markdown
<a id="S001"></a>
**Source:** p.1 S001

**Original:** [source paragraph]

**中文:** [faithful Chinese translation]

**注释:** [optional reading guidance, logic notes, formula checks, or knowledge-point summaries]
```

## Non-Negotiable Defaults

When the user asks for paper translation, reading, `nature-reader`, `中英文对照`, `原文对照`, `全文翻译`, or `翻译解读`, produce a paragraph-level bilingual reader by default.

Do not replace the reader with:

- a Chinese-only summary;
- a paper review without original/translation alignment;
- figure captions without figure/table crops;
- a list of key points detached from source locations;
- only the abstract, introduction, or selected highlights.

If constraints prevent full processing, still create a draft reader and clearly label missing pages, missing figures/tables, untranslated blocks, or low-confidence OCR/crops in `translation_notes.md`. Do not silently downgrade to summary mode.

## Reader Value

The reading file should help a reader move between:

- original text;
- faithful translated text;
- source location;
- figure or table evidence;
- optional explanatory notes.

Good output feels like a paper reader, not a machine-translation dump and not a summary. It lets a reader inspect where each claim came from and how it connects to nearby figures, tables, and equations.

## Copyright Caution

For copyrighted publisher PDFs, keep chat responses short and point to the local artifact. In local `paper.md`, include the bilingual reader only for the user-provided source file or clearly lawful open-access content; avoid reproducing large copyrighted text directly in chat.
