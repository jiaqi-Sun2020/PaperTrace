# Current daily pipeline production-source snapshot — 2026-10-20

This branch preserves the current production daily AI + Quantum source. It is a snapshot, not a claim that daily production or publication has recovered. It does not deploy code, start a worker, resume an edition, alter scheduling or change permissions.

## Source and scope

Parent: 8687a0ee6e1abbd3d7d68b45c62837f6dd6a9ba2 on main. Payload bytes are read from D:/AI/PaperTrace, not copied from the older detached repair worktree (3d79e5fa2673d8f6f0f957521fa490cddc626af4).

The delta contains 38 production skill/source/test files: 22 have textual changes; 16 preserve production line endings with no textual change. Existing Fable and shared HTML dependencies already match the parent and are inherited. The accompanying manifest binds all 137 included production source/dependency paths, including unchanged inherited files. The two snapshot documentation files are newly authored metadata, not production code.

Production Git status was refused by Git's ownership protection. No safe.directory exception, identity switch, production branch change, reset, clean, stash or checkout was used. Remote main, the accessible repository worktree registry and the existing deployment receipt agree on the parent SHA. This is not certification of the entire production dirty state. Only the scoped source bytes and their hashes are certified by this snapshot.

## Included modules

- Current dated acquisition and fixed AIHOT/fixed-source discovery interfaces, original captures and material admission.
- Budget-preserving source task rebinding, bounded recovery, failure-contract diagnostics and observation persistence.
- Daily continuation, bounded closed-loop controller, owned subprocess management and worker diagnostics.
- Existing staging/revision, Fable, content/display review, strict validation and OSS publication interfaces. Runtime, credentials and enablement remain external.
- Relevant existing tests and non-sensitive fixtures. Existing unchanged dependencies remain in the parent tree.

## Explicit exclusions

No real news editions, candidates, captures, task queues, budgets, review/release records, website files, caches, backups, diagnostic output or .tmp prototypes are added. No local automation, external host/runtime policy, publishing configuration, .ossutilconfig, credentials, sessions or personal learner data is added. Mixed global .agents documentation and unrelated homepage/reader/skill changes are not included.

The 492 KB recovery-academic-checkpoints.json fixture contains 14 original cached responses and is excluded. Its new dependent module test_daily_bounded_recovery.py is also excluded intact rather than publishing real cache or silently modifying its tests. Other included modules do not import that test. Reproducing its replay coverage requires the separately retained local evidence, which is not shipped here.

The terminal-status predeployment patch and isolated child-home/receipt-v2 prototype remain undeployed and are excluded. They must not be mistaken for the currently running implementation.

## Existing test evidence — not rerun for this commit

The production deployment receipt for daily-closed-loop-2026-10-19-r4 records 804 news identities: 803 passed, 0 failures/errors, 1 symbolic-link creation skip; Fable 32/32 passed. Its receipt SHA-256 is 30884bb7f0bafd8f234cc3bad043b5a6804b50f2bef57eab11a99b8324c9458b. Static comparison found 134 scoped source paths covered by that receipt unchanged. This is historical evidence, not a new test run or a claim that the public subset reproduces all 804 identities. Symbolic-link creation and physical power loss remain untested.

## Known blockers and execution boundary

The production October 20 browser discovery first reported browser_initialization_timeout and, after its bounded wait, helper_sandbox_lock_failed. Those are production worker observations. A separate isolated CLI diagnostic failed before model/tool initialization with "Error finding codex home: Could not find home directory"; it must not be conflated with the production browser failure.

The current controller still starts Codex CLI workers for discovery, qualification, authoring, repair and independent reviews. Browser discovery and actual display need legitimate tool access. Replacing the OpenAI scheduler alone does not remove those dependencies. Source authenticity, independent/Fable review, exact HTML display binding, strict verification and remote receipt checks remain mandatory. This snapshot has not demonstrated unattended end-to-end publication and does not authorize security bypasses or old-date replay.

See daily-pipeline-snapshot-2026-10-20.manifest.json for exact source SHA-256 and Git blob identities. This branch is for inspection and backup; deployment requires its own approved, fresh-baseline process.
