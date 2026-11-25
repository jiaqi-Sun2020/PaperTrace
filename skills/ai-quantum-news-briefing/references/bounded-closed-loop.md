# Opt-in single-edition closed loop (review candidate)

This increment is not enabled by installation. No automation is created or
updated. `daily --action close-loop --record` requires a human-approved policy
file and its exact SHA-256. The edition date is supplied once by the host in
Asia/Shanghai; `execution_window()` freezes the preceding full natural day.
Cross-midnight continuation never changes either date. Historical cutoff and
the current source pool's per-day claims remain authoritative.

The controller dispatches existing collection, controlled authoring, staging,
review, sealing, local finalize, publisher and online-verification interfaces.
Source readiness, worker exit zero and synthetic test success do not approve
content. Academic >=6, social >=6, new/important >=4 and any stricter current
policy remain unchanged; no shortfall override is added.

## Approved runtime policy

Default template is only `{"version":1,"enabled":false}`. An enabled policy must
bind timezone Asia/Shanghai, start_time 01:00, a same-day deadline_time, max_actions
(1..128), max_agent_invocations (1..16), max_steps_per_invocation (1..32),
no_progress_limit (1..3), agent_timeout_seconds (30..1800), allow_publish (boolean)
and absolute codex_argv (executable, or executable plus a JS entry).
Optional max_tasks_per_batch is 1..4 (default4); it cannot increase the underlying
source/recovery budget. Optional allow_preview defaults false. Optional
driver_wait_seconds is 0..86400 (default0); it is an approved *host wait budget*,
not permission to extend collection, publication deadlines or the scheduler.
An explicit recovery policy also needs its matching recovery_policy_sha256.
No policy is approved or enabled by this document.

`drive()` consumes next_wakeup_at within that host wait budget, sleeping in
chunks <=30s. It keeps the same edition and durable ledger. When the host bound
expires it returns waiting and the actual next wakeup; a live authorized host
must resume that same command. A return value is never a scheduled wakeup.
Source Retry-After, live leases and independently due peers are handled by the
existing queue owners. Interrupted action/agent reservations are not refunded.

## Review boundaries

Review subprocesses use the normal read-only sandbox, fresh ephemeral sessions
and structured review proposals; they do not write review files. The controller
installs a proposal only through `daily_authoring.save`, binding the expected
old review hash and current lifecycle, retaining original backups.

Story-only review receives title/paragraphs in a neutral temporary working
directory and a separate process, before a second mapping reviewer receives the
technical material. Both process slots are reserved before either starts. The
second review must preserve the first round exactly and leave typed actual
display pending. This is context separation plus read-only access, **not an OS
read-deny container**: independent semantic quality and compliance still need
real runtime evaluation. Validators prove schema/binding, not truth.

Display review cannot clear factual or story-mapping failures. Full existing
preview content validation must pass first; with separate allow_preview approval
the existing immutable HTTPS preview API checks run/HTML hashes, uniqueness,
Bucket permissions and current configuration. The read-only display reviewer
receives that receipt, must use an actually permitted browser and can change
only display evidence/judgment. Local file denials must not be bypassed.
Final seal/strict validation remain unchanged and accept no pending display.

Owned subprocess trees are bounded: on Windows start suspended, assign the
process to a kill-on-close Job Object, then resume only that owned process.
Assignment/resume denial stops; no breakaway, access changes or global process
kill. Timeout/output overflow or normal parent exit closes owned descendants.
Windows termination additionally waits for the owned Job's active-process count
to reach zero; unconfirmed termination/accounting stops the controller.
Actual power loss and real Codex/tool invocations are not certified by unit tests.

## Stops and publication

Blocked/expired/exhausted outcomes are durable terminal states with a
pending_send notification outbox. No notification transport is added. Changing a
policy hash, code identity, deleting a journal or refunding budgets is not an
automatic recovery method. A corrected terminal edition needs a separately
reviewed operator transition; this increment deliberately supplies no reset.
While installation/recovery is incomplete the daily host must stay stopped.

Local finalization uses explicit --local-only; --require-remote conflicts are
rejected before commit. The controller next reconciles current online truth,
publishes only with allow_publish and existing enabled OSS permissions, and
requires a subsequent online verification. Uncertain upload outcomes are
reconciled first. Already verified releases are not uploaded again.

## Deployment boundary

This is an isolated review package, not a ready-to-run production installer.
Preserve current r2 code, real news/history and all uncommitted work. Before an
approved install, freeze current target/dependency hashes and Git status, bind a
new external backup/journal to this package, and reuse the tested controlled
installer with a separately reviewed exact scope. Do not reuse r2 manifest/tool
constants or old news snapshots. Before any closed-loop ledger exists, restoring
this increment's exact before bytes is compatible with current lifecycle. After
closed-loop/outbox data exists, old controller code must not be rolled back
without a compatible, reviewed protocol; do not delete that data to force it.

Required operational acceptance before enablement: approved host/runtime policy,
working normal CLI runtime access, real read-only review receipt installation,
real separated Fable review, an approved HTTPS browser/print path, pending_send
delivery ownership, and a host actually consuming waiting results until its
approved bound. Existing app scheduling/permissions are unchanged here.

## Worker phase diagnostics (r3)

The CLI bridge requests JSON event hints. A bounded pipe reader retains only
observed byte counts/SHA-256, exit and cleanup status, elapsed phases and coarse
tool categories. It does not persist stdout/stderr, command arguments, tool
payloads, source text, reasoning or credentials. Event hints are untrusted
diagnostics, never source evidence or review approval. Oversized/invalid lines
are discarded; counts and checkpoints have fixed caps. No timeout, retry or
agent-budget allowance is increased. No extra model invocation is scheduled.

Each job may write absent-only `worker-diagnostics/NNNN.json` checkpoints and
`worker-diagnostics.json`; unknown files are preserved. Diagnostic I/O failure
is reported as incomplete and never replaces the primary error. Timeout and
unconfirmed owned-child cleanup are recorded separately. A successful parent
with unconfirmed cleanup or failed/oversized output stays blocked. Receipt
read errors report operation and numeric OS error fields, without exception
messages or local paths. Missing, malformed and wrong-identity receipts remain
distinct blockers. Review proposals still require all existing semantic gates.

## Scoped browser recovery (r4)

Independently due deterministic tasks precede browser discovery. Live leases
and Retry-After delays remain owned by the pool; waiting peers cannot starve a
due browser task or cause repeated empty work invocations. Unknown lease timing
stops without stealing ownership. Fixed date, request budgets and strict gates
are unchanged.

Only the explicit worker-reported environment codes browser_initialization_timeout,
browser_runtime_unavailable and browser_connection_unavailable enter bounded
recovery. A general agent timeout, policy refusal, 403 or write error is not
silently reclassified. The worker makes one initialization attempt. The host
retains action/agent reservations and waits; default total browser attempts are
2 with a 300-second delay. Optional browser_recovery_attempts is an integer 1–3;
browser_recovery_delay_seconds is an integer 60–1800. Existing overall agent,
action, date and deadline limits still apply, even when they stop recovery sooner.

The journal reports browser_discovery as a scoped blocker. Independent due work
may drain during recovery or after browser exhaustion, including work that only
later becomes due. This does not reopen the exhausted browser budget, approve
missing discovery or create a wakeup service. The host must consume next_wakeup_at;
normal deployment and task prompt activation remain separately reviewed.
An exhausted model-call budget also remains exhausted; it does not prevent
independent non-model work from draining when due. Future independent leases and
Retry-After waits may be consumed without booking another model call.

Mapping input has one accepted blind_round. The prompt template omits its duplicate
but full output must preserve the original round verbatim. Saved input/reviews
are not edited. Canonical project paths use .agents/PROJECT_CONTEXT.md and
.agents/README.md. Optional codex_model is an explicit bounded model identifier;
when absent the configured default remains. No arbitrary CLI flags are admitted.
Command-event numeric exit codes are retained when supplied. Missing exit codes
remain unknown; old metadata without them cannot certify command success.

The source worker owns the read-only work_eligibility view as well as execution:
live leases, Retry-After, denied AI original hosts and fixed-pool backup gating
are shared rules, not guessed by the controller. Old code/policy versions of a
primary do not block its current successful peer. Task/counter history remains.
Current-date/current-code pending captures are included in the source handoff;
coverage success still does not qualify an article. Already registered due work
drains before requesting source expansion, and pending capture waits remain waits.
