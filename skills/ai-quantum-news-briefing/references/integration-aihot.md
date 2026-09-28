# AI HOT Integration

AI HOT is integrated into this skill as a candidate source, not as a separate top-level skill.

Reference snapshot:

- `references/aihot-skill.md`
- `references/aihot-readme.md`
- `references/aihot-feed.sample.xml`

Default candidate-pool command:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\aihot_candidates.py --source api --mode selected --take 50 --date <RELEASE-YYYY-MM-DD> --coverage-date <PREVIOUS-SHANGHAI-YYYY-MM-DD> --output D:\AI\PaperTrace\news\<RELEASE-YYYY-MM-DD>\aihot_candidates_<RELEASE-YYYY-MM-DD>.json
```

RSS fallback:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\aihot_candidates.py --source feed --take 50 --date <YYYY-MM-DD> --output D:\AI\PaperTrace\news\<YYYY-MM-DD>\aihot_candidates_<YYYY-MM-DD>_feed.json
```

Rules:

- Use AI HOT as a broad Chinese AI candidate pool.
- `--date` labels the release; `--coverage-date` filters the previous complete Asia/Shanghai day. With a coverage date, `--take` is the API page size, not a cap on all daily candidates. `--since` is only the retrieval lower bound. The script follows opaque cursors and marks interrupted, out-of-retention, or ambiguous-timestamp windows partial. The feed cannot establish complete daily coverage.
- Do not treat AI HOT summaries as primary evidence.
- For final briefing items, verify important claims against original URL, official blog, publisher page, paper page, or reliable media.
- Use `source_url` as the AI HOT permalink for readable Chinese context and keep `original_url` for primary-source follow-up.
- Run `audit_briefing_config.py` before finalizing the daily briefing.
