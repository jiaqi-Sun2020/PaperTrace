# Figure, table, and pseudocode extraction

Open this reference when extracting and placing figures, tables, algorithms, procedures, or pseudocode. It expands step 5 of the reading workflow.

## Placement near the relevant discussion

Do not try to recreate the PDF pixel-for-pixel. Preserve semantic proximity instead.

Default placement rule:

- crop each figure/table into `assets/` and show it near its first substantive mention in the body text
- keep the caption attached to the figure/table
- show both original caption and Chinese caption translation
- if the caption contains critical details, keep caption and figure together
- if a table is central to the claim, keep it near the paragraph that interprets it
- if a figure/table appears before the body discussion in PDF layout, still place it where it best supports the reading flow and add `Placed near: p.X SYYY`
- if a later section mentions the same figure/table again, link back to the already inserted figure/table block instead of duplicating it

If the paper has a complex multi-column layout, prefer a clean reading layout over exact visual mimicry.

Caption-only extraction is not enough for a final reader. If `source_map.json` records a figure, table, or algorithm/pseudocode object, the final `paper.md` must contain a corresponding visual card, semantic/tight-crop table card, or compiled-LaTeX algorithm card. Use a clearly marked draft only when this cannot be completed yet.

## Object inventory and provenance

Keep raw source object identity immutable in `source_map.json`. Store all derived facts in `reader_wiki/object_inventory.json`, one row per `F###`, `T###`, and `A###`:

- figure: tight `asset_path`, source-page `bbox`, and `representation: tight_crop`
- table: `representation: semantic_table` or `tight_crop`; a semantic table is preferred when cells can be recovered faithfully
- algorithm/pseudocode: `representation: latex_compiled_algorithm`, with source block pointer, `.tex`, `.svg`, compile manifest, hashes, engine, and source/compiled numbered-step parity

The inventory must be bound to the current source-map hash. A full-page image is provenance evidence, never an object crop.

## Crop figures and tables tightly

When extracting a figure or table image:

- crop only the figure or table content area, not the whole page
- use the smallest rectangle that fully contains the visual object
- exclude page headers, footers, surrounding prose, and unrelated margins
- keep the caption separate unless the caption is part of the requested visual crop
- if the crop box is uncertain, mark it as approximate instead of enlarging it

Precision matters more than convenience here. A slightly smaller but correct crop is better than a wider crop that includes unrelated page content.

## Figure/table block shape

Figure/table blocks in `paper.md` should use this shape:

```markdown
<a id="F001"></a>
### Fig. 1. [short translated title]

**Placed near:** p.3 S012
**Source:** p.4 C001

![Fig. 1](assets/fig1.png)

**Original caption:** [caption text]

**中文图注:** [caption translation]

**Reading note:** [brief explanation of what to inspect in the figure]
```

For a table, include a faithful Markdown pipe table when cells can be recovered; otherwise use a tight table crop and say so in the reading note. For an algorithm or pseudocode object, use:

```markdown
<a id="A001"></a>
### Algorithm 1. [title]

**Source:** p.5 A001

**Algorithm LaTeX:** `assets/algorithms/A001.tex`

**Compiled algorithm:** `assets/algorithms/A001.svg`

**Compile manifest:** `assets/algorithms/A001.compile.json`

**Reading note:** [what the control flow or invariant establishes]
```

The LaTeX must preserve the full source algorithm, including Require, Ensure,
and every numbered executable statement. Keep the body in the source language;
Chinese is allowed only inside `\Comment{...}` for comments that exist in the
source. Compile with XeLaTeX and publish the verified SVG. A translated body,
prose paraphrase, summary, missing step, or uncompiled snippet fails.
