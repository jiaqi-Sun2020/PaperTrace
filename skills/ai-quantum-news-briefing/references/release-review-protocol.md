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
performance claims fail. The story review uses
the existing protocol-2 task card and three distinct rounds, including a
story-only comprehension pass and a story/example/source consistency pass.
Record `review_method=self` unless another reviewer really performed it.

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
Multi-day
backfill also needs `coverage_evidence` with one row per covered date, each
containing `date`, `academic_search_ref` and `social_search_ref`; these records
are retained in the manifest's `coverage.daily_search_evidence`. A title or
`date_range` alone does not establish coverage. The completed manifest records
`local_finalized_at`; the OSS receipt separately records its actual publish time.

The scheduler should call `status --from-date <cutover>` first. It may treat
legacy releases as readable, but not as verified full-day coverage. If a local
release is complete and only OSS failed, use standalone `publish`; do not rerun
`run` or `finalize`. A different version for the same release date requires an
explicit correction reason, old HTML SHA-256 and fresh content review. Never
edit validation code or mark unsupported evidence as passed to finish a daily
run. Review files and receipts stay local; only the approved HTML and site index
are uploaded.
