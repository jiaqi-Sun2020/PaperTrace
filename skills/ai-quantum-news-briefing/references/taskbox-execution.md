# One ordinary Codex task: explicit same-task self review

Status: deterministic ordinary-task code path; local regression and actual edition acceptance are separate. This document
does not install code, enable a schedule, approve a real edition, authorize
network access, enable OSS, or publish a website. Production still needs a
separate scoped migration and real pilot. The commands below are a runbook for
that later authorized execution, not commands run during this repair.

## Route and completion contract

Use one existing ordinary Codex task to collect evidence, author Chinese facts,
judgment and relevance, author the complete Fable and consistent example, inspect
sources and real display, then invoke deterministic local gates. All semantic
writing and review occur in this task with review_method=self and
taskbox_context={"mode":"same_task_self","context_isolation":"none","independent_review":false}.
The story-only reading round is a self-check in the same context; it is not a
blind or independent review. Never label another reviewer as having participated.

No separate API, provider adapter, model service, CLI model invocation, closed-loop
driver, new reviewer task, extra paid service, dependency installation or scheduling
is part of this route. Do not invoke daily_closed_loop.py, daily_agent_execution.py,
codex exec, or change runtime policies. The Python scripts below perform
deterministic work; they do not call a model. Source collectors and the existing
publisher still need their actual network and filesystem permissions.

Freeze one release date in Asia/Shanghai at invocation start. Coverage is the
preceding complete Shanghai natural day [00:00, next 00:00). Preserve this date
across midnight, resume and revision. Do not execute backlog or widen evidence
dates implicitly. Original publication dates remain original publication dates.
Existing source-family, four social source-class, source URL/capture admission,
ranking, Fable, coverage, stricter configured delivery and budget gates still apply.
Standard delivery is 6-8 academic and 6-12 social items with at least four
new/material-update social items. This route adds no quota or shortfall override.
Use only already valid evidence under existing owners for any approved expansion.

A taskbox release requires exact integer pipeline=4, coverage contract=3, required
story-review protocol=3, source URL contract=2 in manifest and config, news review=1,
and story review=3. Unknown, boolean and downgraded versions fail. Historical
releases without a taskbox declaration retain their original validation meaning.
Do not strip a taskbox declaration/context or relabel an edition as historical.
Templates, source coverage, capture success, worker exit zero and structural
verification never approve content. A validator proves recorded coverage/binding;
the active task remains responsible for the truth and limits of each claim.

## Existing runtime and persistent creation identity

After system reinstall, test the actual existing Python with sqlite3 and ssl;
the presence of python.exe or the old Anaconda directory is insufficient.
Use the direct Python entry with the pinned 3.12 interpreter and ignored,
non-secret news_runtime.local.json. It never falls back to conda base Python 3.8
or touches unrelated environments. It never installs dependencies, changes PATH,
calls a model, schedules work or chooses a date. From D:/AI/PaperTrace
(replace the example date with the frozen, authorized current date):

```powershell
& 'C:\Users\SSS\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -B .\skills\ai-quantum-news-briefing\scripts\taskbox_daily.py next --date 2026-10-25 --runtime-config .\news_runtime.local.json
```

The runtime file contains only version=1, python_executable,
ossutil_executable, ossutil_config (path only), and ossutil_endpoint. Profile and
region stay in the existing five-field routing configuration. The publisher
uses process-scoped overrides for the existing program and credential container,
without reading/copying it. The endpoint must match the routing region's canonical
HTTPS OSS endpoint. No credential fields are accepted in the runtime schema.
From D:/AI/PaperTrace, this is read-only diagnosis:

```powershell
& 'C:\Users\SSS\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -B .\skills\ai-quantum-news-briefing\scripts\publish_daily_to_oss.py doctor --head-only --runtime-config .\news_runtime.local.json
```

The user selected direct Python after the ordinary-terminal execution-policy
block on .ps1. Do not change or bypass that policy. The existing .ps1 wrapper
remains available where already allowed, but is not required by this route.
Both entries set only the same three PAPERTRACE_OSSUTIL_* overrides and restore
them, including on failure; proxy variables and PATH are not changed.
When HTTP_PROXY or HTTPS_PROXY is already present, ossutil v2 receives its
native --proxy env selector. No proxy URL/credential is copied into argv;
NO_PROXY and TLS verification stay unchanged. There is no direct retry after
a proxy failure. With neither HTTP(S) variable, the ordinary-terminal command
is unchanged. After a prior permission denial, review the new live-check scope
before invoking it; an offline patch is not evidence of task connectivity.
Add --connection-details only to doctor for a bounded, sanitized connection
error, timestamps, exact non-secret invocation and proxy-presence booleans.
Do not repeat a socket permission denial, change proxy/TLS settings, or treat
the Python CLI exit 1 as the ossutil child exit (retained as exit_code).

HeadObject does not call stat/GetObjectAcl, authorize upload, or verify the
website/body binding. The full existing content comparison and preview Bucket
versioning gates remain mandatory. A task-level dial/connect failure is distinct
from a cloud permission verdict. Do not widen ACL permissions to make stat pass.

Freeze the real selected date once; the example does not authorize historical
backfill. Keep that frozen date when continuing across midnight.

New taskbox runs bind their creation contract per run ID in taskbox_runs inside
the existing staging lifecycle ledger. Shared seal/strict/finalize and publisher
verification consult this owner, so deleting both manifest/config declarations,
both review contexts and typed display, then recomputing artifact/review hashes
cannot reclassify a newly created taskbox run as a legacy release. Genuine runs
created without this identity retain their original validation semantics.
Do not delete or edit the lifecycle ledger to force a downgrade. Installation
does not retroactively manufacture creation records for old releases; pre-existing
drafts need explicit inspected recovery, not automatic reclassification.

## Working directory and fixed setup

For later execution after approved migration, run from D:/AI/PaperTrace.
During this repair the only runnable acceptance command is the offline command
in the last section; do not point an isolated source copy at real news.

The following variables are frozen by the current task after the user selects
the edition. Replace RELEASE-DAY with the actual authorized YYYY-MM-DD.

```powershell
Set-Location 'D:/AI/PaperTrace'
$py = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$task = '.\skills\ai-quantum-news-briefing\scripts\taskbox_daily.py'
$source = '.\skills\ai-quantum-news-briefing\scripts\source_preparation.py'
$author = '.\skills\ai-quantum-news-briefing\scripts\daily_authoring.py'
$releaseDay = 'RELEASE-DAY'
& $py -B $task next --date $releaseDay
if ($LASTEXITCODE -ne 0) { throw 'Inspect the current edition blocker' }
& $py -B $task source-status --date $releaseDay
```

next returns an action-required handoff. It is not a successful edition.
Inspect an existing release/stage before collecting. A finalized local release
with only remote work pending must be reconciled, not recollected or restaged.

## Collection, discovery, captures and material admission

Only when network collection is within the actual authorized scope:

```powershell
& $py -B $task collect --date $releaseDay --allow-network
if ($LASTEXITCODE -ne 0) { throw 'Stop and inspect source-specific failures' }
& $py -B $task source-packet --date $releaseDay
if ($LASTEXITCODE -ne 0) { throw 'Repair the returned source packet blocker' }
```

collect dispatches existing date-scoped plan and at most four due tasks.
It never launches a model. The pool owns live leases, consumed attempts,
Retry-After, denied hosts and exhausted budgets. No waiting result creates a
future wakeup. Resume only the same edition through an already authorized host.
Do not clear history, change task/code identities or switch access routes to
refund a budget or bypass a denial. Repeated no-progress needs diagnosis.

Some discovery still requires the active task's permitted browser. Use the
returned typed navigation and current task ID. Persist the complete actual DOM
observation and independent public HTTP receipt, not a reconstructed summary.
For already saved actual discovery bytes, the existing network-free interface is:

```powershell
& $py -B $source resume-discovery --date $releaseDay --pool-dir .\news\_sources --task-id TASK-ID --input ACTUAL-DISCOVERY.json --expected-sha256 EXACT-FILE-SHA256
if ($LASTEXITCODE -ne 0) { throw 'Discovery was not admitted' }
```

TASK-ID, filenames and hashes are observed values, never fabricated placeholders.
Browser denial or receipt export denial stops that lane. A successful HTTP
request is not a semantic source review. Do not copy cookies or credential data.

For an already saved, digest-bound DOM/HTTP observation whose real Google page
adds a bounded `sei` routing parameter or displays opaque `/goto` result hrefs,
the offline `source_preparation.py adapt-discovery` action emits observation v2.
It requires the existing `--date`, `--pool-dir`, `--task-id`, `--input` and
`--expected-sha256` arguments shown above. Save its JSON output to a new file;
preserve the original file. It never navigates, claims a lease, commits a task,
resets an attempt or approves an article. All observed links/counts and the raw
HTTP receipt remain intact. Deterministic `result_classifications` distinguish
target discovery leads, off-scope links, non-post endpoints and unresolved
Google redirects. Unresolved links have no candidate URL. Version 1 remains
strictly readable under its original contract; changing only its version is
invalid. No-results, date or exhaustive-coverage claims are never manufactured.
The existing `resume-discovery` still requires a valid current lease/state;
adapter success cannot reopen a blocked task or bypass a policy denial.

Offline diagnosis should use the production delivery defaults and source-only
ranking (`news-ranker-v2`) with actual admitted captures. A standalone audit of
an unfinished candidate without delivery fields is narrower than release
approval. Ranking exclusions now name the exact binding organization/topic cap
or target limit; these limits remain unchanged. Feed `updated` timestamps do
not substitute for publication timestamps. New RSS collection-funnel counters
do not retrospectively supply counts missing from old captured checkpoints.


### Requalify a saved discovery-format failure (bounded repair)

Run from D:/AI/PaperTrace, using the verified Python 3.12.14 direct entry.
`source_preparation.py requalify-discovery --date 2026-10-25 --pool-dir .\news\_sources --task-id ACTUAL-CURRENT-ALIAS --input ACTUAL-PERSISTED-PUBLIC-EVIDENCE.json --expected-sha256 ACTUAL-FILE-SHA256 --expected-failure-sha256 ACTUAL-CANONICAL-FAILURE-SHA256 --reason fixed_rendered_search_adapter`
is an explicit offline owner operation. Replace the observed identifiers and
digests; do not run placeholder values. The failure digest is the existing
`source_pool.fingerprint(task['failure'])`, not a raw log hash. The input digest
is the SHA-256 of the exact saved public evidence bytes. Inspect the candidate
current-code alias and its original checkpoint before requesting the operation.

Only the exact two-field rendered_search_evidence_invalid business failure on
a new compatible code alias can be requalified. Native validation must accept
the saved DOM/independent HTTP receipt. Original blocked tasks, attempt counts
and budgets remain intact. Policy/HTTP denials, live owners, exhausted budgets,
changed queries and conflicting succeeded results reject without mutation.
This does not retry a request, claim a lease, approve an article or publish.
Use the native absent-only evidence persistence owner and specific hardlink
approval when required; never replace it with an overwriting writer.

The existing registered Nature quantum/machine-learning subject RSS feeds may
supply discovery-topic relevance from their exact publisher subject URL when
the requested term belongs to that registered subject. The retained evidence
records this basis explicitly as article_qualification=false. It cannot supply
an absent original article, replace publication dates with updated/fetched
dates, bypass a login redirect, or satisfy paper/content/publication gates.
An RSS retention gap is not evidence of a historical day with no papers.

Author a complete source-grounded candidate draft using the existing schema,
preserving IDs, exact original URLs and publication dates, material_kind,
coverage evidence, source classes, source excerpts and capture fingerprints.
Save it while authoring_status=in_progress. If original captures are not ready,
the existing per-item capture path is explicit network work:

```powershell
& $py -B $task capture --date $releaseDay --allow-network
if ($LASTEXITCODE -ne 0) { throw 'Repair the exact article capture blocker' }
```

Admit actual source_id/item/capture records through the existing pool owner:

```powershell
& $py -B $source import-materials --date $releaseDay --pool-dir .\news\_sources --input ACTUAL-MATERIALS.json
if ($LASTEXITCODE -ne 0) { throw 'Inspect material admission' }
```

Inspect the returned invalid list even on exit zero. Discovery/capture counts
cannot inflate qualified article counts. Keep the returned material_id/revision
references keyed by candidate item ID. Existing bind-candidate emits a binding:

```powershell
& $py -B $source bind-candidate --date $releaseDay --pool-dir .\news\_sources --input AUTHORED-CANDIDATE.json --references ACTUAL-ITEM-REFERENCES.json
if ($LASTEXITCODE -ne 0) { throw 'Candidate source binding failed' }
```

Insert the returned source_pool_binding into the authored candidate via the
controlled save below. taskbox rebinds the normalized payload through the same
owner. Do not substitute a synthetic fixture or a guessed reference. Pool changes
invalidate affected frozen dependencies and require the existing controlled
revision procedure; never rewrite a source generation.

## Controlled candidate and review saves

All payload files must already contain actually authored UTF-8 JSON. No model
subprocess writes these files. This helper encodes exact bytes without routing
Chinese text through PowerShell's default code page. Each full payload/patch
must fit the existing 20000-character base64 limit. Split larger authoring work
into bounded JSON patches with fresh expected hashes. Never truncate.

Run this helper definition from the same project directory:

```powershell
function Save-TaskboxJson {
    param(
        [Parameter(Mandatory=$true)][string]$Kind,
        [Parameter(Mandatory=$true)][string]$PayloadFile,
        [Parameter(Mandatory=$true)][string]$ExpectedSha256,
        [string]$DeploymentId,
        [string]$RunDir,
        [switch]$Patch
    )
    $payloadBytes = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $PayloadFile).Path)
    $payloadBase64 = [Convert]::ToBase64String($payloadBytes)
    if ($payloadBase64.Length -gt 20000) { throw 'Use bounded JSON patches' }
    $taskArgs = @('-B', $task, $Kind, '--date', $releaseDay, '--payload-base64', $payloadBase64, '--expected-sha256', $ExpectedSha256)
    if ($Kind -eq 'candidate') {
        if ([string]::IsNullOrWhiteSpace($DeploymentId)) { throw 'Bind the approved destination identity' }
        $taskArgs += @('--expected-deployment-id', $DeploymentId)
    }
    if ($RunDir) { $taskArgs += @('--run-dir', $RunDir) }
    if ($Patch) { $taskArgs += '--patch' }
    & $py @taskArgs
    if ($LASTEXITCODE -ne 0) { throw 'Controlled save failed; retain the current bytes' }
}
```

Use absent only for a genuinely absent initial candidate. For later saves use
the exact current target hash returned by the owner or Get-FileHash -Algorithm SHA256.
The deployment ID must be the existing publisher.deployment_id of the separately
verified, approved non-secret routing configuration; do not invent an identity,
change a destination or read ossutil credentials. The prior isolated inspection
is only a clue and does not prove today's configuration or permissions.

```powershell
Save-TaskboxJson -Kind candidate -PayloadFile .\AUTHORED-CANDIDATE.json -ExpectedSha256 absent -DeploymentId APPROVED-DEPLOYMENT-ID
```

Only after every candidate field, ranked rank-1 Fable source, complete version-3
story, matching concrete example and source binding is actually finished, patch
authoring_status to complete with the current hash. Complete is still not review
approval. Saving candidates always leaves semantic_review_status=not_reviewed.

## Stage and source/story self review

```powershell
& $py -B $task stage --date $releaseDay
if ($LASTEXITCODE -ne 0) { throw 'Staging failed; inspect the exact gate' }
& $py -B $task templates --date $releaseDay
if ($LASTEXITCODE -ne 0) { throw 'Templates already exist or structure is invalid' }
& $py -B $task packet --date $releaseDay
if ($LASTEXITCODE -ne 0) { throw 'Review packet is not current' }
```

Use the returned exact run directory as $stage; never guess a hash-shaped ID.
Templates default to unreviewed; display checks default to pending with the
actual HTML hash. Repeated templates does not overwrite existing reviews.

For EVERY selected news item, read the captured original evidence. Check facts,
judgment and relevance independently. Record exact item_id, source_url,
claim_digest, bounded verbatim evidence_anchor, verdict, reason and limitation.
source_crosscheck must match the current capture's record_sha256,
response_sha256 and quoted_excerpt, reading_scope=captured_primary_excerpt,
and an aware checked_at between capture retrieval and now. If the excerpt is
insufficient, retrieve through an authorized route or narrow/revise the claim;
never imply that reading a capture is reading an entire inaccessible paper.

For the story, keep all three protocol-3 rounds and their full required fields:
literal action/state trace and changed-condition counterfactual;
source-grounded technical edges classified as source fact/derivation/teaching
assumption; and the same example's quoted question, observable, decisive step
and result. Keep honest same-task self context, exact story_sha256 and the
task card. Unsupported mechanics or unresolved semantic findings block release.

Save actually authored reviews with the helper, the current review-file hash
and the exact active stage:

```powershell
Save-TaskboxJson -Kind news-review -PayloadFile .\AUTHORED-NEWS-REVIEW.json -ExpectedSha256 CURRENT-NEWS-REVIEW-SHA256 -RunDir $stage
Save-TaskboxJson -Kind story-review -PayloadFile .\AUTHORED-STORY-REVIEW.json -ExpectedSha256 CURRENT-STORY-REVIEW-SHA256 -RunDir $stage
```

No independent-review claim is accepted. A story-only self reading view is not
context isolation. Reviewer assertions remain human/agent judgments, not proof
of scientific truth.

## Actual display, exact current HTML and strict local completion

Inspect the actual staged HTML with a browser the current task is permitted to
use. If local display is denied, do not switch protocols or tools to evade it.
An existing immutable HTTPS preview can be considered only with separate real
preview/upload permission and all pre-display content gates passing. This
repair does not authorize preview uploads. A static scan or synthetic screenshot
description is not actual display acceptance.

Required display checks are responsive_reading, formula_links_keyboard, and
print_layout. Inspect desktop/mobile reading, full story and default-collapsed
example, formulas, source links and keyboard behavior, then actual print layout.
If feedback is disabled, only its specific checks may be identity-bound N/A;
the three required display records still need actual acceptance.

The cross-surface-and-display round must contain exactly one typed display_review:
version=1, status=pass, html_sha256 equal to the exact current HTML bytes and
checks containing each of the three IDs exactly once, all status=pass.
Each evidence object contains exactly type (actual_browser or human_acceptance),
reference (actual observation/receipt), environment and timezone-aware observed_at
no later than now. Keep a meaningful reference the reviewer can inspect.
Do not manufacture a human acceptance, a screenshot or an observation time.

The existing pre-display preview exemption accepts only the typed pending state
with actual_display_pending as its sole unresolved finding and passed
cross_surface_checks. It NEVER permits seal, strict completion or publish.
Missing/null/empty display evidence cannot use the historical exemption in this
mode. Any HTML edit invalidates display acceptance, even a non-story edit.

```powershell
& $py -B $task check --date $releaseDay --run-dir $stage
# Before sealing, a missing preflight audit is expected. Fix every content/source/display failure.
& $py -B $task seal --date $releaseDay --run-dir $stage
if ($LASTEXITCODE -ne 0) { throw 'Do not finalize or publish failed reviews' }
& $py -B $task check --date $releaseDay --run-dir $stage
if ($LASTEXITCODE -ne 0) { throw 'Strict verification failed' }
& $py -B $task finalize --date $releaseDay --run-dir $stage
if ($LASTEXITCODE -ne 0) { throw 'Local finalize failed; preserve local history' }
& $py -B .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py verify --run-dir ".\news\$releaseDay" --strict
if ($LASTEXITCODE -ne 0) { throw 'Final local release is not verified' }
```

finalize explicitly uses strict local-only behavior and never uploads implicitly.
After success the stage is no longer active: do not call stage/templates/finalize
again. Use next/status to inspect the finalized edition. Local completion means
the audited HTML plus full release set and committed local index, not a staging
page, candidate, template or review packet.

## Revisions, conflicts and stopping

For a failed stage, use existing daily_authoring revision-info then revise with
the exact candidate/run/peer/evidence identities it reports, plus a concrete
reason. Run commands from the same project directory:

```powershell
& $py -B $author revision-info --date $releaseDay --run-id ACTIVE-RUN-ID
# Use all actual identities required by that result; never execute the placeholders.
& $py -B $author revise --date $releaseDay --run-id ACTIVE-RUN-ID --expected-run-sha256 CURRENT-RUN-SNAPSHOT-SHA256 --expected-sha256 CURRENT-CANDIDATE-SHA256 --reason 'Concrete source-backed correction'
```

If peer/evidence bindings are required, supply the existing bounded
--expected-peer-runs-base64 / --expected-evidence-base64 arguments. A conflict
stops without replacing unknown bytes. Preserve original candidate/run/reviews.
A new revision resets authoring/review state, keeps the date and requires fresh
source, content, story and current-HTML display checks. Never transplant old
reviews, clear a lease, delete lifecycle data or lower quotas to finish.

Stop on an actual source/permission/environment blocker, an exhausted budget,
an unresolved factual/story/display finding, changed source material or a stale
hash. Report exact edition, stage, gate, retained evidence and the smallest next
action. A waiting result is not a scheduled wakeup. Do not restore an automation.

## Existing-site delivery: later separately authorized operation

Not authorized in the current repair. After strict local completion and actual
destination/site/Bucket/profile permissions have been verified in an authorized
pilot, use only the existing publisher:

```powershell
& $py -B $task publish --date $releaseDay --config .\news_publish.local.json --expected-deployment-id APPROVED-DEPLOYMENT-ID --allow-network
if ($LASTEXITCODE -ne 0) { throw 'Keep the local release; report remote pending/blocked' }
```

Do not automatically enable a disabled/latching destination. Explicit enablement
or an already published correction needs its own existing owner and exact scope.
The wrapper binds candidate/release/deployment identities, runs strict checks,
uses the existing publisher and verifies the remote HTML. Repeated unchanged
publication returns no_change without re-upload. An uncertain upload/negative
online check remains pending; reconcile existing receipts/current online state
before another upload, never recollect or re-finalize. Do not call a pending
remote outcome published_verified. No upload/preview permission was tested here.

## Offline acceptance in this isolated package

Run only from:
C:/Users/SSS/Documents/Codex/2026-10-23/task-3/papertrace-taskbox-pipeline

```powershell
Set-Location 'C:/Users/SSS/Documents/Codex/2026-10-23/task-3/papertrace-taskbox-pipeline'
& 'D:/AI/Anaconda/python.exe' -I -S -B .\validate.py
```

The runner copies this package into a private temporary fixture, prohibits
socket/subprocess use, restricts writes, records real gate results and checks
prior artifacts plus a finite production readset. Source bytes, semantic verdicts,
browser evidence and remote objects in the fixture are explicitly synthetic.
Success proves the tested control flow, not real source truth, real display,
package-level runtime access, production installation or website delivery.
Historical r3's 12 scenarios and taskbox's 4 tests are retained evidence, not
rerun or counted as part of this acceptance.

## Ready-to-paste ordinary task instruction

在本项目现有普通 Codex 任务中执行获准的单期日报，发行日为【YYYY-MM-DD】，
冻结上海时区前一完整自然日为覆盖日。先阅读项目 AGENTS 和本技能的
references/taskbox-execution.md，检查现有本期状态，复用有效材料，按现有
来源准入、排名、完整 Fable 与一致示例要求完成中文内容。仅在当前任务逐项
对照真实来源核查 facts/judgment/relevance，明确记录 review_method=self、
same_task_self、context_isolation=none、independent_review=false；不冒充独立盲审。
实际检查当前 HTML 的桌面/移动、公式/链接/键盘与打印布局，把完整真实显示
证据绑定当前 HTML 哈希。经 seal 和 strict 门禁后先 local-only finalize 并再次
strict 核验。仅在本次实际发布授权覆盖既有目的地且权限已核实时，通过既有
publisher 推送并验证远端；否则报告严格通过的本地结果和未授权的远端步骤。
禁止另接 API、其他模型服务、额外付费、CLI 模型子调用或新审核任务。
保留来源、日期、revision、哈希、预算和幂等约束；失败不发布，不删除历史，
不恢复定时任务，不覆盖其他未提交内容。真实权限或证据不足时报告具体阻点，
不以夹具、模板或结构验证充当事实、显示或发布成功。
