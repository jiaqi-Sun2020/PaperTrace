---
name: read-feedback-skill
description: Generate source-grounded research deep-dive reports from reader HTML feedback after reader-learner has imported it into the personal learner profile, including context packs, derivation notebooks, paper-logic reconstruction, evidence-chain analysis, and polished Markdown/HTML outputs. Use when the user has a reader_feedback JSON file and wants real explanation of unclear concepts, formulas, algorithm steps, figure evidence, research claims, paper-specific derivations, or innovation logic using the updated `.agents/reader-learner/knowledge_profile.json` boundary.
---

# Read Feedback Skill

## Purpose

Turn one exported reader feedback JSON file into a source-grounded research deep dive. This skill reads:

- `reader_feedback*.json` exported from `reader-skill` HTML;
- `.agents/reader-learner/knowledge_profile.json` after `reader-learner` has imported that feedback;
- the reader bundle's `source_map.json` and `paper.md` when available.

It does not mutate `.agents`. Its generated HTML may include a second-pass feedback panel attached by `skills/utils/lean-html-skill`; that panel only collects browser feedback and exports `reader_feedback2.json` or `news_feedback2.json` manually. Use `reader-learner` for profile updates.

The deterministic script creates a baseline explanation report and a research context pack. The final value of this skill comes from Codex using that context pack to write the actual derivation/research report. Do not stop at canned or template explanations when the user asks for "推导", "研究", "公式", "创新点", "证据链", or "为什么成立".

The HTML output follows the local `research-html-report` design pattern for report content. Reusable HTML shell/feedback-export behavior should be delegated to `skills/utils/lean-html-skill`, not reimplemented here.

## Workflow

1. Locate the feedback JSON. If the user gives a reader directory, prefer the newest `reader_feedback*.json` in that directory.
2. Make sure the JSON has already been imported with `reader-learner` when the user asks for a profile-aware explanation.
3. Read `references/explanation-report-contract.md` before changing the report format or adding new sections.
4. Run the bundled context/report builder:

```powershell
python <skill-dir>\scripts\build_feedback_explanation_report.py --feedback <reader_feedback.json>
```

Useful explicit form:

```powershell
python <skill-dir>\scripts\build_feedback_explanation_report.py --feedback <reader_feedback.json> --profile <project-root>\.agents\reader-learner\knowledge_profile.json --output <reader-dir>\feedback_explanations.md --html-output <reader-dir>\feedback_explanations.html
```

By default, the script writes both:

- `<reader-dir>\feedback_explanations.md`;
- `<reader-dir>\feedback_research_context.md`;
- `<reader-dir>\feedback_explanations.html`.

Use `--no-context` only for quick smoke tests. Use `--no-html` only when the user explicitly wants Markdown only. Use `--no-interactive-feedback` only when the user wants a static report without the `lean-html-skill` feedback2 panel. Use `--mathjax-url none` when HTML must not load MathJax.

5. For research/deep-dive requests, read `<reader-dir>\feedback_research_context.md` and write a new final report:

```text
<reader-dir>\feedback_research_deep_dive.md
<reader-dir>\feedback_research_deep_dive.html
```

The deep-dive report must be authored from the context pack and source blocks. It should not be a rearrangement of the baseline `feedback_explanations.md`.

After authoring the Markdown deep dive, render it:

```powershell
python <skill-dir>\scripts\render_research_deep_dive_html.py --input <reader-dir>\feedback_research_deep_dive.md --output <reader-dir>\feedback_research_deep_dive.html
```

6. The deep-dive report must include:
   - paper logic map: problem -> assumption -> derivation -> algorithm -> evidence -> limitation;
   - derivation notebooks for math/formula feedback;
   - algorithm mechanism traces for algorithm-step feedback;
   - evidence-chain analysis for figure/table feedback;
   - user-specific explanation depth guided by profile status and learning needs;
   - explicit "unsupported / needs source check" notes where the context pack is insufficient.

7. Tell the user:
   - whether profile data was used;
   - how many feedback items were explained;
   - the generated baseline report, context pack, and deep-dive paths;
   - any missing inputs, such as absent `source_map.json`.

## Output Rules

The reports must:

- keep every feedback item, including `known`, `unknown`, `learning`, `unrated`, concept clicks, and free-form annotations;
- preserve selected Chinese or English text, selected language, source excerpt, original context, translation context, and block IDs when present;
- explain the user's unclear point first from first principles, then connect it to the exact paper context;
- include the profile status after iteration, not only the raw feedback status;
- make figure/table evidence understandable, especially what each plot is meant to prove;
- separate "known anchor" items from "needs explanation" items in the summary;
- avoid inventing paper claims that are not supported by `source_map.json`, the feedback JSON, or the profile.

The HTML report must:

- be standalone with embedded CSS;
- include a top summary/header, knowledge-boundary snapshot, evidence matrix, per-item explanation cards, and follow-up questions;
- keep the source-anchor section compact: show only a one-line `来源锚点` summary by default, and keep source title/URL, selected text, excerpts, original context, and translation context inside collapsed details;
- include a profile-aware knowledge-chain flow diagram that connects known anchors to unclear concepts and paper evidence;
- for `source_kind: news_briefing`, render the knowledge chain as a layered news map, not a long horizontal chain: top stats, four stages (`Source Claim`, `Theme Clusters`, `Mechanism / Evidence`, `Profile Loop`), compact category cards, and status bars showing unknown/learning/known distribution;
- for unknown, learning, or unrated items, explain the physical meaning in detail before giving the paper-specific role, using the learner profile to decide where to slow down;
- for both known and unknown items, derive the role from mathematical-physics structure whenever possible: start from equations, operators, residuals, RDM definitions, unitary generators, measurement estimators, or evidence equations before giving prose conclusions;
- avoid duplicate per-item sections; the physical-meaning section should explain intuition and paper role, while the derivation section should provide non-overlapping equation/logic steps. Do not repeat the same core/paper/watch bullets as a second "supplemental explanation" block;
- render formulas in readable equation panels with MathJax-compatible display blocks instead of leaving formula-heavy text as cramped inline source;
- keep table headers readable with normal casing and `letter-spacing: 0`;
- be responsive and print-friendly;
- load MathJax only through the configured `--mathjax-url`, with source text still readable if MathJax is unavailable.

The research deep-dive must not:

- rely on `CONCEPT_EXPLANATIONS` or `BLOCK_EXPLANATIONS` as final reasoning;
- explain only by dictionary definitions;
- skip derivation steps with phrases like "obviously", "by theory", or "the paper says";
- treat learner profile notes as paper evidence;
- invent missing equations, claims, or experimental results.

## Relationship To Other Skills

- `reader-skill`: creates the interactive HTML and exports feedback JSON.
- `reader-learner`: imports feedback and updates the long-term learner profile.
- `read-feedback-skill`: generates the post-reading explanation report from the exported feedback and updated profile.
- `lean-html-skill`: owns shared HTML post-processing, especially second-pass `reader_feedback2.json` / `news_feedback2.json` export controls.

## Quality Checklist

Before finishing:

1. `reader_feedback*.json` parses successfully.
2. The learner profile was found or the final response explicitly says it was missing.
3. The output report contains the same number of item sections as feedback items.
4. Free-form annotations retain selected text and bilingual context when available.
5. Figure annotations cite their figure/caption IDs.
6. `feedback_research_context.md` exists unless `--no-context` was used.
7. For research/deep-dive tasks, `feedback_research_deep_dive.md/html` exist and contain actual derivations/evidence analysis.
8. HTML output exists unless `--no-html` was used.
9. If interactive feedback is enabled, HTML contains the `lean-html-skill` feedback2 panel.
10. `python -m py_compile` passes for the report builder.
11. `python -m py_compile` passes for the deep-dive HTML renderer.
12. `skill-creator` quick validation passes for this skill directory.
