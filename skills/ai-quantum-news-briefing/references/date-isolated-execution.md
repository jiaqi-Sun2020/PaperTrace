# One explicit edition per invocation

Automatic publication eligibility starts at **2026-10-16**, Asia/Shanghai.
Earlier dates leave automatic backfill and execution; their original publication,
failure, review, capture and revision records remain unchanged. Retirement is
not a successful release and does not retract an already published website.

The existing source architecture r1 remains in use. This increment fixes queue
selection and scopes worker admission; it adds no service, uploader or scheduler.
`daily` is the supported automatic execution entry. Old individual commands
remain compatibility/read-only diagnostics, not an automatic backfill route.

## Actual commands after this increment is approved and installed

From **D:/AI/PaperTrace**, freeze the release date once when an invocation starts:

```powershell
$releaseDay = '2026-10-16'
& 'D:/AI/Anaconda/python.exe' -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py daily --date $releaseDay --action status
& 'D:/AI/Anaconda/python.exe' -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py daily --date $releaseDay --action plan --record
```

The scheduler/agent chooses the date in Asia/Shanghai once; do not recompute it
after midnight. Coverage stays the preceding complete Shanghai natural day.
For Oct16 it is Oct15. Every generated `next_commands[].argv` retains that date.

`status` is read-only. `plan --record` persists the queue history cutoff and
registers current-date acquisition tasks. It does not generate or approve prose.
Before executing network tasks, validate and admit matching existing raw source
cache with the existing `validate_result` + task claim/complete interface.
Then run only due missing tasks:

```powershell
& 'D:/AI/Anaconda/python.exe' -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py daily --date $releaseDay --action work --max-tasks 4 --record
& 'D:/AI/Anaconda/python.exe' -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py daily --date $releaseDay --action packet
```

No automatic migration or network collection occurs just by installation.
The initial `plan --record` activates cutoff metadata through the supported
queue writer, not hand-edited JSON. Repeated activation preserves timestamps and
bytes. Older queue dates remain historical records, with `historical_retired`
in the returned view; explicit prior withdrawal reasons are preserved.

## Selection and stopping contract

`execution_order`, `next_date`, `next_action` and `final_response_allowed` all
refer to the requested date. Only that date may be executable. Another eligible
date is deferred, and an earlier-than-cutoff date is retired without inspecting
its failed artifacts. Neither is a dependency of today's publication. A future
explicit invocation may independently resume an eligible date, preserving its
original date/window; no implicit backlog loop follows today's completion.

For a retired date: `run_outcome=not_scheduled`, empty order, null next date,
`workflow_retired`; it is never `workflow_complete` or publication approved.
For current completion: empty order and null next date even if history remains.
For current pending work: exactly that date in order and next date, with an
action or command for the same edition. A precise blocker can end the current
attempt with `run_outcome=blocked`; it never means successful publication.

Shared queue/database corruption, schema or identity mismatch, storage/lock
permissions and current release environment faults still block with structured
stage/scope/code. Unknown store corruption is not discarded to appear ready.
An expired lease is recovered only on its own task claim, so an unrelated old
expired task cannot consume the current claim. Worker budgets only consider the
requested coverage date; discovery submit/deny/claim rejects a mismatched date.

## Stage recovery

| Returned stage | Next supported action |
|---|---|
| source_and_authoring_pending | Reuse valid cache; bounded current-date work; actual three-class typed discovery; independently author available materials |
| authoring_pending | Existing controlled authoring, complete Fable, bind-candidate, rank/Delta under actual strict policy |
| review_pending / staging_invalid | Repair only the current run via controlled revision; redo invalidated judgments/display bindings |
| ready_to_finalize | Actual review/sealing/strict release commands; this inspector never publishes |
| remote_pending | One current online status/receipt reconciliation; retain local release, never recollect or blindly reupload |
| workflow_complete | Stop this date; do not upload again or fall through to backlog |
| workflow_retired | Preserve history and stop automatic work on this date |
| execution_blocked / source_blocked | Report precise shared/current dependency and minimal recovery; no fallback to an old-date pipeline |

All original coverage, evidence, 6–8 academic, 6–12 social, at least4 new/important,
actual stricter policy, Fable and real semantic/independent/display/strict gates
remain. Feedback is optional and defaults off. Program and synthetic tests do
not certify a real edition or browser display. No OSS, proxy or schedule changes
are included. The earlier browser request-header policy loading failure is a
shared runtime prerequisite to retest through the permitted interface, not
something this date-selection change claims to fix.

## Installation and rollback boundary

This document is delivered in an isolated production-baseline package. Do not
call it deployed until the exact new package is approved, installed and tested
using actual production code with isolated data. Earlier r1 approval does not
authorize this new payload. Keep the existing dirty edits and source pool.

Rollback uses only this increment's external original-byte backup. If cutoff
metadata or a pool-bound run is already active, incompatible old code rollback
must stop; do not delete metadata/bindings or history to force it. During initial
installation/regression, before real cutoff activation, the immediate r1 baseline
can be restored safely. Unknown edits always stop recovery.

This package creates no automation and does not certify any existing scheduler's
state. The entry and prerequisites above can be handed to the daily task;
creating or updating that schedule requires separate user authorization.
