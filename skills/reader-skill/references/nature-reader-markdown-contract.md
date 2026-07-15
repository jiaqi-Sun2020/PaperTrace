# Nature-Reader Markdown Contract

Use this reference when converting `nature-reader` output to HTML or updating `scripts/markdown_reader_to_html.py`.

## Bundle Shape

```text
paper.md
source_map.json
translation_notes.md
assets/
```

`paper.md` is the primary input. `source_map.json` and `translation_notes.md` are provenance companions and should be linked from the HTML when present.

`R###` bibliography blocks use a separate original-only shape and must not be parsed as bilingual text:

```markdown
<a id="R001"></a>
**Source:** p.12 R001

**Reference list (original only):** [1] Author, Title, Venue, Year.
```

Render this as one `reference-block` / `reference-panel`, never as an `Original`/Chinese pair.

## Core Block Shape

```markdown
<a id="S001"></a>
**Source:** p.1 S001

**Original:** English source paragraph.

**中文:** Faithful Chinese translation of the Original block.

**注释:** Optional paper logic, knowledge-point summary, formula check, figure note, or reader guidance.
```

HTML conversion should render this as one aligned reader block. `Original` and `中文` are the bilingual pair; `注释` is a separate guidance column.

Do not place Markdown headings (`#` through `######`) inside `Original` or
`中文`. Put section headings outside the anchored block. Formula components are
paired objects: both language fields must contain the same ordered LaTeX
expressions with the same inline/display presentation. A one-sided formula
chip or display card is a hard validation failure.
The renderer must not infer additional math components from plain underscores,
superscripts, model names, or variable-looking prose.

## Translation Contract

Final HTML output requires faithful translations. The converter should reject `中文` blocks containing draft/paraphrase markers such as:

- `中文译意`
- `非逐句精翻`
- `待忠实翻译`
- `reading scaffold`
- `translation aid`

There is no draft-bypass HTML route. If any of these markers remain, fix the Markdown bundle before running HTML generation.

## Figure/Table Shape

Figure and table cards should keep image/table, source pointer, caption, translation, and reading note together. Use extracted images or reliable crops. Do not embed a full PDF source page as the primary figure.

Every source-map object must have a matching `reader_wiki/object_inventory.json` row. Figure cards require a tight asset and bbox provenance; tables declare `semantic_table` or `tight_crop`; algorithms/pseudocode declare `structured_steps` or `pseudocode_table` and render matched original/Chinese numbered steps.

## Tables

Simple Markdown pipe tables should become HTML tables. Preserve header text naturally; do not force all caps or wide letter spacing.

## Anchors

Preserve every anchor ID:

- `S###` for text blocks
- `F###` for figures
- `T###` for tables
- `A###` for algorithms/procedures/pseudocode
- `R###` for original-only bibliography blocks
- `C###` for captions when present

These IDs are used for feedback and source-grounded follow-up questions.

## Failure Handling

If conversion cannot confidently parse a block, render the original Markdown segment inside a readable fallback panel and keep its anchor. Do not silently drop text.
