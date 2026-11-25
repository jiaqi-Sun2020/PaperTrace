# Bounded daily recovery contract (isolated proposal, 2026-10-17 r2)

This is a production-baseline repair package, not a deployment or a published
edition. Existing source coverage, delivery policy, original-article admission,
ranking, Fable, semantic/display reviews, lifecycle and OSS gates retain authority.

## Current-day supply and phase ownership

`coverage_ready` means the registered source-family/query and discovery evidence
passed. It never certifies sufficient articles or prose. `content_readiness`
separately reports unique discoveries, captures, evidence-qualified articles and
rejected capture/material records. Its floors use the sole delivery policy and
an existing candidate's stricter configuration. Topic, organization, source class,
new/important-update and semantic requirements remain unapproved until ranked
authoring and actual reviews evaluate them.

`candidate_shortage` has a concrete current-date blocker instead of a packet loop.
`article_qualification_pending` requires the agent to prepare article inputs,
capture originals and use existing import/bind interfaces. An available discovery
is not evidence-qualified; evidence-qualified is not semantically reviewed.
Returning an author/browser command does not complete that stage.

## Diagnosis and retained caches

`daily --action diagnose` is read-only. It replays existing academic checkpoint
envelopes, query/window/source-scope bindings and digests, reporting corrupt or
absent checkpoints explicitly. Failed rows are never promoted to healthy rows.
No diagnostic re-fetches a URL. The 14 real October17 generic errors replay as
8 feed/query ranges not covering the target day, 5 unstructured adapters and
1 JMLR date-unknown row (205 quarantined entries). HTTP200 is not daily coverage.
OpenReview/Science403 and arXiv quantum exhausted429 remain separately blocked.

New failure records retain validator codes, row flags, date/window diagnosis and
response digest. Raw exception text, credentials and body text are not copied into
failure messages. A code update can reuse a source task only when its exact
query/date/kind/source configuration and policy are unchanged. Successful results
must pass the current validator. Old task/result bytes remain; attempts and
blocked/exhausted state cannot reset. A live prior owner blocks rebind. An expired lease can rebind without restoring its consumed attempt; the old row remains intact. Actual running events across compatible code identities share one capped budget, the strictest saved cap and latest Retry-After. Superseded identities cannot claim again.
Unpublished run/review bindings are not approved by this source-cache operation.

## Same-window recovery, never wider article dates

`daily --action recover --recovery-policy <reviewed JSON>` performs a bounded
late retrieval through existing adapters. It rechecks only successful source
queries after the explicit minimum interval. Each parent has one deterministic
recheck, each recheck at most one network attempt, at most four reserved recheck
tasks per edition. Failed/interrupted reservations consume the budget. Other dates,
denied hosts, failed/exhausted parents and disallowed sources cannot be claimed.
The original issue/coverage date and URLs/query parameters remain unchanged.
Code aliases of a reserved recheck count once and retain its original parent; pending aliases rebind before executing. A short per-day reservation lock is released before requests. Original results stay in the pool; a validated newer full query is projected into
the current view and included in candidate source bindings.

Exhausted or access-denied sources are never reset. Retry-After on ordinary tasks
is preserved. A saved retry time is eligibility only, not proof of another run.
After a completed bound still leaves a shortage, stop without another packet or
recovery loop. Supplying qualified current-day articles or changing the product
date-window policy are separate decisions. This package adds no lookback dates,
new source registry entries or cross-date worker claims.

## Evidence persistence capability

Before costly `work`/enabled `recover`, the source entry probes the issue's
collection directory using only a uniquely named public temporary file. It checks
write/fsync/read and atomic no-clobber hard-link capability and removes its own
probe. Failure occurs before any collector call. It does not prove browser export,
network access or ongoing space/permission availability.

`evidence_persistence.py save` consumes a public receipt already exported to a
permitted local byte file, never a large command-line string or prose patch.
The exporter must save the actual tool-returned receipt/body bytes: no truncation,
summary reconstruction, cookies, private browser data, new transport or access
denial bypass. A permitted persistent runtime can write its existing in-memory
public receipt to a file; if that export is forbidden, stop and report the missing
capability instead of fetching again or switching access routes.

The saver requires expected byte count and full SHA-256, validates the exact
receipt contract and decoded HTTP-body digest/window/public URLs, and installs the
unaltered JSON bytes atomically without clobbering an unknown output. Repeat saves
reuse exact bytes without touching mtime. Files remain within the requested
`news/_collection/<release-day>/`; reparse paths and suspicious input/output names
are rejected. The default capacity is32MB; a 120KB response is not truncated.

## Continuation ownership and proposed scheduling

Short queue transactions store per-edition attempt lease and machine-readable
continuation in the existing `_automation/workflow_queue.json`; no new database,
parallel scheduler or source of publication truth is added. A per-edition OS
advisory lock covers the invocation, independently of the900-second persisted
intent lease. A live owner cannot be stolen because metadata expires; process
death releases the OS lock. Requests stay outside the shared publication/index
lock. Existing source leases and publication
locks still apply; an unrelated external editor is not covered by this lease.

`daily --action continue --date D --recovery-policy <reviewed JSON>` consumes the
saved stage for that exact issue. It executes due source work or the bounded
recheck; frozen/reviewed/finalized stages keep the existing lifecycle authority.
It first registers compatible current-code identities without requests, then chooses from fresh state; it never executes arbitrary stored argv. The saved continuation identifies the
existing automation `ai`, earliest eligible time and next commands, but explicitly
says `not_scheduled_by_code`. No wakeup or notification has been activated here.

Enabled policy requires version1, timezone Asia/Shanghai, aware issue-date
not_before/deadline, interval60..86400 seconds, max_recheck_tasks1..4 and
max_tasks_per_invocation1..4. `recovery-policy.disabled.json` is the sole default.
The tested times/budgets are synthetic, not production policy. Approval is still
needed for the real budget and for how the existing single automation will wake
to consume the saved continuation. Keep10:00 cutoff /10:30 earliest retry until the
user resolves whether the10:30 compensating attempt has a later deadline. Never
silently select that policy or create a second automation.

## Remaining acceptance

All automated reviews, original transports and remote objects in the E2E traces
are fixtures. Real article meaning, independent Fable review, current-HTML display,
OSS identity and a real release still require evidence. Multiple unattended real
days including a weekend, shortage/recovery and restart cases are separate
operational acceptance. Code/test success alone does not certify daily reliability.


## Failure context and saved browser evidence repair (2026-10-18 proposal)

Failure retry control remains the four-field contract (`code`, `retryable`, optional
`http_status` / `retry_after_seconds`). Academic summaries are now separately
validated `details.version=1`, bounded to named scalar fields, source/day binding,
validator codes and response digest. No raw body, exception prose or credential
fields are admitted. Failure persistence is outside the collector exception
boundary: a broken store cannot overwrite the real source cause as another source
failure. Existing bad blocked rows remain intact; diagnosis does not reset attempts
or automatically release them. Cache diagnosis follows only verified same-query
code aliases to original checkpoint bytes and reports their task ID and digest.

From `D:/AI/PaperTrace`, after this exact increment is separately deployed, first
probe the intended `news/_collection/<release-date>` capability using the existing
`evidence_persistence.py probe`. This is a filesystem probe, NOT evidence that the
browser export or desktop edit tool has permission. A desktop tool refusal must
be reported and resolved with the appropriate scoped approval, not bypassed by
switching writers, tools, protocols or directories. The Oct18 failed observation
was targeted at another C-drive visualization directory; its recorded failed edit
has no underlying errno. Its exact environmental cause remains unverified.

The existing `save` action still accepts only actual public HTTP receipts.
New `save-discovery` accepts the complete existing rendered-search envelope
(observation plus independent raw HTTP receipt), using the unchanged discovery
validator, full expected file SHA-256 and byte length. DOM and raw HTTP digests
remain distinct. It does not fabricate evidence or write from a summary.

Proposed commands (replace bracketed inputs with actual approved public file
identities; do not execute placeholders):

```powershell
Set-Location 'D:/AI/PaperTrace'
& 'D:/AI/Anaconda/python.exe' -B .\skills\ai-quantum-news-briefing\scripts\evidence_persistence.py save-discovery --news-root .\news --date <RELEASE-DAY> --input <EXISTING-PUBLIC-BYTE-FILE> --output <NEWS-COLLECTION-DISCOVERY-FILE> --expected-sha256 <FILE-SHA256> --expected-bytes <EXACT-BYTE-COUNT>
& 'D:/AI/Anaconda/python.exe' -B .\skills\ai-quantum-news-briefing\scripts\source_preparation.py resume-discovery --date <RELEASE-DAY> --pool-dir .\news\_sources --task-id <CURRENT-DATE-DISCOVERY-TASK> --input <SAVED-DISCOVERY-FILE> --expected-sha256 <FILE-SHA256>
```

`resume-discovery` validates file bytes and task/query/class/day before claiming.
It uses a current lease, retains consumption through expired-lease recovery,
refuses live ownership and exhausted budgets, and recognizes an identical committed
result after acknowledgement loss. It performs no browser/HTTP request. Invalid
files consume no attempt. The old token remains invalid after lease recovery.
A code upgrade may require the existing network-free daily `plan` to register
compatible identities first. This does not reset old attempts or reclassify bad
failed rows as healthy.

Local save failures return operation/type/errno/winerror without raw exception
prose. A tool-level rejection that prevents invoking this interface remains an
external permission issue; do not claim it was repaired by unit tests.

This increment changes no source adapter, publication date range, Quantum query,
source-class requirement, delivery floor, content/Fable/display review or publisher.
Real saved evidence and originals must still be checked in the production task.

## Adversarial follow-up r2: diagnostic isolation and explicit cached correction

Observed HTTP denial/rate limiting takes precedence over a provider diagnostic.
Malformed secondary fields become explicitly invalid diagnostic fields, never
facts. A failed diagnostic builder cannot replace a known transport cause.
Storage errors propagate with `original_source_failure` / task identity through
the source CLI and daily blocker output; no second failure-store write is attempted.
Corrupt diagnostic caches are reported per source without discarding peer reports.

Old `failure_contract_invalid` records are not automatically unblocked by plan,
work, continue, or diagnose. After a separately approved deployment, `plan` may
register a compatible current-code alias while retaining attempts and all history.
An operator can explicitly submit a **network-free** correction for that new alias:

```powershell
Set-Location 'D:/AI/PaperTrace'
& 'D:/AI/Anaconda/python.exe' -B .\skills\ai-quantum-news-briefing\scripts\source_preparation.py reconcile-cached-failure --date <RELEASE-DAY> --pool-dir .\news\_sources --task-id <CURRENT-CODE-ACADEMIC-ALIAS> --expected-failure-sha256 <CANONICAL-FAILURE-SHA256> --expected-sha256 <ORIGINAL-CHECKPOINT-FILE-SHA256> --reason legacy_failure_contract_repair
```

Placeholders are identities to obtain from actual status/diagnosis, not executable
examples. Failure identity is `source_pool.fingerprint(task['failure'])`; checkpoint
identity is SHA-256 of exact file bytes, not the row or payload hash. CLI checks the
release/coverage day. Both the current alias and immutable original must have the
exact two-field legacy failure, and no related real denial or active owner may
exist. Source/query/policy, checkpoint envelope, source scope and current evidence
validators all remain mandatory. Exhausted budgets are rejected. No new attempt,
HTTP request, evidence file write, candidate generation or semantic approval occurs.

Successful correction changes only the new alias's acquisition result and appends
a digest-bound event in the same SQLite transaction. Original blocked task, events
and cache bytes remain intact. Acknowledgement loss or two concurrent CLI calls
converge on one result; wrong digest, changed evidence, real 403 or an invalid cache
stops. Invalid caches return `cached_failure_still_invalid` (CLI exit 2), not ready.
The 21 actual Oct18 caches were invalid in r1's offline diagnosis, so this interface
does **not** certify that those 21 tasks can become ready; approved peer collection
or source-contract work may still be needed. It is never a retry-budget reset.

Once any production acquisition/lifecycle bytes change after installation, the
existing installer refuses automatic old-code rollback. Preserve history and use
a reviewed compatible forward recovery; do not delete the records to force rollback.
