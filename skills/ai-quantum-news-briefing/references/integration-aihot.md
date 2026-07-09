# AI HOT Integration

AI HOT is integrated into this skill as a candidate source, not as a separate top-level skill.

Reference snapshot:

- `references/aihot-skill.md`
- `references/aihot-readme.md`
- `references/aihot-feed.sample.xml`

Default candidate-pool command:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\aihot_candidates.py --source api --mode selected --take 50 --date <YYYY-MM-DD> --output C:\Users\SSS\Desktop\PAPER\news\<YYYY-MM-DD>\aihot_candidates_<YYYY-MM-DD>.json
```

RSS fallback:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\aihot_candidates.py --source feed --take 50 --date <YYYY-MM-DD> --output C:\Users\SSS\Desktop\PAPER\news\<YYYY-MM-DD>\aihot_candidates_<YYYY-MM-DD>_feed.json
```

Rules:

- Use AI HOT as a broad Chinese AI candidate pool.
- Do not treat AI HOT summaries as primary evidence.
- For final briefing items, verify important claims against original URL, official blog, publisher page, paper page, or reliable media.
- Use `source_url` as the AI HOT permalink for readable Chinese context and keep `original_url` for primary-source follow-up.
- Run `audit_briefing_config.py` before finalizing the daily briefing.
