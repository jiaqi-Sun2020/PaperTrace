# Reading analysis and paper history v1

Read when authoring a new full reader, upgrading an explicitly selected reader,
or validating its logic/history. This extends formal-reader-v3; it never changes
immutable source identity, feedback v2, or learner state.

## Authorship and local logic

The current-session primary model writes each non-reference record's `notes`.
The existing `**注释:**` remains the serialization label; its UI label is
`逻辑分析`. Do not add a competing store for per-paragraph reasoning.

Explain the particular paragraph's question/role, actual objects and premises,
the transition and its rule, and the justified result/boundary or next link.
These are coverage questions, not repeated mandatory headings. Background,
methods, results and administrative declarations need different explanations;
bibliography stays original-only. Do not invent a proof for declarations.
Keep indispensable bridges visible. No total length ceiling applies; fold only
optional detailed calculations, not the reason a conclusion follows.

### Logic visualization v1 (inside notes, not a second content store)

New declarations include `logic_visualization_version: 1`; historical declarations
without it remain compatible. Each substantive record has a small directly
authored diagram before the full prose. Expand important multi-step mechanisms;
use a one-node role card for declarations, not a fabricated proof. References
stay original-only. Never infer causal edges from keywords or sentence order.

Serialize one or more fenced `reader-logic` JSON blocks in `notes`. Each block
has `version: 1`, `kind` (`flow`, `argument`, `comparison`, `role`), descriptive
`title`, `nodes` (`id`, `label`), `edges` (`from`, `to`, `type`, `label`, `basis`),
`conditions` (text list), and valid local `source_anchors`. Relation types are
`sequence`, `data_flow`, `supports`, `contrast`; evidence identity is `source`,
`derivation`, or `teaching`. These labels explain the actual relationship; an
arrow alone is insufficient. Comparison never means physical causation.

Keep the fence on its own line after the Markdown note label. All text and
necessary conditions remain selectable and visible; no image-based text,
online graph service or competing per-block file. Formal compilation rejects
malformed/unknown versions, missing references, unexplained nodes and diagrams
without full explanatory prose. Both rendering paths use the same component.
The complete notes digest binds diagrams and prose to the current self-review.
Removing an upgraded visualization declaration cannot downgrade the contract.

Use object/operation distinctions, early minimal cases and counterfactuals from
logic-chain-tutor as teaching techniques, not an external runtime dependency.
Separate paper facts, derivations and teaching assumptions. Numerical teaching
cases must be labelled, not passed off as measured data. Interpretation belongs
in notes, never in Original or Chinese translation.

Upgrade existing figure/table/formula/algorithm notes rather than adding
another panel: identify observation/input, operation/comparison, result and
which claim it supports or cannot support. Compiled algorithm source language
and immutable source anchors remain unchanged.

## Data and continuation

New bundles declare `reader_wiki/reading_analysis_contract.json` with
`reading_analysis_version: 1`, `required: true`, and source-map SHA-256.
Carry this declaration through derived run state, authoring packets and reader
manifest. Same-source old pass records cannot satisfy a newly declared feature
without its summary/history/review. Historical bundles lacking the declaration
remain readable; do not silently bulk upgrade them.

Paper Summary v2 preserves all v1 sections and adds an ordered `logic_chain`
array of `{role, text, source_anchors}`. Explain question -> gap -> assumptions /
method -> evidence -> justified conclusion -> limits, without forcing a paper
to claim an experiment or proof it did not perform. v1 remains supported.

`apply_reading_analysis.py` consumes primary-authored JSON; it performs only
coverage validation, atomic mechanical copying and compilation, never semantic
generation. Its exact non-reference `notes` map prevents accidental omissions.

## History evidence and display

`reader_wiki/paper_history.json` schema 1 binds `source_map_sha256`,
`checked_as_of`, `status` (`verified`, `partial`, `not_checked`), `nodes`,
`relations`, `searches`, and `gaps`. One current node must always exist, even
when external retrieval fails. Dates are typed preprint/published/revised;
date uncertainty is disclosed instead of invented. Use earliest verified date
only for chronology; chronology never creates an inheritance edge.

Each node has safe ID, strong identity (DOI/arXiv when available; otherwise
source-backed title/authors identity), primary HTTPS URL, typed dates,
`title`, `summary`, `question`, `method`, `advance`, `results`, `limitations`,
and optional local `source_anchors`. Same preprint/published paper is one node.

Edges point from the work making the relationship to its cited/used/extended
work. Types: `cites`, `uses`, `extends`, `tests`, `challenges`, `related`.
Each has explanation and evidence `{url, excerpt, locator, checked_on}` plus
either a current-paper `source_anchor` whose Original actually contains the
quote, or a captured primary source under `reader_wiki/history_sources/` with
path/hash, URL and text matching the quote. A hash proves freshness, not truth.
Similarity, chronology and common authors alone never authorize a successor.

Default investigation follows direct predecessors/successors and necessary
background, not an exhaustive field census. Disclose queries, as-of date,
unreachable sources and scope. No verified successor found is not no successor.
Preserve metric tasks/conditions and never combine incompatible effects into a
cross-paper leaderboard. Historical uncertainty is nonfatal; malformed,
fabricated or stale asserted relations fail validation and must be removed or
repaired rather than displayed as verified.

The first content module after title/controls is one chronological vertical
timeline, then Paper Summary, then the existing reader panels. Every paper's
date, topic and actual contribution are visible without opening a detail;
native inline details retain full titles/dates, methods, effects, conditions
and evidence. All details start closed and may open independently. Timeline
segments express chronology only. Do not create inheritance arrows from dates.
Summary logic_chain is an argument overview, not a physical causal graph.
Respond to actual article-container width: keep three columns only when they
fit; otherwise put analysis below the bilingual pair, then stack on mobile.
Never override the resizable source-pane width. Keyboard, all reader themes,
offline, no-script and print remain readable. No new framework or live AI call.

## First read (reading_scan_version: 1)

New batch declarations require these additions. Historical declarations without
the flag still render with the old fields. Author the fields against the current
paper, in Chinese; do not derive roles from a citation verb or a publication date.

- Each history node has `reading_role: {label, topic, explanation, source_anchors}`.
  Use a short role in this paper (e.g. proof technique, competing baseline, data
  source, conflicting evidence), a short topic, and one sentence explaining the
  use. If one work supplies two roles, say both. Include the current paper with
  its own contribution. If the evidence is external-only, use empty source_anchors
  and `evidence_relation: [from_id, to_id, type]` pointing to the node's verified
  evidence in details. A genuinely unresolved external role uses the literal
  label `关系待核实`, explains the gap and may use an empty anchor list; do not
  infer ancestry. Verified edges and primary evidence remain separate, in details.
- In `paper_summary.json` author `result_brief: {headline, items}`. The headline
  states the main finding (not “results overview”). Each item has `kind`,
  `subject`, `finding`, `scope`, and nonempty `source_anchors`. For `comparison`
  also supply `metric` (what was measured, including units as needed) and
  `baseline` (named comparator/configuration); state direction and magnitude in
  the finding, and conditions such as best case, sample or error in scope.
  For `standalone` omit the baseline; metric is optional. A theorem, null result,
  qualitative finding or proposed protocol is not a speedup: state what is
  supported and, where relevant, what was not tested. No fixed count. Cover each
  distinct principal finding once, not every ablation; use the same metric name
  only for genuinely comparable measures. Don't sort by effect size.
- The authoring helper accepts `result_brief` alongside `logic_chain` or retains
  the one already in the summary. The initial view groups by metric, puts the
  named comparator and scope next to each result, and keeps complete explanations
  and evidence below. For a long list, prioritize the main conclusion in the
  headline/first group; never clip findings just to fit a viewport.
- In the existing dates/metrics and freshness/display review rounds, check each
  label against evidence and read each finding with its comparator. Check desktop
  and narrow article widths; a comparison must not require expanding a disclosure.

## Review boundary

`reading_analysis_review.json` is labelled `self_review`, lists reviewed record
IDs and binds the notes digest, summary and history file hashes. Its eight
rounds record actual note quotations, judgment, result and limitation:
coverage, unsupported premises, object distinctions, historical edges,
dates/metrics, freshness/display, interactions, compatibility/privacy.
Any unresolved contradiction fails. Program checks structure/quotes/freshness,
not beginner comprehension or scientific truth. Real browser and final HTML
audit reports are separate evidence; do not report prose self-review as them.
Missing browser evidence is recorded as `not_run` with a reason and current
HTML hash, never recycled from an older passing report. The formal structural
audit reports browser status separately; `not_run` is not visual acceptance.
