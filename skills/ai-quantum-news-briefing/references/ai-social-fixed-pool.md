# AI social fixed-pool contract (2026-10-16 r1)

This increment changes AI social/industry discovery only. Quantum acquisition,
historical records, date isolation, revision lifecycle, review and publication
ownership remain in the existing pipeline. No cookie, login session, extra Skill,
RSSHub, proxy change, schedule change or new publication permission is introduced.

## Approved finite pool

| ID | Exact entry | Type / method | Role and limits |
|---|---|---|---|
| ai_hot | https://aihot.news/api/v1/items | Aggregator / anonymous JSON | selected, window=7d, by=published, limit=50, opaque cursor; not independent media |
| openai-news | https://openai.com/news/rss.xml | Official / RSS | Discovery only; original 403 stops access; no completeness claim |
| deepmind-news | https://deepmind.google/blog/ | Official / fixed column | Article links; discovery date unknown until original evidence |
| anthropic-news | https://www.anthropic.com/news | Official / fixed column | Article links; discovery date unknown until original evidence |
| techcrunch-ai | https://techcrunch.com/category/artificial-intelligence/feed/ | Independent media / RSS | Primary; observed 20 returned entries, no complete-day guarantee |
| ars-ai | https://arstechnica.com/ai/feed/ | Independent media / RSS | Primary; observed 20 returned entries, no complete-day guarantee |
| verge-ai | https://www.theverge.com/rss/ai-artificial-intelligence/index.xml | Independent media / Atom | Backup; observed 10 entries and possible non-AI records |

Entries were checked read-only in the preceding source-verification phase. Those
observations establish availability at that check, not long-term reliability.
This implementation phase performs no live requests. Current AIHOT references:
https://aihot.news/agent?tab=api and https://aihot.news/openapi-v1.json .

## Evidence and time

AIHOT schemaVersion=1, query echo and page count/hasMore/nextCursor must agree.
links.original is the fetch target; links.aihot is aggregation provenance.
publishedAt and discoveredAt stay separate; missing publication time never falls
back to discoveredAt. A rolling seven-day API result is filtered locally against
the explicit previous Shanghai natural day; it is not described as a natural-day
API query. API pagination keeps existing budgets and checkpoint-prefix validation.
ETag 304 reuse requires the exact cached representation and its digest. HTTP errors
do not trigger wider queries. 429/503 Retry-After controls bounded retry scheduling;
delays outside the scheduler's one-day bound stop for operator attention.

RSS/column observations retain the returned bytes, decoded-representation SHA-256,
query/final URL, retrieval time, stable discovery identity, invalid positions and
raw/window/emitted/truncated counts. The 100-record projection is bounded output,
not exclusion or proof of complete coverage. Dated old records are filtered before
the cap; unknown dates remain unknown. Source groups are interleaved before the
combined cap. Identical original URLs merge provenance, not facts or review status.

Original capture still precedes admission. AI items carry ai_source_provenance and
URL-contract v2, preserving original query/fragment bytes. Original canonical URL,
article:published_time or canonical Article JSON-LD datePublished, timezone and
response digest must agree. dateModified and related-article timestamps do not
establish publication time. Unknown/conflicting dates stop admission for that item.
Original 401/403 stops further AI captures from that host for the current day;
other pool hosts can continue. No credentials, alternate access path or denial
bypass is used. Fixed-entry cross-host redirects stop before following.

## Real entry and recovery

After a separately approved deployment, run from D:/AI/PaperTrace:

```powershell
Set-Location 'D:/AI/PaperTrace'
& 'D:/AI/Anaconda/python.exe' -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py sources --date 2026-10-16 --pool-dir 'D:/AI/PaperTrace/news/_sources' --domain ai-social --action plan
& 'D:/AI/Anaconda/python.exe' -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py sources --date 2026-10-16 --pool-dir 'D:/AI/PaperTrace/news/_sources' --domain ai-social --action work --max-tasks 4
& 'D:/AI/Anaconda/python.exe' -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py sources --date 2026-10-16 --pool-dir 'D:/AI/PaperTrace/news/_sources' --domain ai-social --action packet
```

Use the actual release date explicitly throughout a run, even across midnight.
Plan registers deterministic tasks; work claims only that date's AIHOT/fixed-source
and AI-provenance capture tasks; packet is discovery/authoring input, not a draft
or approval. Repeat bounded work when pending tasks remain. Stable successful
tasks reuse the cache; code/policy changes intentionally create new bindings.
The Verge backup waits for primary media results and is eligible on primary
failure, original-access denial or fewer than three dated discovered media records. This heuristic does
not certify three publishable records; authors still choose qualified alternatives.
Existing enqueue-captures, original-evidence admission and bind-candidate interfaces
remain required; discovery itself neither authors prose nor uploads.

The existing combined daily entry still processes academic and Quantum work.
Its three rendered-search observations remain unchanged. AI-only work does not
claim them or forge their results. Fixed-pool observations establish two discovery
source categories; AIHOT is not a third independent category. The old combined
coverage gate is retained, so unfinished Quantum/search evidence is a real pending
gate, not silently waived by the new AI observations.

## Publication gates and compatibility

For new pool-bound dates >=2026-10-16, candidate binding also requires valid fixed
observations and exact committed task/result references. Historical wire evidence
is still readable for audit. New API checkpoint scopes never reuse legacy cursors;
an old scoped checkpoint is content-addressed backed up before replacement;
unknown future or corrupt checkpoint bytes are preserved and rejected.

Academic 6-8, social 6-12, at least four new/material updates, existing three source
classes, primary/media minima, organization/topic caps, original facts, Fable,
content/display reviews, release preflight and strict validation remain unchanged.
Stricter effective policy wins. Discovery readiness is not content readiness.
Insufficient qualified candidates must report the exact gap, not search indefinitely,
invent a time, automatically reduce quality or declare verified shortfall.
Feedback remains optional under the installed reading-mode policy.


## Bounded adversarial corrections (2026-10-16 r2)

Original access-denial controls are keyed by coverage day and exact hostname.
An already successful AI capture is retained and is not listed for replacement
because a different original on that host was denied. The existing date-scoped
entry remains required; this day key is defensive protection for mixed histories.
The replacement signal asks the author to select a qualified pool candidate;
it does not fabricate text, switch a frozen candidate, waive quotas or approve it.
A real-adapter synthetic test covers denial, alternate-host capture/admission and
byte-identical cache reuse without additional network calls on repeat work.

Every canonical tag is checked, relative canonical URLs resolve against the actual
original URL, and conflicting canonicals are rejected. Invalid unrelated JSON-LD
nodes no longer abort traversal of later canonical article nodes. Conflicting
original publication instants and unknown timezones still reject admission.
AI original publication proofs now require extractor_version=2, so an insufficient
r1 derived date proof cannot silently reuse the new validation. Old records are
not edited by validation; any later controlled recapture uses existing backup rules.
This version tag applies only to AI-provenance captures; Quantum captures keep
their installed meaning and need no artificial retagging or migration.

When discoveries of one exact original URL disagree on aware publication instants,
the merged discovery exposes a conflict and leaves published_at unknown pending
original verification; all discovery references remain. Different offsets for the
same instant agree. AIHOT API IDs are opaque: candidate hashes use the exact ID,
and story_id uses its digest rather than lossy punctuation/lowercase cleaning.
Existing feed compatibility and stored historical identities are not rewritten.

403 protection observes persisted failures at the start of bounded work and failures
encountered within that worker. It cannot cancel another worker's already in-flight
request. Run the normal single daily AI work owner; no new host-wide distributed
lock or collection platform is introduced by this correction.
