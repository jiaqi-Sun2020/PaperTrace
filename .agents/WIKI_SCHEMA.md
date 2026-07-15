# Visible Wiki Schema

`.agents/wiki/` is the persistent human-facing knowledge layer. It contains only curated `concept`, `entity`, `theme`, `question`, `synthesis`, `claim`, and `source` pages with stable IDs and `visibility: public-wiki`.

Source-layer data remains in its existing locations: PDFs, reader bundles, raw feedback, events, logs, pipeline state, and `.agents/reader-learner/knowledge_profile.json`. Do not move, rewrite, or promote raw interaction text into public pages.

- `knowledge_status` is a projection of the profile's explicit `mastered`, `known`, `learning`, `unknown`, or `unrated` state.
- Exposure never upgrades a knowledge status.
- `source_refs` contains public `source.*` page IDs.
- `profile_source_refs` maps a source summary to immutable `src-*` IDs in the profile; it must not expose a local path or raw payload.
- Allowed relation types are `prerequisite`, `supports`, `contradicts`, `extends`, `example-of`, `evidence-for`, and `about`.
- Freeform annotations and unresolved `concept-*` IDs are not public concept pages.
- A complete projection contains exactly one public page for each stable profile concept and one concise source summary for each profile source. The excluded raw records remain retained in the profile and are counted in `maps/Profile Coverage.md`.

Run from `D:\AI\PaperTrace`:

```powershell
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py sync
python .\skills\reader-learner\scripts\lint_visible_wiki.py --profile .\.agents\reader-learner\knowledge_profile.json --wiki .\.agents\wiki --strict --require-profile-coverage
```
