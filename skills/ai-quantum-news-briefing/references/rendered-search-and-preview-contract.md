# Rendered search discovery and pre-display preview contract (r4)

This is an isolated, production-baseline increment. It does not certify a
release, a browser observation's semantic truth, or PutObject permission.

## Discovery evidence

`source_class_evidence` may contain `evidence_type=rendered_search_observation`,
`version=1`, for the existing reputable-media, company-social and executive-social
queries. The targets are explicitly bounded to the public targets declared in
`RENDERED_SEARCH_TARGETS`. New engines or targets require a separate contract
review. AI HOT continues to require its existing dated, paginated HTTP evidence.

The record binds the exact HTTPS query, positive `site:` targets and source
class, exclusive `after:`/`before:` labels, Shanghai coverage bounds, the query
actually displayed in the supported browser, declared browser provenance and
recording time, public result URLs/count or an observed no-results message.
`observation_sha256` is the canonical JSON SHA-256 of `observation`. It is a DOM
observation digest, never an HTTP response digest. Unknown fields, versions and
types are refused rather than interpreted through the older HTTP contract.

`http_receipt` is a separate anonymous request receipt. Its `response_hash` is
recomputed from its bounded `body_base64` raw bytes, with `hash_scope=raw_http_bytes`.
The query and date window must match; its retrieval time remains independent of
the browser recording time. A JavaScript bootstrap is retained as exactly that
response. The browser results are not asserted to have come from those bytes.
No cookies, account UI, browser profile or browser-private response export is
used. Producers must retain the original public observation and raw receipt.

Every rendered observation has `scope=observed_page_only`,
`exhaustive_account_coverage=false`, `zero_account_publications_established=false`,
`publication_dates_verified=false`, and `personalization_possible=true`. A
missing next-page observation is `null` (unknown); it is not manufactured as
pagination completion. The no-results case means zero matches to this indexed
query, never zero publications by an account. First-page results are sufficient
only to evidence this bounded discovery action. They do not establish complete
publisher coverage or authorize `verified_shortfall`.

Legacy untyped HTTP discovery retains its existing meaning. The validator checks
declared provenance and integrity, not authenticity of the observer or scientific
truth. Selected articles still require original capture, dates, identity and
facts/judgment/relevance review. No result URL is added automatically to news
quotas; quantity, diversity, Science and academic-family gates are unchanged.

## Pre-display preview

Only the `preview` transport entry point calls
`validate_bundle(... require_manifest_binding=False, require_audit_report=False,
preview_display_pending=True)`. Formal `validate_review`, seal-review, strict
verification, finalize and formal OSS publishing retain the strict default.
The opt-in is a code-level phase argument, not a candidate JSON approval flag.
Bound or report-requiring validation rejects this opt-in.

The current run, source capture, coverage, candidate and HTML checks still apply.
Every selected news claim and the first two protocol-3 story rounds must pass.
The third round still supplies all material declarations, exact quotes,
question/observable/step/result alignment and a passed
`cross_surface_checks={judgment:pass, reason:...}`. Its only unresolved finding
may be `{kind:actual_display_pending, reason:...}`. Its `judgment` is `pending`.

The typed `display_review` is version 1, binds the actual `html_sha256`, and has
exactly three checks: `responsive_reading`, `formula_links_keyboard`,
`print_layout`. Before preview, all three check statuses and the overall status
are `pending`. Failed, unknown, mixed, stale, historical or incomplete pending
records are refused. Partial acceptance must not be flattened into a pass;
retain it separately until this bounded record can honestly be completed.

After actual browser or human acceptance, each check can become `pass` only with
`evidence={type:actual_browser|human_acceptance, reference:..., environment:...,
observed_at:<aware ISO timestamp>}`. Then the overall status and third judgment
become `pass`, and unresolved becomes empty. Deleting warnings, changing a word
to PASS, an HTTP 200 or a static test is not actual display evidence. The full
HTML digest is checked again at formal bundle validation. These declarations
require real retained evidence; programs cannot independently prove honesty.

Historical completed review records without the typed block remain compatible.
They cannot use the pending exception. Preview receipts remain transport-only:
`formal_publish=false`, `browser_display_status=not_tested`. They are not formal
publication receipts or display acceptance. Versioning safety, immutable preview
keys, exact remote-byte reconciliation, active-run uniqueness and commit-time
checks are unchanged.

## Operational order and stop point

From the project root after a separately approved, baseline-checked deployment:

1. Retain public discovery observations and independent HTTP bytes; assemble the
   typed records without editing raw evidence. Recompute the social evidence ref.
2. Use existing controlled authoring/revision and source admission interfaces;
   generate staging through the production generator. Do not hand-edit HTML.
3. Complete actual content and the first two story reviews plus correspondence
   checks. Record only actual display as pending against the generated HTML.
4. Preview only after OSS safety/permission checks succeed and preview authority
   applies. Review the exact HTTPS page, including mobile/desktop, themes,
   formulas, links/keyboard and print. Preserve evidence, not inferred PASS.
5. Update the bound actual display record, then run seal-review, preflight audit,
   strict verify, finalize and remote delivery only under their separate authority.

This delivery stops at review. It installs no production code, writes no real
candidate/staging/review/receipt and performs no real upload. The r3b installer
has a frozen three-file identity and cannot install this new increment. Reuse
its recovery protocol only after a separately frozen and tested scope adaptation;
do not edit its constants and run it on production.
