---
name: adaptive-teach
description: Run profile-backed, stateful teaching for PaperTrace without owning learner memory. Use only when explicitly invoked to find the next learning topic, diagnose real understanding, arrange a due review, continue a teaching session, or turn recent reader/news feedback into a short Chinese lesson and a safe teaching-feedback handoff.
---

# Adaptive Teach

Use this skill only with the user's explicit request because it reads personal learning data.

## Pipeline Identity and Terminal Gates

This skill owns **Primary Pipeline 4: Adaptive Teaching Decision & Evidence Loop**. It is distinct from paper-reader HTML generation, daily-briefing publication, and local chat-profile import.

The decision/session phase is:

```text
explicit teaching request
  -> validate profile + Mission/settings
  -> analyze weakness / insufficient evidence / due review / prerequisites
  -> select exactly one stable concept and one mode
  -> diagnose when needed
  -> generate one validated 10–20 minute Markdown/HTML lesson
```

For a lesson request, the validated session/lesson artifacts complete the requested decision phase, but they never prove learning or mutate the profile. The full evidence loop continues only after real learner performance:

```text
actual answers/application/self-check
  -> build teaching_feedback.json
  -> validate-feedback
  -> import-feedback
  -> reader-learner backup + atomic profile/review-queue update + optional Visible Wiki sync
```

Do not manufacture feedback to force same-turn closure. If no actual performance exists, stop the evidence loop at the lesson and report that profile import did not occur.

## Ownership

Read `.agents/reader-learner/knowledge_profile.json` as the only long-term knowledge-state source. `concepts`, `events`, `sources`, and `review_queue` remain owned by `reader-learner`. Write private teaching artifacts only under `.agents/adaptive-teach/`; never edit the profile directly.

Use `references/ARCHITECTURE.md` before changing boundaries, `references/TEACHING-CYCLE.md` for a session, `references/WEAKNESS-MODEL.md` for ranking, `references/EVIDENCE-RUBRIC.md` for evidence, and `references/TEACHING-FEEDBACK-CONTRACT.md` before creating/importing feedback. Use `references/LESSON-CONTRACT.md` only when authoring a lesson and `references/WORKSPACE-CONTRACT.md` only when changing workspace state.

## Deterministic cycle

1. Validate schema v2 through the existing profile validator; stop before writing teaching state on failure. Initialize the private workspace and minimal Mission only when absent. Confirm with the user before changing an existing Mission.
2. Analyze only stable concept IDs. Separate explicit weakness, insufficient evidence, due review, and configured prerequisite blockers. Exposure-only `unrated` remains a diagnostic candidate.
3. Select exactly one mode: `diagnose`, `teach`, `review`, `prerequisite`, or `transfer`. Use stable priority then concept-ID tie-breaker; explain every reason code and alternative.
4. Run at most three diagnostic prompts when uncertainty affects difficulty. Produce one 10–20 minute lesson with recall, an application, immediate self-check, and transfer/counterexample.
5. Generate HTML from the Markdown content and attach the shared `lean-html-skill` feedback panel. It remains browser-local until exported; lesson generation is never learning evidence.
6. Create an importable `teaching_feedback.json` only from actual user performance. Validate it, then delegate `teaching-feedback` import to `reader-learner`; record the import result in the session record.

## Commands

Run these from `D:\AI\PaperTrace`:

```powershell
python .\skills\adaptive-teach\scripts\adaptive_teach.py analyze
python .\skills\adaptive-teach\scripts\adaptive_teach.py next
python .\skills\adaptive-teach\scripts\adaptive_teach.py lesson --output-dir .\.tmp\adaptive-lesson
python .\skills\adaptive-teach\scripts\adaptive_teach.py validate-feedback --feedback <teaching_feedback.json>
python .\skills\adaptive-teach\scripts\adaptive_teach.py import-feedback --feedback <teaching_feedback.json>
```

For a real response JSON, use `build-feedback --actual-feedback <actual_performance.json> --output-dir <session-dir>`. `import-feedback` invokes the reader-learner pipeline; it does not duplicate its validator, backup, atomic writer, or visible-Wiki projection.

## Completion checks

Report the selected stable concept, mode, reason codes, evidence references, remaining uncertainty, lesson paths, and whether import happened. Do not call a lesson completed as mastery. Do not treat source exposure, page views, HTML generation, or self-report alone as proof of retention.
