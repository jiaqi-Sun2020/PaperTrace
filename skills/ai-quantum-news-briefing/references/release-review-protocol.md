# Reviewed daily release protocol

New automated releases use `daily_pipeline.py run` protocol 2. `run` stages HTML,
Markdown, feedback, normalized content and an index update without publishing.
`verify --structure-only` checks those files before a semantic review exists.
The staged review is then authored, sealed, strictly verified and finalized.

The reviewer must inspect the actual source for every selected item. Generate
blank, **unreviewed** records with `review-template`; do not turn its placeholders
into a pass without reading the source. The news review has one row per selected
item, with its exact `item_id`, `claim_digest`, `source_url`, a verbatim
`evidence_anchor` from that item's `source_excerpt`, a `pass`/failure judgment,
reason and limitation. Its `claim_reviews` must separately assess `facts`,
`judgment` and `relevance`, each with a verdict, source-bound anchor, reason and
limitation; one unreviewed claim blocks sealing. Unsupported causal or
performance claims fail. New story reviews use protocol 3 with the existing
private task card and three distinct rounds. The story-only round records a
literal state trace and a changed-condition counterfactual. The source round
maps each decisive quoted action to a technical operation and classifies it as
source fact, derivation or teaching assumption. The cross-surface round quotes
the question, observable, decisive step and result of the same worked example.
Unresolved findings block approval. Record `review_method=self` unless another
reviewer really performed it.

`seal-review` checks review coverage, provenance, HTML story visibility, the
current story/example digest, each selected claim digest and the release content
digest. It writes a preflight audit and binds all three review files into the
version-2 manifest. The subsequent `verify --strict`, `finalize` and direct OSS
`publish` refuse absent, failed or stale review evidence. A passing validator
means the review is complete and bound to this release; it does not prove the
reviewer's semantic judgment. If evidence is insufficient, leave the verdict
unreviewed or failed, stop and report the exact unsupported claim.

For an 08:00 Asia/Shanghai scheduled run, use the prior complete calendar day:
`[yesterday 00:00, today 00:00)`. `manifest.date` remains the release/publication
date; `coverage.start` and `coverage.end` describe the separate evidence window.
The source config needs a timezone-aware `collection_completed_at`; any ISO dates
in its display `date_range` must match the declared covered calendar days.
Every new release, including a single-day release, needs `coverage_evidence`
with one ordered row per covered Shanghai date. Each row embeds its dated
`academic_search` and `social_search` records and binds them using canonical
`sha256:` values in `academic_search_ref` and `social_search_ref`. The validator
checks the embedded records, actual window, Science publisher-day proof, AI HOT
cursor completion and social source-class search records; arbitrary nonempty
references no longer count. `coverage_evidence_contract_version=1` in a new
manifest makes the same check run during strict verification, finalization and
direct publishing. Legacy releases remain readable, but a first remote upload
or correction needs current coverage evidence. A title or `date_range` alone
does not establish coverage. The completed manifest records
`local_finalized_at`; the OSS receipt separately records its actual publish time.

The digest is `sha256:` followed by SHA-256 of UTF-8 JSON serialized with
`sort_keys=True`, `ensure_ascii=False` and compact separators `(',', ':')`.
`academic_search` is the full venue ledger for that day. `social_search`
contains matching `coverage_start`/`coverage_end`, the complete
`ai_hot_window`, and `source_class_evidence` entries for the four required
classes; each source-class record carries an HTTPS `query_url`/`final_url`,
HTTP status, response SHA-256, retrieval time after the window, and the exact
window boundaries. The structural validator cannot prove a source's claims or
authenticate a hand-authored record; the source review must examine the
underlying response. Do not mark Science verified by manually changing a
status field. The current Science sweep records official attempts and a
Crossref snapshot but does not emit a publisher-complete listing proof. Until
an actual source and parser establish that proof, Science remains pending.

Retrieval and coverage have separate statuses. Science HTTP 403 remains in the
audit trail; a complete Crossref query only verifies the currently indexed
metadata snapshot and cannot alone make Science day coverage pass. Science RSS
cannot pass it either. AI HOT's complete dated selected pool is discovery
coverage for that source, not complete social-news coverage or item-level claim
verification. Missing, partial, stale or contradictory evidence stops release.

New manifests declare `required_story_review_protocol=3`, separate from
`opening_story.version=3`. Historical protocol-2 story reviews remain valid
for local reading and verification. Before first OSS upload or correction of
an older release, author a v3 review against its unchanged content and re-seal
it; preserve the old review sidecar before replacement. A remote no-op needs
no new upload review. This check runs before either HTML or homepage upload.

The scheduler should call `status --from-date <cutover>` first. It may treat
legacy releases as readable, but not as verified full-day coverage. If a local
release is complete and only OSS failed, use standalone `publish`; do not rerun
`run` or `finalize`. A different version for the same release date requires an
explicit correction reason, old HTML SHA-256 and fresh content review. Never
edit validation code or mark unsupported evidence as passed to finish a daily
run. Review files and receipts stay local; only the approved HTML and site index
are uploaded.
