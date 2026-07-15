# Architecture

`reader-learner` owns schema v2, normalization, validation, source/event persistence, `review_queue`, backup, atomic writes, migration, and Visible Wiki projection. `adaptive-teach` reads that profile and owns Mission, settings, transparent analysis, teaching artifacts, spacing policy, and handoff construction. `lean-html-skill` owns the reusable HTML shell, feedback panel, browser-local state, download/copy controls, and design audit.

The profile is the sole long-term fact source. Session records and `derived/` are replayable teaching context, never status truth.
