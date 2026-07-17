#!/usr/bin/env python3
"""Versioned, atomic completion state for resumable formal readers.

Raw PDF evidence stays immutable.  This module owns only derived reader state:
one independently-validatable JSON record per source block/object and a compact
run-state summary.  It deliberately cannot translate, crop, or invent cards.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from formula_contract import atomic_formula_issues, bilingual_math_issues, source_math_evidence_issues, source_math_inventory_issues


SCHEMA_VERSION = 3
PIPELINE_VERSION = "formal-reader-v3"
SOURCE_MATH_EVIDENCE_CONTRACT = "source-math-evidence-v2"
STATUS_VALUES = {"pending", "pass", "invalid"}
RECORD_KINDS = {"block", "formula", "figure", "table", "algorithm", "reference"}
MATH_RE = re.compile(r'(\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$\$[\s\S]*?\$\$|(?<!\\)\$(?!\s)(?:\\.|[^$]){1,800}?(?<!\\)\$)')
PLACEHOLDER_RE = re.compile(r"translation-required|block-note-required|\[.*?(?:TODO|pending|draft).*?\]", re.I)
ANCHOR_RE = re.compile(r'(?m)^<a\s+id=["\']([^"\']+)["\']\s*>\s*</a>\s*$')
ZH_LABEL = "\u4e2d\u6587"
NOTES_LABEL = "\u6ce8\u91ca"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def atomic_write_json(path: Path, value: dict[str, Any], *, validator: Any | None = None) -> None:
    if validator is not None:
        validator(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checked = json.loads(temporary.read_text(encoding="utf-8"))
    if validator is not None:
        validator(checked)
    temporary.replace(path)


def atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def source_text(row: dict[str, Any]) -> str:
    return str(
        row.get("original")
        or row.get("original_text")
        or row.get("text")
        or row.get("caption_original")
        or row.get("caption")
        or ""
    )


def source_math_inventory_required(value: str) -> bool:
    """Decide at bootstrap whether a source formula block needs full review.

    Existing completed bundles are not silently rewritten during a contract
    upgrade.  Newly seeded formula evidence with OCR/layout math residue is
    explicitly marked pending for a source component inventory instead.
    """

    if source_math_evidence_issues(value, field="Source evidence"):
        return True
    return bool(re.search(r"(?m)(?:^|\n)\s*[^\n]{0,80}(?:=|∝|≤|≥|≲|≳)[^\n]{1,80}", value))


def source_math_inventory_evidence(value: str) -> list[str]:
    """Return immutable-source signals that require component reconstruction.

    Extraction type is only a hint: theorem math also appears in paragraph and
    caption rows. These labels are derived evidence for the completion gate,
    not rendered reader content.
    """

    return list(dict.fromkeys(source_math_evidence_issues(value, field="Source evidence")))


def evidence_hash(row: dict[str, Any]) -> str:
    payload = {
        "id": row.get("id") or row.get("block_id") or "",
        "page": row.get("page"),
        "type": row.get("type") or "",
        "original": source_text(row),
        "caption_id": row.get("caption_id") or "",
        "source_block_id": row.get("source_block_id") or "",
        "source_page_image": row.get("source_page_image") or "",
    }
    return sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def record_filename(stable_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "--", stable_id).strip(".-") + ".json"


def records_dir(reader_dir: Path) -> Path:
    return reader_dir / "reader_wiki" / "completion_blocks"


def record_path(reader_dir: Path, stable_id: str) -> Path:
    return records_dir(reader_dir) / record_filename(stable_id)


def run_state_path(reader_dir: Path) -> Path:
    return reader_dir / "reader_wiki" / "completion_run_state.json"


def canonical_path(reader_dir: Path) -> Path:
    return reader_dir / "reader_wiki" / "canonical_reader.md"


def formal_status_path(reader_dir: Path) -> Path:
    return reader_dir / "reader_wiki" / "formal_status.json"


def validate_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version", "stable_id", "record_kind", "block_type", "source_anchor", "source_page",
        "source_evidence_hash", "source_pdf_sha256", "original", "zh", "notes", "object_metadata",
        "status", "validation_errors", "updated_at",
    }
    missing = sorted(required - set(record))
    if missing:
        errors.append("missing required fields: " + ", ".join(missing))
        return errors
    if record["schema_version"] != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if record["record_kind"] not in RECORD_KINDS:
        errors.append("unknown record_kind")
    if record["status"] not in STATUS_VALUES:
        errors.append("unknown status")
    if not isinstance(record["source_page"], int) or record["source_page"] < 1:
        errors.append("source_page must be a positive integer")
    for key in ("stable_id", "block_type", "source_anchor", "source_evidence_hash", "source_pdf_sha256", "original", "zh", "notes", "updated_at"):
        if not isinstance(record[key], str):
            errors.append(f"{key} must be a string")
    if not re.fullmatch(r"[a-f0-9]{64}", str(record["source_evidence_hash"])):
        errors.append("source_evidence_hash must be a lowercase SHA-256")
    if not re.fullmatch(r"[a-f0-9]{64}", str(record["source_pdf_sha256"])):
        errors.append("source_pdf_sha256 must be a lowercase SHA-256")
    if not isinstance(record["object_metadata"], dict):
        errors.append("object_metadata must be an object")
    if not isinstance(record["validation_errors"], list) or not all(isinstance(item, str) for item in record["validation_errors"]):
        errors.append("validation_errors must be a list of strings")
    if errors or record["status"] != "pass":
        return errors

    kind = record["record_kind"]
    original = record["original"].strip()
    zh = record["zh"].strip()
    metadata = record["object_metadata"]
    if kind == "block":
        if not original or not zh:
            errors.append("pass block requires Original and Chinese text")
        if original == zh and re.search(r"[A-Za-z]{4}", original):
            errors.append("pass block Chinese text duplicates translatable Original text")
        if PLACEHOLDER_RE.search(original + "\n" + zh):
            errors.append("pass block contains a placeholder")
        for field, value in (("Original", original), ("Chinese", zh)):
            errors.extend(atomic_formula_issues(value, field=field))
        if (
            metadata.get("source_math_inventory_required") or "source_math_inventory" in metadata
        ):
            # Formula source blocks carry a component inventory.  This is a
            # fail-closed evidence contract, not a presentational hint.
            errors.extend(source_math_inventory_issues(metadata, original, zh, block_id=str(record["stable_id"])))
        elif metadata.get("bilingual_math_contract") == "exact-v1":
            errors.extend(bilingual_math_issues(original, zh, block_id=str(record["stable_id"])))
    elif kind == "formula":
        if not MATH_RE.search(original):
            errors.append("pass formula requires Original-side LaTeX")
    elif kind == "figure":
        asset_path = str(metadata.get("asset_path") or "")
        if not asset_path or "assets/source_pages/" in asset_path.replace("\\", "/"):
            errors.append("pass figure requires a tight object asset, never a source page")
        if not metadata.get("asset_sha256") or not metadata.get("bbox"):
            errors.append("pass figure requires asset hash and source-page bbox")
        if not metadata.get("original_caption") or not metadata.get("zh_caption"):
            errors.append("pass figure requires original and Chinese captions")
    elif kind == "table":
        representation = str(metadata.get("representation") or "")
        if representation not in {"semantic_table", "tight_crop"}:
            errors.append("pass table requires semantic_table or tight_crop")
        if not metadata.get("original_caption") or not metadata.get("zh_caption"):
            errors.append("pass table requires original and Chinese captions")
        if representation == "semantic_table" and not str(metadata.get("markdown_table") or "").strip():
            errors.append("semantic table requires markdown_table")
        if representation == "tight_crop" and not metadata.get("asset_path"):
            errors.append("tight-crop table requires asset_path")
    elif kind == "algorithm":
        if metadata.get("representation") != "latex_compiled_algorithm":
            errors.append("pass algorithm requires latex_compiled_algorithm representation")
        for key in (
            "latex_source_path", "latex_source_sha256", "compiled_asset_path",
            "compiled_asset_sha256", "compile_manifest_path", "compile_manifest_sha256",
            "compile_engine",
        ):
            if not str(metadata.get(key) or "").strip():
                errors.append(f"pass algorithm requires {key}")
        if int(metadata.get("numbered_steps") or 0) < 2:
            errors.append("pass algorithm requires every source-numbered step")
    elif kind == "reference":
        if not original:
            errors.append("pass reference requires original-only citation text")
        if zh:
            errors.append("reference records must not have Chinese translation text")
    return errors


def assert_valid_record(record: dict[str, Any]) -> None:
    errors = validate_record(record)
    if errors:
        raise ValueError("invalid completion record: " + "; ".join(errors))


def new_record(*, stable_id: str, record_kind: str, block_type: str, source_anchor: str, source_page: int,
               source_evidence_hash: str, source_pdf_sha256: str, object_metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "stable_id": stable_id,
        "record_kind": record_kind,
        "block_type": block_type,
        "source_anchor": source_anchor,
        "source_page": source_page,
        "source_evidence_hash": source_evidence_hash,
        "source_pdf_sha256": source_pdf_sha256,
        "original": "",
        "zh": "",
        "notes": "",
        "object_metadata": object_metadata or {},
        "status": "pending",
        "validation_errors": [],
        "updated_at": utc_now(),
    }


def expected_records(source_map: dict[str, Any]) -> list[dict[str, Any]]:
    paper = source_map.get("paper") or {}
    pdf_hash = str(paper.get("source_pdf_sha256") or "").lower()
    if not re.fullmatch(r"[a-f0-9]{64}", pdf_hash):
        raise ValueError("source_map paper.source_pdf_sha256 is required for v3 completion state")
    rows: list[dict[str, Any]] = []
    for source in source_map.get("blocks", []) or []:
        if not isinstance(source, dict):
            continue
        anchor = str(source.get("id") or source.get("block_id") or "")
        if not anchor:
            continue
        block_type = str(source.get("type") or "paragraph").lower()
        kind = "reference" if block_type == "reference" else "block"
        block_metadata = {"source_object": False}
        math_evidence = source_math_inventory_evidence(source_text(source))
        if block_type in {"equation_or_formula", "formula"} and not math_evidence:
            math_evidence = ["Source evidence: source_map declares a formula/equation block"]
        if kind == "block" and block_type != "algorithm" and math_evidence:
            block_metadata["source_math_inventory_required"] = True
            block_metadata["source_math_evidence_contract"] = SOURCE_MATH_EVIDENCE_CONTRACT
            block_metadata["source_math_evidence"] = math_evidence
        rows.append(new_record(
            stable_id=f"{kind}:{anchor}", record_kind=kind, block_type=block_type, source_anchor=anchor,
            source_page=int(source.get("page") or 1), source_evidence_hash=evidence_hash(source),
            source_pdf_sha256=pdf_hash,
            object_metadata=block_metadata,
        ))
        if block_type in {"formula", "equation_or_formula"}:
            rows.append(new_record(
                stable_id=f"formula:{anchor}:01", record_kind="formula", block_type=block_type, source_anchor=anchor,
                source_page=int(source.get("page") or 1), source_evidence_hash=evidence_hash(source),
                source_pdf_sha256=pdf_hash, object_metadata={"formula_index": 1},
            ))
    for collection, kind in (("figures", "figure"), ("tables", "table"), ("algorithms", "algorithm")):
        for source in source_map.get(collection, []) or []:
            if not isinstance(source, dict):
                continue
            anchor = str(source.get("id") or "")
            if not anchor:
                continue
            metadata = {
                "source_object": True,
                "caption_original": source.get("caption_original") or source.get("caption") or "",
                "caption_id": source.get("caption_id") or "",
                "source_block_id": source.get("source_block_id") or "",
                "source_page_image": source.get("source_page_image") or "",
            }
            rows.append(new_record(
                stable_id=f"{kind}:{anchor}", record_kind=kind, block_type=kind, source_anchor=anchor,
                source_page=int(source.get("page") or 1), source_evidence_hash=evidence_hash(source),
                source_pdf_sha256=pdf_hash, object_metadata=metadata,
            ))
    return sorted(rows, key=lambda row: row["stable_id"])


def load_record(reader_dir: Path, stable_id: str) -> dict[str, Any] | None:
    path = record_path(reader_dir, stable_id)
    if not path.exists():
        return None
    record = read_json(path)
    assert_valid_record(record)
    return record


def write_record(reader_dir: Path, record: dict[str, Any]) -> Path:
    record["updated_at"] = utc_now()
    previous_errors = [str(item) for item in record.get("validation_errors", [])]
    structural_errors = validate_record(record)
    record["validation_errors"] = list(dict.fromkeys([*previous_errors, *structural_errors]))
    if record.get("status") == "pass" and structural_errors:
        record["status"] = "invalid"
    atomic_write_json(record_path(reader_dir, str(record["stable_id"])), record, validator=assert_valid_record)
    return record_path(reader_dir, str(record["stable_id"]))


def seed_records(reader_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    source_map = read_json(reader_dir / "source_map.json")
    planned = expected_records(source_map)
    issues: list[str] = []
    records: list[dict[str, Any]] = []
    for baseline in planned:
        existing = load_record(reader_dir, baseline["stable_id"])
        if existing is None:
            write_record(reader_dir, baseline)
            records.append(baseline)
            continue
        if existing["source_evidence_hash"] == baseline["source_evidence_hash"] and existing["source_pdf_sha256"] == baseline["source_pdf_sha256"]:
            baseline_metadata = baseline.get("object_metadata") or {}
            if baseline_metadata.get("source_math_inventory_required"):
                metadata = existing.setdefault("object_metadata", {})
                metadata.update({
                    "source_math_inventory_required": True,
                    "source_math_evidence_contract": SOURCE_MATH_EVIDENCE_CONTRACT,
                    "source_math_evidence": list(baseline_metadata.get("source_math_evidence") or []),
                })
                inventory = metadata.get("source_math_inventory")
                if not isinstance(inventory, dict) or inventory.get("status") != "complete":
                    existing["status"] = "invalid"
                    existing["validation_errors"] = [
                        "source-math evidence contract upgraded; author a complete source_math_inventory before formal rendering"
                    ]
                    issues.append(f"{existing['stable_id']}: source-math inventory is required by {SOURCE_MATH_EVIDENCE_CONTRACT}")
                write_record(reader_dir, existing)
            records.append(existing)
            continue
        existing["status"] = "invalid"
        existing["validation_errors"] = ["immutable source evidence changed; record must be re-completed"]
        write_record(reader_dir, existing)
        records.append(existing)
        issues.append(f"{existing['stable_id']}: immutable source evidence changed")
    return records, issues


def load_all_records(reader_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(records_dir(reader_dir).glob("*.json")):
        record = read_json(path)
        assert_valid_record(record)
        rows.append(record)
    return rows


def update_run_state(reader_dir: Path, *, last_failure_gate: str = "") -> dict[str, Any]:
    source_map_path = reader_dir / "source_map.json"
    source_map = read_json(source_map_path)
    planned = expected_records(source_map)
    records = {row["stable_id"]: row for row in load_all_records(reader_dir)}
    missing = [row["stable_id"] for row in planned if row["stable_id"] not in records]
    pending = sorted([key for key, row in records.items() if row.get("status") == "pending"] + missing)
    invalid = sorted(key for key, row in records.items() if row.get("status") == "invalid")
    passed = sorted(key for key, row in records.items() if row.get("status") == "pass")
    state = {
        "schema_version": SCHEMA_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "generated_at": utc_now(),
        "source_map_path": "source_map.json",
        "source_map_sha256": sha256_file(source_map_path),
        "source_pdf_sha256": str((source_map.get("paper") or {}).get("source_pdf_sha256") or "").lower(),
        "expected_records": len(planned),
        "completed_records": len(passed),
        "pending_records": pending,
        "invalid_records": invalid,
        "status": "pass" if not pending and not invalid and len(passed) == len(planned) else "incomplete",
        "last_failure_gate": last_failure_gate,
    }
    atomic_write_json(run_state_path(reader_dir), state)
    return state


def ensure_object_inventory(reader_dir: Path) -> Path:
    """Seed the source-wide inventory without overwriting existing human work.

    ``objects`` remains compatible with the preflight renderer (figures,
    tables, and algorithms).  ``source_items`` is the exhaustive first-pass
    inventory for prose, formulas, bibliography, captions, and objects.
    """
    path = reader_dir / "reader_wiki" / "object_inventory.json"
    source_map_path = reader_dir / "source_map.json"
    source_hash = sha256_file(source_map_path)
    source_map = read_json(source_map_path)
    objects: list[dict[str, Any]] = []
    source_items: list[dict[str, Any]] = []
    for row in source_map.get("blocks", []) or []:
        if not isinstance(row, dict):
            continue
        source_id = str(row.get("id") or row.get("block_id") or "")
        if not source_id:
            continue
        block_type = str(row.get("type") or "paragraph").lower()
        primary_kind = "reference" if block_type == "reference" else "block"
        source_items.append({
            "id": source_id,
            "stable_id": f"{primary_kind}:{source_id}",
            "kind": primary_kind,
            "block_type": block_type,
            "page": row.get("page"),
            "source_evidence_hash": evidence_hash(row),
            "status": "completion-required",
        })
        if block_type in {"formula", "equation_or_formula"}:
            source_items.append({
                "id": source_id,
                "stable_id": f"formula:{source_id}:01",
                "kind": "formula",
                "block_type": block_type,
                "page": row.get("page"),
                "source_evidence_hash": evidence_hash(row),
                "status": "completion-required",
            })
    for collection, kind in (("figures", "figure"), ("tables", "table"), ("algorithms", "algorithm")):
        for row in source_map.get(collection, []) or []:
            if not isinstance(row, dict):
                continue
            source_id = str(row.get("id") or "")
            objects.append({
                "id": source_id,
                "kind": kind,
                "page": row.get("page"),
                "source_object_id": source_id,
                "source_block_id": str(row.get("caption_id") or row.get("source_block_id") or ""),
                "asset_path": "",
                "bbox": [],
                "representation": "",
                "status": "completion-required",
            })
            source_items.append({
                "id": source_id,
                "stable_id": f"{kind}:{source_id}",
                "kind": kind,
                "page": row.get("page"),
                "source_evidence_hash": evidence_hash(row),
                "status": "completion-required",
            })
    if path.exists():
        current = read_json(path)
        if str(current.get("source_map_sha256") or "") != source_hash:
            # A source-math override must never write through this file, but a
            # historical helper could accidentally replace the object ledger
            # with a formula inventory.  Recover only that unmistakable shape
            # from the authoritative completion records; do not overwrite an
            # inventory that claims another source map.
            if (
                current.get("contract") == "source-math-inventory-v1"
                and not current.get("objects")
                and not current.get("source_items")
            ):
                recovered = {
                    "version": 3,
                    "role": "derived_source_and_object_completion_inventory",
                    "source_map_sha256": source_hash,
                    "objects": objects,
                    "source_items": source_items,
                }
                by_stable_id = {str(record.get("stable_id") or ""): record for record in load_all_records(reader_dir)}
                for row in recovered["objects"]:
                    record = by_stable_id.get(f"{row['kind']}:{row['id']}")
                    if record:
                        row.update(record.get("object_metadata") or {})
                        row["status"] = str(record.get("status") or row["status"])
                atomic_write_json(path, recovered)
                return path
            raise ValueError("object_inventory.json belongs to a different source_map and cannot be overwritten")
        if isinstance(current.get("source_items"), list):
            return path
        # Preserve all human-completed object metadata; append only the new
        # source-wide inventory required by v3.
        current["version"] = 3
        current["role"] = "derived_source_and_object_completion_inventory"
        current["source_items"] = source_items
        atomic_write_json(path, current)
        return path
    atomic_write_json(path, {
        "version": 3,
        "role": "derived_source_and_object_completion_inventory",
        "source_map_sha256": source_hash,
        "objects": objects,
        "source_items": source_items,
    })
    return path


def reader_is_formal_ready(reader_dir: Path) -> tuple[bool, list[str]]:
    problems: list[str] = []
    state_path = run_state_path(reader_dir)
    if not state_path.exists():
        return False, ["missing completion_run_state.json"]
    state = read_json(state_path)
    if state.get("pipeline_version") != PIPELINE_VERSION:
        problems.append("completion run state pipeline version is stale")
    if state.get("status") != "pass":
        problems.append("completion records are not all pass")
    preflight_path = reader_dir / "reader_wiki" / "preflight_manifest.json"
    if not preflight_path.exists() or read_json(preflight_path).get("status") != "pass":
        problems.append("object preflight is not pass")
    # A stale marker invalidates only the previous HTML artifact. It is not a
    # permanent completion-state failure: a later v3 record/preflight/compile/
    # render/audit sequence may supersede that old artifact.
    return not problems, problems


def mark_stale(reader_dir: Path, reasons: Iterable[str]) -> dict[str, Any]:
    wiki = reader_dir / "reader_wiki"
    old_manifest = wiki / "formal_artifact_manifest.json"
    legacy_manifest = wiki / "legacy_formal_artifact_manifest.json"
    if old_manifest.exists() and not legacy_manifest.exists():
        shutil.copyfile(old_manifest, legacy_manifest)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "status": "stale",
        "updated_at": utc_now(),
        "reasons": list(reasons),
        "html_path": "reader_interactive.html",
        "html_sha256": sha256_file(reader_dir / "reader_interactive.html") if (reader_dir / "reader_interactive.html").exists() else "",
    }
    atomic_write_json(formal_status_path(reader_dir), payload)
    atomic_write_json(wiki / "formal_artifact_manifest.json", {
        "version": SCHEMA_VERSION,
        "formal_status": "stale",
        "updated_at": payload["updated_at"],
        "reasons": payload["reasons"],
        "artifacts": {"html": {"path": "reader_interactive.html", "sha256": payload["html_sha256"]}},
    })
    return payload


def clear_stale_after_audit(reader_dir: Path) -> None:
    path = formal_status_path(reader_dir)
    payload = read_json(path) if path.exists() else {}
    payload.update({
        "schema_version": SCHEMA_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "status": "formal_pass",
        "updated_at": utc_now(),
        "html_path": "reader_interactive.html",
        "html_sha256": sha256_file(reader_dir / "reader_interactive.html"),
        "formal_artifact_manifest": "reader_wiki/formal_artifact_manifest.json",
    })
    payload.pop("reasons", None)
    atomic_write_json(path, payload)


def _split_legacy_segments(markdown: str) -> dict[str, str]:
    matches = list(ANCHOR_RE.finditer(markdown))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        result[match.group(1)] = markdown[match.end():end]
    return result


def _label(segment: str, label: str, next_labels: tuple[str, ...]) -> str:
    start = re.search(rf'(?ms)^\*\*{re.escape(label)}:\*\*\s*', segment)
    if not start:
        return ""
    begin = start.end()
    ends = []
    for next_label in next_labels:
        found = re.search(rf'(?ms)^\*\*{re.escape(next_label)}:\*\*\s*', segment[begin:])
        if found:
            ends.append(begin + found.start())
    end = min(ends) if ends else len(segment)
    return segment[begin:end].strip()


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def migrate_legacy(reader_dir: Path, legacy_paper_path: Path | None = None) -> dict[str, Any]:
    """Safely copy only independently valid legacy text into pending/pass records.

    It never trusts a legacy ledger, never mutates raw evidence, and never
    declares an object/formula formal without the v3 checks. ``legacy_paper_path``
    may be an external read-only legacy bundle; all records/status files are
    still written only under ``reader_dir``.
    """
    records, seed_issues = seed_records(reader_dir)
    source_map = read_json(reader_dir / "source_map.json")
    source_rows = {
        str(row.get("id") or row.get("block_id") or ""): row
        for row in source_map.get("blocks", []) or [] if isinstance(row, dict)
    }
    legacy_path = legacy_paper_path.resolve() if legacy_paper_path is not None else reader_dir / "paper.md"
    segments = _split_legacy_segments(legacy_path.read_text(encoding="utf-8", errors="replace")) if legacy_path.exists() else {}
    migrated = 0
    passed = 0
    for record in records:
        if record["record_kind"] != "block":
            continue
        segment = segments.get(record["source_anchor"], "")
        source = source_rows.get(record["source_anchor"], {})
        original = _label(segment, "Original", (ZH_LABEL, NOTES_LABEL, "Notes"))
        zh = _label(segment, ZH_LABEL, (NOTES_LABEL, "Notes"))
        notes = _label(segment, NOTES_LABEL, ("Notes",)) or _label(segment, "Notes", ())
        if not original and not zh:
            continue
        record["original"] = original
        record["zh"] = zh
        record["notes"] = notes
        record["object_metadata"]["legacy_candidate"] = True
        record["object_metadata"]["legacy_paper_sha256"] = sha256_file(legacy_path) if legacy_path.exists() else ""
        source_value = source_text(source)
        trustworthy = bool(original and zh and _normalized(original) and _normalized(source_value))
        if trustworthy and _normalized(original) == _normalized(source_value) and not PLACEHOLDER_RE.search(original + "\n" + zh):
            record["status"] = "pass"
        else:
            record["status"] = "pending"
            record["validation_errors"] = ["legacy content copied as a candidate; v3 source/encoding review required"]
        write_record(reader_dir, record)
        migrated += 1
        passed += int(record["status"] == "pass")
    state = update_run_state(reader_dir, last_failure_gate="legacy migration requires v3 object/formula/reference preflight")
    stale = mark_stale(reader_dir, [
        "legacy output predates formal-reader-v3 completion records",
        "legacy source map/object inventory cannot prove complete figure/table/algorithm/reference coverage",
        "legacy HTML must not be reported as current formal output",
    ])
    return {"migrated_candidates": migrated, "passed_records": passed, "seed_issues": seed_issues, "run_state": state, "stale": stale}


def _record_map(reader_dir: Path) -> dict[str, dict[str, Any]]:
    return {record["stable_id"]: record for record in load_all_records(reader_dir)}


def compile_canonical_markdown(reader_dir: Path, *, materialize_paper: bool) -> Path:
    state = update_run_state(reader_dir)
    if state["status"] != "pass":
        raise ValueError("cannot compile canonical reader while completion records remain pending or invalid")
    source_map = read_json(reader_dir / "source_map.json")
    title = str((source_map.get("paper") or {}).get("title") or "Untitled Paper")
    records = _record_map(reader_dir)
    algorithm_object_anchors = set()
    for row in records.values():
        if row.get("record_kind") != "algorithm" or row.get("status") != "pass":
            continue
        algorithm_object_anchors.add(row["source_anchor"])
        source_block_id = str((row.get("object_metadata") or {}).get("source_block_id") or "")
        if source_block_id:
            algorithm_object_anchors.add(source_block_id)
    lines = [f"# {title}", "", "> Canonical reader derived solely from v3 pass records.", "", "## Bilingual Reader", ""]
    for record in sorted(records.values(), key=lambda row: (row["source_page"], row["stable_id"])):
        if record["status"] != "pass":
            continue
        kind = record["record_kind"]
        anchor = record["source_anchor"]
        metadata = record["object_metadata"]
        if kind == "block":
            # An algorithm source block and its algorithm object often share
            # one immutable ID.  Render the latter once as the authoritative
            # full line-by-line card instead of producing duplicate HTML IDs.
            if record.get("block_type") == "algorithm" and anchor in algorithm_object_anchors:
                continue
            lines.extend([f'<a id="{anchor}"></a>', f"**Source:** p.{record['source_page']} {anchor}", "", f"**Original:** {record['original']}", "", f"**{ZH_LABEL}:** {record['zh']}", "", f"**{NOTES_LABEL}:** {record['notes']}", ""])
        elif kind == "reference":
            lines.extend([f'<a id="{anchor}"></a>', f"**Source:** p.{record['source_page']} {anchor}", "", f"**Reference list (original only):** {record['original']}", ""])
        elif kind == "figure":
            lines.extend([f'<a id="{anchor}"></a>', f"### Figure {anchor}", "", f"**Source:** p.{record['source_page']} {anchor}", "", f"![{anchor}]({metadata['asset_path']})", "", f"**Original caption:** {metadata['original_caption']}", "", f"**{ZH_LABEL}图注:** {metadata['zh_caption']}", "", f"**Reading note:** {record['notes']}", ""])
        elif kind == "table":
            lines.extend([f'<a id="{anchor}"></a>', f"### Table {anchor}", "", f"**Source:** p.{record['source_page']} {anchor}", ""])
            if metadata.get("representation") == "semantic_table":
                lines.extend([str(metadata["markdown_table"]).strip(), ""])
            else:
                lines.extend([f"![{anchor}]({metadata['asset_path']})", ""])
            lines.extend([f"**Original caption:** {metadata['original_caption']}", "", f"**{ZH_LABEL}表注:** {metadata['zh_caption']}", "", f"**Reading note:** {record['notes']}", ""])
        elif kind == "algorithm":
            number = re.sub(r"\D+", "", anchor) or anchor
            lines.extend([
                f'<a id="{anchor}"></a>',
                f"### Algorithm {number} ({anchor})",
                "",
                f"**Source:** p.{record['source_page']} {anchor}",
                "",
                f"**Algorithm LaTeX:** `{metadata['latex_source_path']}`",
                "",
                f"**Compiled algorithm:** `{metadata['compiled_asset_path']}`",
                "",
                f"**Compile manifest:** `{metadata['compile_manifest_path']}`",
                "",
                f"**Reading note:** {record['notes']}",
                "",
            ])
    content = "\n".join(lines).rstrip() + "\n"
    destination = canonical_path(reader_dir)
    atomic_write_text(destination, content)
    if materialize_paper:
        atomic_write_text(reader_dir / "paper.md", content)
    return destination


def render_progress_html(reader_dir: Path) -> Path:
    state = update_run_state(reader_dir)
    records = _record_map(reader_dir)
    rows = []
    for record in sorted(records.values(), key=lambda row: (row["source_page"], row["stable_id"])):
        if record["status"] != "pass":
            continue
        if record["record_kind"] not in {"block", "reference"}:
            continue
        if record["record_kind"] == "reference":
            body = f"<p>{html.escape(record['original'])}</p>"
        else:
            body = f"<p><strong>Original</strong> {html.escape(record['original'])}</p><p><strong>{ZH_LABEL}</strong> {html.escape(record['zh'])}</p>"
        rows.append(f"<section id=\"{html.escape(record['source_anchor'], quote=True)}\"><small>p.{record['source_page']} · {html.escape(record['stable_id'])}</small>{body}</section>")
    pending_preview = "<br>".join(html.escape(item) for item in (state["pending_records"] + state["invalid_records"])[:40]) or "none"
    document = f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><title>Reader progress</title>
<style>body{{font-family:system-ui;max-width:960px;margin:32px auto;padding:0 18px}}.banner{{background:#7f1d1d;color:#fff;padding:16px;font-weight:800}}section{{border:1px solid #ddd;padding:14px;margin:12px 0}}small{{color:#666}}</style>
</head><body><div class=\"banner\">INCOMPLETE / NOT FORMAL — feedback export, profile handoff, and formal manifests are disabled.</div>
<h1>Reader progress</h1><p>Passed: {state['completed_records']} / {state['expected_records']}; pending: {len(state['pending_records'])}; invalid: {len(state['invalid_records'])}</p>
<h2>Remaining records</h2><p>{pending_preview}</p><h2>Passed content only</h2>{''.join(rows) or '<p>No validated blocks yet.</p>'}</body></html>"""
    path = reader_dir / "reader_progress.html"
    atomic_write_text(path, document)
    return path
