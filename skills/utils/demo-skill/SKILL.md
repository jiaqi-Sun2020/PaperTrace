---
name: demo-skill
description: Build or revise polished bilingual project demo pages from verified README and AGENTS contracts. Use when an agent needs to create Chinese and English HTML demos, explain exactly four project pipelines, adapt the bundled GSAP/ScrollTrigger storytelling templates, research current GitHub design references, or audit demo pages before committing or publishing them.
---

# Project Demo Builder

Create a source-traceable Chinese/English demo pair without inventing project behavior. Treat the bundled PaperTrace pages as editable visual templates, not universal project facts.

## Workflow

1. Establish the contract before editing.
   - Find the repository root and read its `AGENTS.md` plus every canonical document it explicitly requires, in order.
   - Read the root `README.md` and the files that own the requested pipeline contracts.
   - Do not inspect credentials or learner/profile data unless the request explicitly requires the approved workflow.
   - Identify the four pipeline names, ordered stages, human interaction points, handoffs, outputs, validation gates, and prohibited shortcuts. Ask only if the sources do not determine which four pipelines to show.
   - For the bundled PaperTrace templates, the canonical four are exactly: (1) Paper Reader HTML, ending at audited `reader_interactive.html`; (2) AI + Quantum Daily Briefing Release, ending at the verified published briefing HTML plus its required release set; (3) Local Chat-to-Profile Import, ending only after human review and backed-up patch application; and (4) Adaptive Teaching Decision & Evidence Loop, whose lesson phase ends at a validated single-topic session and whose profile-return phase requires actual learner performance plus strict feedback import. Do not substitute intermediate bundles, configs, candidates, exposure, or page views as terminal evidence.

2. Research design only when requested.
   - Use the connected GitHub capability or current web search; popularity and repository state are time-sensitive.
   - Prefer maintained, high-signal projects and primary repository/documentation pages.
   - Borrow interaction and information-design principles, not copyrighted source code or branding. Record links near the final design rationale when the user requests attribution.

3. Materialize the templates.

   Run from the target repository root:

   ```powershell
   python .\skills\utils\demo-skill\scripts\create_demo.py --output-dir .
   ```

   The command creates `demo.html` and `demo-en.html` and refuses to overwrite either file unless `--force` is explicitly passed. The source assets are `assets/demo.html` and `assets/demo-en.html`.

4. Replace project-specific content in both pages.
   - Keep the Chinese and English pages structurally equivalent: same sections, four pipelines, stages, claims, links, and interaction model.
   - Use faithful English rather than abbreviated translation.
   - Separate verified behavior from future vision or design analogy.
   - Preserve command paths, filenames, statuses, and hard gates exactly when they are part of the project contract.
   - Update titles, metadata, navigation, language links, accessibility labels, and footer provenance.

5. Adapt the presentation.
   - Keep semantic HTML usable without animation.
   - Use GSAP + ScrollTrigger for progressive scroll choreography; use Lenis only for optional smoothing and MathJax only when formulas need it.
   - Pin CDN versions. Provide readable static and `prefers-reduced-motion` fallbacks when scripts or networks fail.
   - Preserve keyboard focus, adequate contrast, responsive type, and non-overlapping content.
   - Do not let the visual layer alter pipeline semantics, application data, or repository workflows.

6. Audit adversarially.
   - Recheck every pipeline claim against README/AGENTS/source files.
   - Compare the two language pages section by section.
   - Test at desktop `1440x1024` and mobile `390x844`; check horizontal overflow, navigation, language switching, focus visibility, reduced motion, and console errors.
   - If browser testing is unavailable, run static checks and state that visual verification remains outstanding.
   - Keep screenshots, browser profiles, search notes, and QA logs temporary or excluded unless the user explicitly asks to retain them.

7. Prepare repository changes safely.
   - Inspect Git status and ignore rules before staging.
   - Stage only the requested demo files and intentional reusable assets. Never include credentials, local profiles, caches, screenshots, or unrelated dirty-worktree changes.
   - Show or summarize the exact upload scope before commit/push when publishing is requested.

## Template Contract

- `assets/demo.html`: Chinese PaperTrace reference implementation.
- `assets/demo-en.html`: English PaperTrace reference implementation.
- `scripts/create_demo.py`: deterministic, atomic, no-overwrite-by-default materializer.

In the PaperTrace templates, label bundle/config/candidate artifacts and generated lessons without performance evidence correctly. Never describe `paper.md`, `reader_wiki/`, a news candidate/config, chat candidates, lesson exposure, or page views as proof that the corresponding pipeline's terminal evidence gate passed.

In the PaperTrace templates, label bundle/config/candidate artifacts as intermediate states. Never describe `paper.md`, `reader_wiki/`, a news candidate/config, or chat candidates as the terminal artifact of their pipeline.

Edit copied outputs in the target project. Do not mutate the bundled templates for a one-off demo unless the user is explicitly updating this skill.
