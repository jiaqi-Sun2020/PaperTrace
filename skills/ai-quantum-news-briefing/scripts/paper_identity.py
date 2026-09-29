"""Shared, conservative paper classification and cross-URL identity helpers."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

ACADEMIC_HOSTS = {
    "arxiv.org": "preprint", "journals.aps.org": "aps", "aps.org": "aps",
    "nature.com": "nature", "science.org": "science", "openreview.net": "openreview",
    "openaccess.thecvf.com": "cvf", "thecvf.com": "cvf", "proceedings.mlr.press": "pmlr",
    "neurips.cc": "neurips", "aclanthology.org": "acl", "quantum-journal.org": "quantum-journal",
    "npjqi.springeropen.com": "npj-qi", "eccv.ecva.net": "ecva", "ecva.net": "ecva",
    "jmlr.org": "jmlr", "iopscience.iop.org": "iop", "ieeexplore.ieee.org": "ieee",
    "ojs.aaai.org": "aaai", "api2.openreview.net": "openreview",
}
NON_PAPER_TYPES = {"dataset", "book", "book-chapter", "report", "posted-content", "search", "landing-page"}


def host(url: Any) -> str:
    try:
        name = urlsplit(str(url or "")).hostname or ""
    except ValueError:
        return ""
    name = name.lower()
    return name[4:] if name.startswith("www.") else name


def academic_host_kind(url: Any) -> str:
    name = host(url)
    for known, kind in ACADEMIC_HOSTS.items():
        if name == known or name.endswith("." + known):
            return kind
    return ""


def article_level_path(url: Any) -> bool:
    try:
        path = urlsplit(str(url or "")).path.lower().rstrip("/")
    except ValueError:
        return False
    return bool(path and path not in {"/search", "/menu", "/papers.php", "/articles", "/recent",
                                     "/login", "/signin", "/account", "/subscribe"}
                and not path.startswith(("/toc/", "/list/", "/search/", "/collections/", "/group/",
                                         "/login/", "/signin/", "/account/", "/subscribe/")))


def normalized_doi(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text)
    text = re.sub(r"^doi:\s*", "", text)
    match = re.fullmatch(r"10\.\d{4,9}/[^\s?#]+", text.rstrip("/.,"))
    return match.group(0) if match else ""


def doi_for(item: dict[str, Any]) -> str:
    value = normalized_doi(item.get("doi"))
    if value:
        return value
    url = str(item.get("source_url") or "")
    if host(url) == "doi.org":
        return normalized_doi(url)
    match = re.search(r"10\.\d{4,9}/[^\s?#]+", url, re.I)
    return normalized_doi(match.group(0)) if match else ""


def arxiv_for(item: dict[str, Any]) -> str:
    value = str(item.get("arxiv_id") or "").strip().lower()
    if not value and host(item.get("source_url")) == "arxiv.org":
        path = urlsplit(str(item.get("source_url"))).path
        match = re.search(r"/(?:abs|pdf)/((?:\d{4}\.\d{4,5}|[a-z.-]+/\d{7}))(?:v\d+)?(?:\.pdf)?$", path, re.I)
        value = match.group(1).lower() if match else ""
    return re.sub(r"v\d+$", "", value)


def openreview_for(item: dict[str, Any]) -> str:
    value = str(item.get("openreview_id") or "").strip()
    if value:
        return value
    url = str(item.get("source_url") or "")
    if academic_host_kind(url) == "openreview":
        match = re.search(r"(?:[?&]id=|/forum/)([A-Za-z0-9_-]+)", url)
        return match.group(1) if match else ""
    return ""


def paper_kind(item: dict[str, Any]) -> str:
    """A DOI resolver is acceptable only with separate article-level venue evidence."""
    url = item.get("source_url")
    kind = academic_host_kind(url)
    publication_type = str(item.get("publication_type") or item.get("document_type") or "").lower()
    if publication_type in NON_PAPER_TYPES:
        return ""
    if host(url) == "doi.org":
        capture = item.get("source_capture") or {}
        article_url = capture.get("final_url")
        if (doi_for(item) and publication_type in {"journal-article", "proceedings-article"}
                and capture.get("status_code") == 200 and capture.get("quoted_excerpt")
                and academic_host_kind(article_url) and article_level_path(article_url)
                and host(article_url) != "doi.org"
                and (not item.get("article_source_url") or item.get("article_source_url") == article_url)):
            return academic_host_kind(article_url)
        return ""
    if not kind or not article_level_path(url):
        return ""
    capture = item.get("source_capture") or {}
    if capture and (capture.get("status_code") != 200 or
                    not academic_host_kind(capture.get("final_url")) or
                    not article_level_path(capture.get("final_url"))):
        return ""
    return kind


def same_paper(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_doi, right_doi = doi_for(left), doi_for(right)
    if left_doi and right_doi and left_doi == right_doi:
        return True
    left_arxiv, right_arxiv = arxiv_for(left), arxiv_for(right)
    if left_arxiv and right_arxiv and left_arxiv == right_arxiv:
        return True
    left_openreview, right_openreview = openreview_for(left), openreview_for(right)
    if left_openreview and right_openreview and left_openreview == right_openreview:
        return True
    for row, other in ((left, right), (right, left)):
        related = row.get("related_identifiers") or {}
        if isinstance(related, dict):
            quote = str((row.get("source_capture") or {}).get("quoted_excerpt") or "").lower()
            target_doi = doi_for(other)
            target_arxiv = arxiv_for(other)
            if (target_doi and normalized_doi(related.get("doi")) == target_doi
                    and target_doi in quote):
                return True
            if (target_arxiv and str(related.get("arxiv_id") or "").lower() == target_arxiv
                    and target_arxiv in quote):
                return True
    return False
