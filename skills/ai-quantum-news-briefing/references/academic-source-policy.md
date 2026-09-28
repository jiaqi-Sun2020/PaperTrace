# Academic Source Policy

Use this reference when the daily briefing needs academic frontier coverage. The goal is to avoid arXiv-only tunnel vision while keeping claims source-grounded.

## First Principle

Treat arXiv as fast discovery, not final authority. For important academic claims, prefer venue or publisher pages when available, then use arXiv as preprint context. The daily briefing should answer two separate questions:

1. What is new?
2. What is institutionally credible enough to cite as academic evidence?

Those are not the same question. arXiv is excellent for speed; PRL/PRA/Nature/Science/CVPR/ICLR/ICML/NeurIPS/Quantum Journal are stronger evidence when the work has appeared there.

## Source Tiers

Tier 1 primary venues and publishers:

- APS: PRL, PRA, PRX, PRX Quantum via `journals.aps.org`
- Nature Portfolio: `nature.com`, including Nature, Nature Physics, Nature Machine Intelligence, Nature Communications, npj Quantum Information
- Science / AAAS: `science.org`
- OpenReview: ICLR and some workshop / conference review pages. If a user says "ICLA", usually treat it as ICLR unless context suggests another venue.
- CVF: CVPR / ICCV / ECCV proceedings via `openaccess.thecvf.com`
- PMLR: ICML / AISTATS / COLT via `proceedings.mlr.press`
- NeurIPS proceedings: `neurips.cc`
- ACL Anthology: `aclanthology.org` for NLP / LLM methodology papers
- Quantum journal: `quantum-journal.org`

Tier 2 useful discovery / indexing:

- arXiv for fast preprints
- Semantic Scholar / Crossref / Google Scholar snippets only as discovery aids
- Official lab blogs when they link to a paper, code, benchmark, or technical report

Tier 3 media / commentary:

- MIT Technology Review, Quanta, Phys.org, IEEE Spectrum, The Gradient, VentureBeat, etc. Use for context, not as the sole source for technical claims.

## Daily Workflow

1. Start with AI HOT selected items for broad AI industry/product/research candidates.
2. For academic frontier sections, run venue-aware searches across APS, Nature, Science, OpenReview/ICLR, CVF/CVPR, PMLR/ICML, NeurIPS, ACL Anthology, Quantum journal, and arXiv.
3. Promote a paper into the final briefing only when at least one of these is true:
   - it is from a primary venue/publisher;
   - it is a new arXiv preprint with direct relevance to QWTA/CTQW/Quantum Walk GNN/AI for Quantum;
   - it is an official lab technical report with enough method detail.
4. Add top-level `academic_search` to the briefing config. This is mandatory when the config contains academic or quantum items. It must list the checked venues and compact topic-level results.
5. For each arXiv-only item, add `venue_sweep_note` to the config. Keep it short, e.g. `Checked APS PRL/PRA/PRX, Nature, Science, OpenReview/ICLR, CVF/CVPR, PMLR/ICML, NeurIPS, ACL, Quantum Journal; no venue page found in window; treated as preprint.`
6. Mark arXiv-only items as `preprint` and avoid overclaiming peer-reviewed status.
7. A venue ledger row is not checked merely because it contains a search URL, HTTP 200, or `checked_no_hit`. Preserve retrieval failures separately from coverage conclusions. Non-Science required venues still stop publication when their evidence fails.
8. Science's official search and `/toc/science/0/0` discovery page are attempted separately; the eTOC RSS only corroborates items. The Crossref ISSN `0036-8075` query is a dated, paginated discovery snapshot, not proof of a complete publisher-day inventory. Without a complete, date-scoped publisher listing, record `skipped_unavailable`, exclude Science-journal candidates before ranking, and show the omission notice. Never call this zero Science publications. Restoring `verified` requires a new publisher-backed parser, not a hand-authored listing payload.
9. Coverage evidence is distinct from content evidence. DOI, title or abstract metadata alone cannot substantiate a paper's mechanism, performance or novelty claim; review the article or another suitable primary source separately.
10. Use the adversarial audit before finalizing; missing or incomplete `academic_search` is a failure.

## Optional expansion after the required day

When the normal academic target remains unattainable, use `academic_venue_sweep.py --expanded` to inspect PRX Quantum, Nature Physics, Nature Communications, npj Quantum Information, PMLR AISTATS/COLT, CVF ICCV, and ECVA ECCV separately. These eight pages are discovery attempts, not new required daily coverage rows. The ECCV accepted-paper list can be preliminary; verify a final paper-level source before selecting an item. A successful page response never proves a complete dated inventory or an article's claims.

Only after this expansion, search the 14-calendar-day academic context window. Preserve the exact original publication date and label earlier items `近期回看`. The separate lookback sweep is not the required one-day `academic_search` and cannot repair an unavailable non-Science required daily source. A version-1 `delivery_expansion` record binds optional attempts, the lookback sweep, both prior days of 72-hour social discovery and their hashes before a `verified_shortfall` release may relax quantity minima.

## Academic Evidence Contract

For every item in `Academic frontier` or `Quantum physics / quantum computing`, fill these fields when possible:

- `evidence_level`: one of `peer-reviewed venue`, `conference proceedings`, `official research publication`, `arXiv preprint`, `official technical report`, `media context`.
- `source_url`: the strongest primary URL found.
- `venue_sweep_note`: required when `source_url` is arXiv.
- `source_excerpt`: one concise factual anchor, not marketing language.
- `concepts`: include method terms, not only broad labels.

If the source is arXiv but the topic is likely to have a venue version, search before finalizing. If no venue page is found, say so instead of silently relying on arXiv.

Top-level config must also include:

```json
{
  "academic_search": {
    "academic_search_version": 3,
    "date_range": "YYYY-MM-DD",
    "required_venues": ["aps-prl", "aps-pra", "aps-prx", "nature", "science", "openreview-iclr", "cvf-cvpr", "pmlr-icml", "neurips", "acl", "quantum-journal", "arxiv"],
    "topics": [
      {
        "term": "quantum walk graph neural network",
        "checked_venues": ["aps-prl", "aps-pra", "aps-prx", "nature", "openreview-iclr", "cvf-cvpr", "pmlr-icml", "neurips", "acl", "quantum-journal", "arxiv"],
        "primary_hits": [],
        "status": "evidenced_with_science_gap"
      }
    ]
  }
}
```

## Query Templates

Use web search with source restrictions when browsing:

- `site:journals.aps.org/prl quantum walk OR Hamiltonian simulation`
- `site:journals.aps.org/pra quantum walk OR quantum machine learning`
- `site:nature.com quantum computing Hamiltonian simulation`
- `site:science.org quantum computing AI`
- `site:openreview.net ICLR graph neural network quantum`
- `site:openaccess.thecvf.com CVPR vision language action robot model`
- `site:proceedings.mlr.press ICML graph neural networks physics`
- `site:neurips.cc quantum machine learning graph neural network`
- `site:aclanthology.org language model agent evaluation`
- `site:quantum-journal.org quantum walk Hamiltonian`
- `site:arxiv.org/abs quantum walk graph neural network`

For final reports, cite the primary source URL used for the claim.

## Low-Token Search Pattern

When token budget matters, do not paste long search results into context. Use compact venue buckets:

```text
topic: quantum walk graph neural network
window: 2026-07-07..2026-07-09
checked: APS=0, Nature=0, Science=unavailable, OpenReview=0, CVF=0, PMLR=0, NeurIPS=0, QuantumJournal=0, arXiv=2
promote: arXiv:2607.xxxxx because directly relevant to CTQW/QWTA; label as preprint
```

This preserves the audit trail without spending tokens on irrelevant snippets.
