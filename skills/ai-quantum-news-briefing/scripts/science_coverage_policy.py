"""Science-specific publication boundary for new daily releases.

This is deliberately narrower than a general missing-source exemption.  An
unavailable Science inventory is not evidence that the journal published zero
articles, and a Science-family DOI is not necessarily a Science-journal DOI.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit


NOTICE = "本期未能核验 Science 当日完整目录，因此未纳入其论文；这不表示当日零发表。"


def science_skipped(academic_search: Any) -> bool:
    if not isinstance(academic_search, dict) or academic_search.get("academic_search_version") != 3:
        return False
    rows = [row for row in academic_search.get("rows", [])
            if isinstance(row, dict) and row.get("venue") == "science"]
    return bool(rows) and all(row.get("result") == "skipped_unavailable" for row in rows)


def science_journal_candidate(item: dict[str, Any]) -> bool:
    """Exclude Science or ambiguous science.org academic records, not sister journals."""
    url = str(item.get("source_url") or "")
    identity = " ".join(str(item.get(key) or "") for key in
                        ("source_url", "source_excerpt", "doi", "journal_title"))
    if re.search(r"10\.1126/science\.[a-z0-9._-]+", identity, re.I):
        return True
    if str(item.get("journal_title") or "").strip().lower() == "science":
        return True
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    if host not in {"science.org", "www.science.org"}:
        return False
    if "/10.1126/science." in path:
        return True
    sister_prefixes = ("/10.1126/sciadv.", "/10.1126/sciimmunol.",
                       "/10.1126/scirobotics.", "/10.1126/scisignal.",
                       "/10.1126/scitranslmed.")
    return not any(prefix in path for prefix in sister_prefixes)
