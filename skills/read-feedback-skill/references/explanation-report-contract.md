# Explanation Report Contract

Use this reference when generating or changing Markdown/HTML reports or research deep dives from `reader_feedback*.json`.

## Inputs

Required:

- `reader_feedback*.json`: exported by `reader-skill` HTML.

Recommended:

- `.agents/reader-learner/knowledge_profile.json`: updated by `reader-learner` after importing the feedback.
- `source_map.json`: reader bundle source map with stable block, caption, figure, and table IDs.
- `paper.md`: full bilingual reader Markdown.

## Required Report Sections

1. Metadata
   - paper title;
   - feedback path;
   - profile path and whether it was loaded;
   - source map path and whether it was loaded;
   - generation timestamp.

2. Knowledge boundary snapshot
   - counts by feedback status;
   - concepts marked known/mastered;
   - concepts or annotations needing explanation;
   - suggested reading route through the unclear concepts.

3. Per-item explanations
   - one section for every feedback item;
   - feedback status and profile status;
   - annotation kind;
   - source block ID, page, and source type when available;
   - selected text, original context, translation context, or source excerpt;
   - a direct explanation adapted to `confusion_type`:
     - `term_definition`: define the term first;
     - `paper_usage`: explain how the paper uses it;
     - `math_step`: unpack the mathematical move;
     - `algorithm_step`: explain the algorithmic operation;
     - `assumption`: identify what is assumed;
     - `evidence`: explain what figure/table/data supports;
     - `relation`: explain how the selected idea connects to surrounding concepts;
     - `other` or empty: explain from context.

4. Follow-up prompts
   - short questions the user can ask next if a section remains unclear.

## Required Research Deep-Dive Sections

When the user wants derivation, research logic, formulas, innovation analysis, or paper reasoning, the final report must go beyond the baseline explanation report and include:

1. Paper logic map
   - research problem;
   - gap or limitation of prior/naive method;
   - central claim;
   - assumptions;
   - derivation bridge;
   - algorithmic realization;
   - evidence and limitation.

2. Concept dependency graph
   - known anchors from learner profile;
   - unknown/learning blockers;
   - which blockers must be understood before later claims.

3. Derivation notebooks
   - one notebook for each math/formula feedback item;
   - symbols and units;
   - starting premise;
   - transformation steps;
   - conclusion;
   - hidden assumptions;
   - what source block supports each step.

4. Algorithm mechanism traces
   - input state/data;
   - operator/update rule;
   - iteration logic;
   - output/readout;
   - relationship to the paper's derivation.

5. Evidence-chain audit
   - figure/table measured quantity;
   - baseline/reference;
   - claim supported;
   - what the evidence does not prove.

6. User-specific explanation plan
   - explain known anchors briefly;
   - spend depth on unknown/learning facets;
   - convert free-form questions into concrete follow-up study tasks.

## Required HTML Sections

The HTML report should follow the local `research-html-report` style:

1. Hero/header
   - title;
   - one-sentence purpose/claim;
   - feedback item count;
   - needs-explanation count;
   - profile-loaded state;
   - generation timestamp.

2. Knowledge boundary snapshot
   - status cards;
   - known anchors;
   - needs-explanation list.

3. Knowledge-chain flow diagram
   - show the paper reasoning path as compact connected nodes;
   - color/status-code nodes from the learner profile where possible;
   - make the diagram a learning route, not a replacement for paper evidence.

4. Evidence matrix
   - one table row per feedback item;
   - item number, concept/annotation, source block, question type, feedback status, profile status, source-map availability.

5. Per-item explanation cards
   - metadata grid;
   - compact source anchor panels;
   - collapsed full source context for original/translation text when available;
   - profile-aware physical-meaning explanation for unknown, learning, or unrated items;
   - a non-duplicative mathematical-physics derivation section for both known and unknown items where possible;
   - readable formula panels for formula-heavy concepts, derivations, and measurement equations;
   - follow-up question details.

6. Next questions
   - short prompts the user can ask after reading.

For deep-dive HTML, add:

- derivation panels with bright equation blocks and symbol legends;
- claim/evidence matrix;
- mechanism or reasoning-flow diagram using CSS boxes or inline SVG;
- limitation ledger.

HTML must use embedded CSS, semantic HTML, readable tables, normal letter spacing, responsive layout, and print rules.

## Grounding Rules

- Prefer `original_context` and `translation_context` from the feedback item for free-form annotations.
- Do not expose large original/translation context blocks by default in HTML; show concise anchors and keep full context in collapsed details.
- Use `source_map.json` to recover block/caption context by ID.
- Use learner profile entries only as personal state and prior notes; do not treat profile explanations as paper evidence.
- Keep block IDs in the report. Examples: `S016`, `F002`, `C001`.
- If a block ID is missing from `source_map.json`, still explain from the feedback item's selected text/source excerpt and mark the source-map context as unavailable.
- HTML reports may load MathJax for formula rendering, but raw source text must remain readable if MathJax is unavailable. Put important equations in dedicated formula panels rather than cramped inline prose.
- Do not duplicate the physical-meaning section with a second prose explanation block. If additional material is needed, it must add derivation steps, symbol logic, measurement estimators, assumptions, or limitations that are not already stated.
- Known items should still receive a concise mathematical anchor; unknown/learning items should receive slower derivation from equations or operators to the paper-specific conclusion.
- Do not treat hardcoded concept/block explanations from scripts as final reasoning. They are fallback hints only.

## Profile Semantics

Status meaning:

- `mastered`: the user can explain and apply the concept without help.
- `known`: the user understands the concept in this paper's context.
- `learning`: the user partly understands it and benefits from reminders.
- `unknown`: the user needs explanation before reading fluently.
- `unrated`: the concept or selected text has not been judged yet.

Do not downgrade a concept in the report. Report the profile status as data, then focus explanation depth according to that status.
