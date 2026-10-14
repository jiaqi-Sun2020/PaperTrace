"""Versioned, derived reading analysis; never rewrites immutable paper evidence.

Validators check coverage, identities and freshness, not semantic truth.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit
from logic_diagrams import diagrams_in_notes, notes_prose, validate_logic_diagram

CONTRACT_FILE = "reading_analysis_contract.json"
RELATIONS = {"cites", "uses", "extends", "tests", "challenges", "related"}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analysis_records(records):
    return [r for r in records if r.get("record_kind") != "reference" and not (
        r.get("record_kind") == "block" and r.get("block_type") == "algorithm"
        and (r.get("object_metadata") or {}).get("source_algorithm_contract") == "compiled-source-language-v1"
    )]


def notes_digest(records):
    return digest({r["stable_id"]: r.get("notes", "") for r in analysis_records(records)})


def safe_url(value):
    try:
        url = urlsplit(value)
        return url.scheme == "https" and bool(url.hostname) and not url.username and not url.password
    except (ValueError, TypeError):
        return False


def iso_date(value):
    try:
        return date.fromisoformat(value).isoformat() == value
    except (ValueError, TypeError):
        return False


def strong_identity_keys(identity):
    if not isinstance(identity, dict):
        return set()
    keys = set()
    doi = str(identity.get("doi") or "").strip().casefold()
    doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi)
    if doi:
        keys.add("doi:" + doi)
    arxiv = str(identity.get("arxiv") or "").strip().casefold()
    arxiv = re.sub(r"^(?:https?://arxiv\.org/(?:abs|pdf)/|arxiv:\s*)", "", arxiv)
    arxiv = re.sub(r"(?:v\d+)?(?:\.pdf)?$", "", arxiv)
    if arxiv:
        keys.add("arxiv:" + arxiv)
    return keys


def validate_history(history, anchors, source_hash):
    errors = []
    if not isinstance(history, dict) or history.get("schema_version") != 1:
        return ["paper history requires schema_version 1"]
    if history.get("source_map_sha256") != source_hash:
        errors.append("paper history belongs to a different source map")
    if history.get("status") not in {"verified", "partial", "not_checked"}:
        errors.append("paper history requires an explicit evidence status")
    if not iso_date(history.get("checked_as_of")):
        errors.append("paper history lacks checked_as_of")
    if not isinstance(history.get("searches"), list) or not history.get("gaps"):
        errors.append("paper history must disclose search scope and gaps")
    nodes = history.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return errors + ["paper history lacks the current paper node"]
    ids = [n.get("id") for n in nodes if isinstance(n, dict)]
    if len(ids) != len(nodes) or len(set(ids)) != len(ids) or any(not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", str(i)) for i in ids):
        errors.append("paper history node IDs must be unique safe identifiers")
    if sum(bool(n.get("current")) for n in nodes) != 1:
        errors.append("paper history must identify exactly one current paper")
    for node in nodes:
        for field in ("title", "summary", "question", "method", "advance", "results", "limitations"):
            if not isinstance(node.get(field), str) or not node[field].strip():
                errors.append(f"history node {node.get('id')} lacks {field}")
        unresolved_current = node.get("current") and history.get("status") in {"partial", "not_checked"} and node.get("url") is None
        if (not safe_url(node.get("url")) and not unresolved_current) or not node.get("identity"):
            errors.append("history node requires a primary HTTPS URL and paper identity")
        dates = node.get("dates")
        if not isinstance(dates, list) or not dates:
            errors.append("history node lacks typed publication dates")
        else:
            for row in dates:
                if row.get("kind") == "unknown" and row.get("date") is None and history.get("status") in {"partial", "not_checked"}:
                    continue
                if row.get("kind") not in {"preprint", "published", "revised"} or not iso_date(row.get("date")) or not safe_url(row.get("source_url")):
                    errors.append("history dates require kind, ISO date and primary source")
        if any(a not in anchors for a in node.get("source_anchors", [])):
            errors.append("history node cites an unknown reader anchor")
    seen_identities = set()
    for node in nodes:
        identities = strong_identity_keys(node.get("identity"))
        if seen_identities & identities:
            errors.append("duplicate strong paper identity in history")
        seen_identities.update(identities)
    for edge in history.get("relations", []):
        if edge.get("from") not in ids or edge.get("to") not in ids or edge.get("from") == edge.get("to") or edge.get("type") not in RELATIONS:
            errors.append("invalid history relation endpoints/type")
        evidence = edge.get("evidence") or {}
        if not safe_url(evidence.get("url")) or not evidence.get("excerpt") or not evidence.get("locator") or not evidence.get("checked_on"):
            errors.append("history relation lacks primary evidence, locator or verification date")
        if not edge.get("explanation"):
            errors.append("history relation lacks explanation")
        if evidence.get("source_anchor") not in anchors and not evidence.get("source_capture"):
            errors.append("history relation requires a local source anchor or captured primary evidence")
    return errors


def validate_reading_analysis(reader_dir, records, summary):
    """Absent declaration is historical compatibility, not new-authoring approval."""
    wiki = reader_dir / "reader_wiki"
    path = wiki / CONTRACT_FILE
    if not path.exists():
        state_path = wiki / "completion_run_state.json"
        if state_path.exists() and json.loads(state_path.read_text(encoding="utf-8")).get("reading_analysis_version"):
            return {}, {}, ["reading analysis declaration removed from an upgraded reader"]
        return {}, {}, []
    errors = []
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
        history = json.loads((wiki / "paper_history.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, {}, [f"reading analysis missing/malformed artifact: {type(exc).__name__}"]
    source_hash = file_hash(reader_dir / "source_map.json")
    if contract.get("reading_analysis_version") != 1 or contract.get("required") is not True or contract.get("source_map_sha256") != source_hash:
        errors.append("invalid/stale reading analysis declaration")
    if summary.get("schema_version") != 2 or not summary.get("logic_chain"):
        errors.append("reading analysis requires paper summary v2 with logic_chain")
    for record in analysis_records(records):
        note = record.get("notes", "").strip()
        if not note or re.search(r"\[.*required\]|这一块用于定位|逻辑位置：本文主题是|待补充", note):
            errors.append(f"{record['stable_id']}: missing/non-specific logical analysis")
    anchors = {r.get("source_anchor") for r in records}
    visual_version = contract.get('logic_visualization_version')
    state_path = wiki / 'completion_run_state.json'
    if state_path.exists() and json.loads(state_path.read_text(encoding='utf-8')).get('logic_visualization_version') == 1 and visual_version != 1:
        errors.append('logic visualization declaration removed from an upgraded reader')
    if visual_version not in {None, 1}:
        errors.append('unsupported logic visualization contract')
    for record in analysis_records(records):
        try:
            diagrams = diagrams_in_notes(record.get('notes', ''))
            if visual_version == 1 and not diagrams:
                errors.append(record['stable_id'] + ': missing authored logic visualization')
            if diagrams and not notes_prose(record.get('notes', '')):
                errors.append(record['stable_id'] + ': diagram must not replace full explanation')
            for diagram in diagrams:
                errors.extend(record['stable_id'] + ': ' + e for e in validate_logic_diagram(diagram, anchors))
        except ValueError as exc:
            errors.append(record['stable_id'] + ': ' + str(exc))
    errors.extend(validate_history(history, anchors, source_hash))
    for edge in history.get("relations", []):
        evidence = edge.get("evidence") or {}
        anchor = evidence.get("source_anchor")
        if anchor:
            original = next((r.get("original", "") for r in records if r.get("source_anchor") == anchor and r.get("record_kind") == "block"), "")
            if str(evidence.get("excerpt") or "") not in original:
                errors.append("history relation quote is absent from its source anchor")
        else:
            capture = evidence.get("source_capture") or {}
            relative = str(capture.get("path") or "")
            capture_path = (wiki / relative).resolve()
            try:
                capture_path.relative_to((wiki / "history_sources").resolve())
                source = json.loads(capture_path.read_text(encoding="utf-8"))
                if file_hash(capture_path) != capture.get("sha256") or source.get("url") != evidence.get("url") or evidence.get("excerpt") not in source.get("text", ""):
                    errors.append("history relation captured evidence is stale/unmatched")
            except (ValueError, OSError):
                errors.append("history relation lacks safe captured evidence")
    review_path = wiki / "reading_analysis_review.json"
    try:
        review = json.loads(review_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return contract, history, errors + ["missing reading analysis self-review"]
    expected = {"notes_sha256": notes_digest(records), "summary_sha256": file_hash(wiki / "paper_summary.json"), "history_sha256": file_hash(wiki / "paper_history.json")}
    if review.get("bound_content") != expected or review.get("review_type") != "self_review":
        errors.append("reading analysis review is stale or not honestly labelled self_review")
    if set(review.get("reviewed_record_ids") or []) != {r["stable_id"] for r in analysis_records(records)}:
        errors.append("reading analysis review does not cover all non-reference records")
    rounds = review.get("rounds") or []
    if len(rounds) != 8 or {r.get("round") for r in rounds} != set(range(1, 9)):
        errors.append("reading analysis requires eight review rounds")
    for row in rounds:
        if row.get("result") != "pass" or not row.get("judgment") or not row.get("limitation"):
            errors.append("unresolved/unsupported reading analysis review round")
        quotes = row.get("quotes") or []
        if not quotes:
            errors.append("review round lacks actual text evidence")
        for quote in quotes:
            rid = quote.get("record_id")
            actual = next((r.get("notes", "") for r in records if r.get("stable_id") == rid), "")
            if not quote.get("text") or quote["text"] not in actual:
                errors.append("reading analysis review quote is not present in the authored note")
    return contract, history, errors


def declare_reading_analysis(reader_dir, *, bind_frozen=True):
    """Called for new bundles, not silently applied to legacy completed readers."""
    path = reader_dir / "reader_wiki" / CONTRACT_FILE
    from completion_state import atomic_write_json
    source = json.loads((reader_dir / "source_map.json").read_text(encoding="utf-8"))
    pdf_hash = str((source.get("paper") or {}).get("source_pdf_sha256") or "")
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if not (bind_frozen and existing.get("source_map_binding") == "pending_freeze"
                and existing.get("reading_analysis_version") == 1 and existing.get("required") is True
                and existing.get("source_pdf_sha256") == pdf_hash):
            return
    atomic_write_json(path, {"reading_analysis_version": 1, "required": True,
                             "logic_visualization_version": 1,
                             "source_map_sha256": file_hash(reader_dir / "source_map.json") if bind_frozen else "",
                             "source_map_binding": "frozen" if bind_frozen else "pending_freeze",
                             "source_pdf_sha256": pdf_hash})
