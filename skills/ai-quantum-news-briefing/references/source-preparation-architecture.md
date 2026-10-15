# Recoverable source preparation, contract 1

This is an isolated production-baseline merge. It installs nothing, migrates no
real draft, changes no schedule and performs no real publication.

## Responsibility and authority

| Stage | Input -> output | Authority / recovery |
|---|---|---|
| Discovery | Registered source/date/config -> retained result | SQLite task lease/result; existing adapter owns its checkpoint |
| Original capture | Original URL/excerpt -> existing capture bytes | Existing `source_capture`; successful bytes reused |
| Authoring material | Valid dated capture -> immutable material generation | Pool admission, always `not_reviewed` |
| Dated preparation | Coverage + material references -> authoring packet | Derived handoff with exact gaps, never another release status |
| Edition | Authored candidate -> ranking, Fable, staging, actual reviews | Existing daily lifecycle remains the sole run authority |
| Delivery | Strictly reviewed release -> receipt/remote verification | Existing publisher and release lock; no new uploader/database |

Legacy `status/collect/resume` and versions 1–4 retain their meaning. The
explicit `sources` command opts into source preparation. It does not write an
orchestration checkpoint, candidate, staging directory or publication receipt.

## Storage and transactions

The workload is one Windows host and several bounded collectors. Atomic JSON
remains appropriate for existing single-owner checkpoints; SQLite's standard
library transactions handle atomic task ownership/result/material changes.
Use the default rollback journal, `synchronous=FULL` and short transactions.
No Postgres, Redis, TypeScript service, credentials or external provider is added.
No network call runs inside a pool transaction. Material updates for the
canonical `news/_sources/pool.sqlite` also take the existing release lock,
preventing a race with official publish/finalize checks.

Back up through SQLite's backup API, then atomically admit the completed backup
without overwriting a destination. This also handles committed WAL data; do not
copy only a live `.sqlite` file. Production needs local filesystem locking and
the existing absent-only hard-link capability. Network filesystems, actual
power loss and hostile privileged filesystem races are not certified here.

## Task and browser contracts

Task identity hashes version, kind, source, Shanghai coverage day, exact inputs,
source configuration, code/contract and policy. Input/date/config drift creates
a new task; it does not reset the old task or clear another source's success.

States: `pending -> running -> succeeded`, `retry_wait`, `blocked`, `exhausted`.
Unique leases prevent stale commits. Identical committed results tolerate a
lost acknowledgement. At most three claims include interrupted workers; expired
leases recover within that bound. Failed work cannot advance a successful
checkpoint. Adapter cursors remain in existing query-bound checkpoints.

403/404, policy denial, filesystem permission, TLS refusal, invalid evidence,
timeout and 429 have distinct diagnostics. Policy denial stops that action.
Retry-After is durable waiting, never a capped early retry or a long sleep.
Delays beyond one day require diagnosis instead of an earlier automatic retry.

`discovery_navigation.py` constructs the existing three Google query scopes
from `daily_coverage_evidence.RENDERED_SEARCH_TARGETS`. It returns a typed
`navigation_url` and a CUA invocation using `discovery_navigation.mjs` before
`tab.goto(url)`. The agent binds an already permitted tab as `tab`; the helper
does not open another browser/service or retry a denial. A query string fails
before browser invocation. A valid URL is neither access permission nor proof
of search coverage. `submit-discovery` still requires the existing typed DOM
observation plus separate original anonymous HTTP bytes for that task/date.

## Materials and review invalidation

Identity uses source ID plus the exact original URL. Semantic parameters and
fragments remain intact; no generic URL/title merging is borrowed. Original
fields, capture timestamps and hashes are preserved. Known DOI/exact-URL
duplicates cannot inflate packet quantity estimates; final ranking owns dedup.

Each changed item/capture gets an immutable generation, including reversions.
Unknown dates, aggregate-only summaries, unsupported academic identities and
invalid excerpts never become admitted material. Capture success plus valid
material insertion is one transaction. Unqualified captures remain evidence,
not qualified pool entries. Admission never upgrades semantic review/evidence.

Candidate bindings verify committed coverage results and current material.
Generation narrows dependencies to selected entries: unrelated material updates
do not block a frozen edition. Unpublished bound runs check dependencies at
structure verification, sealing, strict validation, preview, finalize and first
upload. A matching published receipt preserves its historical reviewed snapshot.
Never erase old captures, reviews, lifecycle or receipts to make a new run pass.

Rollback to code lacking this contract must stop once any pool-bound run exists,
including a published historical run. Keep the pool/revisions; never strip bindings to invoke an older
validator. Reuse the existing controlled recovery protocol with this explicit
compatibility guard; do not use an earlier base-code backup.

## PLOS, policy and acceptance

The PLOS replay-verified Research Article query/projection is unchanged, keeping
old ledgers replayable. Admission accepts only the exact publisher article
host/path, matching `10.1371` DOI/type and original capture. Search/API/home pages,
lookalike hosts and inconsistent DOI redirects fail. Research Article metadata
survives normalization. New protocol 3/4 ranking uses v2; v1 remains legacy.

No academic 6–8, social 6–12, new/important >=4, stricter configured diversity,
four-class coverage, complete Fable, real semantic/display review or strict
publication rule is relaxed. Partial preparation permits independent capture
and authoring; missing required evidence still blocks a bound candidate.

Synthetic review/mock-upload tests prove control flow, not true content,
browser display or real OSS delivery. Production maintenance/filesystem checks,
installation and migration approval, and fourteen real scheduled observation
days are separate acceptance after this code handoff.
