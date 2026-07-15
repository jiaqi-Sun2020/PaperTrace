#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Delta-first helper for recurring AI+quantum news briefings.

The script keeps a compact JSONL story index so daily briefings can compare
against recent story IDs instead of re-reading whole previous Markdown reports.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

from briefing_contract import canonical_url as contract_canonical_url
from briefing_contract import is_lossless_text
from briefing_contract import normalize_briefing_config
from briefing_contract import story_id_for_item as contract_story_id_for_item


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


VALID_NOVELTY = {"new", "material_update", "continuing", "duplicate"}
ACADEMIC_SOURCE_DOMAINS = {
    "arxiv.org",
    "journals.aps.org",
    "nature.com",
    "science.org",
    "openreview.net",
    "openaccess.thecvf.com",
    "proceedings.mlr.press",
    "neurips.cc",
    "aclanthology.org",
    "quantum-journal.org",
}


def clean_text(value: Any, limit: int = 4000) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def project_root_from(path: Path) -> Path:
    resolved = path.resolve()
    for parent in [resolved, *resolved.parents]:
        if (parent / "news").exists() and (parent / "skills").exists():
            return parent
    return Path(__file__).resolve().parents[3]


def default_index_path(start: Path) -> Path:
    return project_root_from(start) / "news" / "_index" / "story_index.jsonl"


def parse_date(value: Any) -> date | None:
    text = clean_text(value, 120)
    match = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def infer_date(config: dict[str, Any], fallback_path: Path | None = None, explicit: str | None = None) -> date:
    for value in [explicit, config.get("date"), config.get("date_range"), config.get("briefing_title")]:
        parsed = parse_date(value)
        if parsed:
            return parsed
    if fallback_path:
        parsed = parse_date(str(fallback_path))
        if parsed:
            return parsed
    return datetime.now().date()


def canonical_url(value: Any) -> str:
    return contract_canonical_url(value)


def is_academic_delivery_item(item: dict[str, Any]) -> bool:
    """Return whether an item is backed by a formal academic venue/preprint."""
    try:
        domain = urlsplit(canonical_url(item.get("source_url"))).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
    except ValueError:
        return False
    return any(domain == known or domain.endswith("." + known) for known in ACADEMIC_SOURCE_DOMAINS)


def is_social_news_item(item: dict[str, Any]) -> bool:
    """Keep explicitly designated social-news items in their own final section."""
    section_title = clean_text(item.get("section_title"), 160).lower()
    return "社会" in section_title or "social" in section_title


def slug_ascii(value: str, fallback_prefix: str = "story") -> str:
    text = clean_text(value, 500).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    text = re.sub(r"-+", "-", text)
    if len(text) >= 3:
        return text[:100]
    digest = hashlib.sha1(clean_text(value, 1000).encode("utf-8")).hexdigest()[:12]
    return f"{fallback_prefix}-{digest}"


def story_id_for_item(item: dict[str, Any]) -> str:
    return contract_story_id_for_item(item)

    # Legacy derivation retained below for source compatibility only.
    explicit = clean_text(item.get("story_id"), 160)
    if explicit:
        return slug_ascii(explicit)
    url = canonical_url(item.get("source_url"))
    if url:
        arxiv = re.search(r"arxiv\.org/abs/([0-9]{4}\.[0-9]+)", url)
        if arxiv:
            return "arxiv-" + arxiv.group(1).replace(".", "-")
        parsed = urlsplit(url)
        domain = parsed.netloc.lower().replace("www.", "")
        path = parsed.path.strip("/")
        return slug_ascii(f"{domain} {path}")
    concepts = item.get("concepts") or []
    if isinstance(concepts, list):
        concept_text = " ".join(clean_text(c, 80) for c in concepts[:4])
    else:
        concept_text = clean_text(concepts, 160)
    basis = " ".join(
        part
        for part in [
            clean_text(item.get("source_title"), 300),
            clean_text(item.get("title"), 300),
            clean_text(item.get("category"), 120),
            concept_text,
        ]
        if part
    )
    return slug_ascii(basis)


def iter_items(config: dict[str, Any]) -> Iterable[dict[str, Any]]:
    sections = config.get("sections") or []
    if isinstance(sections, list):
        for section in sections:
            if not isinstance(section, dict):
                continue
            section_title = clean_text(section.get("title"), 160)
            raw_items = section.get("items") or []
            if not isinstance(raw_items, list):
                continue
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                copied = dict(item)
                copied.setdefault("section_title", section_title)
                yield copied
    raw_items = config.get("items") or []
    if isinstance(raw_items, list):
        for item in raw_items:
            if isinstance(item, dict):
                yield dict(item)


def item_summary(item: dict[str, Any], limit: int = 260) -> str:
    text = clean_text(
        item.get("update_summary")
        or item.get("new_facts")
        or item.get("facts")
        or item.get("summary")
        or item.get("source_excerpt")
        or item.get("title"),
        limit * 2,
    )
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def load_index(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
            if isinstance(record, dict):
                records.append(record)
    return records


@contextmanager
def index_lock(path: Path, timeout: float = 10.0):
    lock_path = path.with_name(path.name + ".lock")
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(f"timed out waiting for story index lock: {lock_path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def upsert_index(path: Path, records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    with index_lock(path):
        existing = load_index(path)
        by_key: dict[tuple[str, str], dict[str, Any]] = {}
        order: list[tuple[str, str]] = []
        for record in existing + records:
            key = (clean_text(record.get("story_id"), 240), clean_text(record.get("last_seen") or record.get("date"), 40))
            if key not in by_key:
                order.append(key)
            by_key[key] = record
        payload = "".join(json.dumps(by_key[key], ensure_ascii=False, separators=(",", ":")) + "\n" for key in order)
        atomic_write_text(path, payload)
        return len(records)


def append_index(path: Path, records: list[dict[str, Any]]) -> None:
    """Compatibility alias; writes are now idempotent atomic upserts."""
    upsert_index(path, records)


def recent_records(records: list[dict[str, Any]], today: date, days: int) -> list[dict[str, Any]]:
    cutoff = today - timedelta(days=days)
    recent: list[dict[str, Any]] = []
    for record in records:
        seen = parse_date(record.get("last_seen") or record.get("date"))
        if seen and cutoff <= seen <= today:
            recent.append(record)
    return recent


def prior_for(item: dict[str, Any], recent: list[dict[str, Any]]) -> dict[str, Any] | None:
    sid = story_id_for_item(item)
    url = canonical_url(item.get("source_url"))
    for record in reversed(recent):
        if clean_text(record.get("story_id")) == sid:
            return record
        if url and canonical_url(record.get("source_url")) == url:
            return record
    return None


def explicit_novelty(item: dict[str, Any]) -> str:
    novelty = clean_text(item.get("novelty") or item.get("delta_status"), 80).lower()
    if novelty in VALID_NOVELTY:
        return novelty
    if item.get("material_update") or item.get("update_summary") or item.get("new_facts"):
        return "material_update"
    return ""


def has_verified_update(item: dict[str, Any], prior: dict[str, Any] | None) -> bool:
    new_facts = clean_text(item.get("new_facts") or item.get("update_summary"), 2000)
    fingerprint = clean_text(item.get("evidence_fingerprint") or item.get("source_fingerprint"), 200)
    previous_fingerprint = clean_text((prior or {}).get("evidence_fingerprint") or (prior or {}).get("source_fingerprint"), 200)
    return bool(new_facts and fingerprint and fingerprint != previous_fingerprint)


def classify_item(item: dict[str, Any], recent: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    explicit = explicit_novelty(item)
    prior = prior_for(item, recent)
    if prior:
        if explicit == "duplicate":
            return "duplicate", prior
        if explicit in {"new", "material_update"}:
            return ("material_update" if has_verified_update(item, prior) else "continuing"), prior
        return "continuing", prior
    if explicit in {"material_update", "continuing", "duplicate"}:
        return explicit, prior
    if prior:
        return "continuing", prior
    return "new", None


def compact_continuing_item(item: dict[str, Any], prior: dict[str, Any] | None, item_id: str) -> dict[str, Any]:
    prior_summary = prior.get("summary") if prior else ""
    previous = clean_text(prior_summary, 220) if is_lossless_text(prior_summary) else ""
    facts = "无新增事实；保留为观察项。"
    if previous:
        facts += f" 上次记录：{previous}"
    elif prior_summary:
        facts += " 上次记录摘要因历史编码损坏而省略。"
    concepts = item.get("concepts")
    return {
        "id": item_id,
        "story_id": story_id_for_item(item),
        "novelty": "continuing",
        "title": "继续跟踪：" + clean_text(item.get("title") or item.get("source_title") or story_id_for_item(item), 140),
        "category": clean_text(item.get("category") or item.get("section_title"), 160),
        "facts": facts,
        "judgment": "等待新的官方来源、论文版本、独立报道或实质性影响后再展开。",
        "relevance": clean_text(item.get("relevance") or item.get("research_relevance"), 180),
        "evidence_level": clean_text(item.get("evidence_level"), 120),
        "source_title": clean_text(item.get("source_title") or item.get("title"), 300),
        "source_url": canonical_url(item.get("source_url")),
        "source_excerpt": clean_text(item.get("source_excerpt") or item_summary(item), 500),
        "evidence_fingerprint": clean_text(item.get("evidence_fingerprint") or item.get("source_fingerprint"), 200),
        "published_at": clean_text(item.get("published_at") or item.get("publishedAt"), 100),
        "venue_sweep_note": clean_text(item.get("venue_sweep_note"), 1000),
        "concepts": concepts if isinstance(concepts, list) else [],
        "delta_note": f"Seen before on {clean_text(prior.get('last_seen') if prior else '')}; compressed to one line.",
    }


def full_delta_item(item: dict[str, Any], novelty: str, prior: dict[str, Any] | None, item_id: str) -> dict[str, Any]:
    copied = dict(item)
    copied["id"] = clean_text(copied.get("id")) or item_id
    copied["story_id"] = story_id_for_item(copied)
    copied["novelty"] = novelty
    if prior:
        copied["delta_note"] = clean_text(
            copied.get("delta_note")
            or f"Previously seen on {clean_text(prior.get('last_seen'))}; expanded because it is marked as {novelty}.",
            500,
        )
    else:
        copied["delta_note"] = clean_text(copied.get("delta_note") or "New story; no recent index match.", 500)
    if copied.get("source_url"):
        copied["source_url"] = canonical_url(copied.get("source_url"))
    return copied


def index_record_for(item: dict[str, Any], config: dict[str, Any], seen_date: date, novelty: str) -> dict[str, Any]:
    concepts = item.get("concepts")
    return {
        "story_id": story_id_for_item(item),
        "last_seen": seen_date.isoformat(),
        "status": novelty,
        "title": clean_text(item.get("title") or item.get("source_title"), 220),
        "summary": item_summary(item),
        "category": clean_text(item.get("category") or item.get("section_title"), 160),
        "source_title": clean_text(item.get("source_title"), 300),
        "source_url": canonical_url(item.get("source_url")),
        "briefing_title": clean_text(config.get("briefing_title") or config.get("title"), 300),
        "briefing_path": clean_text(config.get("briefing_path"), 1000),
        "date_range": clean_text(config.get("date_range") or config.get("date"), 300),
        "concepts": [clean_text(c, 120) for c in concepts[:8]] if isinstance(concepts, list) else [],
        "evidence_fingerprint": clean_text(item.get("evidence_fingerprint") or item.get("source_fingerprint"), 200),
        "published_at": clean_text(item.get("published_at") or item.get("publishedAt"), 100),
        "first_seen": clean_text(item.get("first_seen") or seen_date.isoformat(), 40),
    }


def transform_config(
    config: dict[str, Any],
    index_records: list[dict[str, Any]],
    today: date,
    lookback_days: int,
    continuing_mode: str,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    config = normalize_briefing_config(config, require_source_url=True)
    recent = recent_records(index_records, today, lookback_days)
    groups: dict[str, list[dict[str, Any]]] = {"new": [], "material_update": [], "continuing": [], "social": []}
    academic_items: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    index_updates: list[dict[str, Any]] = []
    counters = {"new": 0, "material_update": 0, "continuing": 0, "duplicate": 0}

    for raw_item in iter_items(config):
        novelty, prior = classify_item(raw_item, recent)
        if novelty == "duplicate":
            counters["duplicate"] += 1
            skipped.append(
                {
                    "story_id": story_id_for_item(raw_item),
                    "title": clean_text(raw_item.get("title") or raw_item.get("source_title"), 220),
                    "reason": "explicit duplicate",
                }
            )
            continue
        if novelty == "continuing":
            counters["continuing"] += 1
            if continuing_mode == "skip":
                skipped.append(
                    {
                        "story_id": story_id_for_item(raw_item),
                        "title": clean_text(raw_item.get("title") or raw_item.get("source_title"), 220),
                        "reason": "seen recently without material update",
                        "last_seen": clean_text(prior.get("last_seen") if prior else ""),
                    }
                )
                continue
            item_id = f"C{counters['continuing']:03d}"
            delta_item = compact_continuing_item(raw_item, prior, item_id)
            if is_academic_delivery_item(raw_item):
                academic_items.append(delta_item)
            elif is_social_news_item(raw_item):
                groups["social"].append(delta_item)
            else:
                groups["continuing"].append(delta_item)
            index_updates.append(index_record_for(raw_item, config, today, "continuing"))
            continue
        counters[novelty] += 1
        if is_social_news_item(raw_item):
            item_id = f"S{len(groups['social']) + 1:03d}"
        else:
            item_id = ("N" if novelty == "new" else "U") + f"{len(groups[novelty]) + 1:03d}"
        delta_item = full_delta_item(raw_item, novelty, prior, item_id)
        if is_academic_delivery_item(raw_item):
            academic_items.append(delta_item)
        elif is_social_news_item(raw_item):
            groups["social"].append(delta_item)
        else:
            groups[novelty].append(delta_item)
        index_updates.append(index_record_for(delta_item, config, today, novelty))

    sections: list[dict[str, Any]] = []
    if academic_items:
        sections.append({"title": "Academic research and venue evidence", "items": academic_items})
    if groups["social"]:
        sections.append({"title": "社会新闻", "items": groups["social"]})
    if groups["new"]:
        sections.append({"title": "今日新增", "items": groups["new"]})
    if groups["material_update"]:
        sections.append({"title": "重大更新", "items": groups["material_update"]})
    if groups["continuing"]:
        sections.append({"title": "持续跟踪，一句话", "items": groups["continuing"]})

    transformed = dict(config)
    transformed["sections"] = sections
    transformed["delta_policy"] = {
        "mode": "delta_first",
        "index_lookback_days": lookback_days,
        "continuing_mode": continuing_mode,
        "generated_for_date": today.isoformat(),
        "rule": "Expand only new stories and material updates; compress or skip recently seen stories.",
    }
    transformed["delta_counts"] = counters
    transformed["skipped_duplicates"] = skipped

    manifest = {
        "date": today.isoformat(),
        "lookback_days": lookback_days,
        "continuing_mode": continuing_mode,
        "counts": counters,
        "sections": [{"title": section["title"], "items": len(section["items"])} for section in sections],
        "skipped": skipped,
    }
    return transformed, manifest, index_updates


def render_markdown(config: dict[str, Any]) -> str:
    lines: list[str] = []
    title = clean_text(config.get("briefing_title") or config.get("title") or "AI + Quantum 日报")
    lines.append(f"# {title}")
    lines.append("")
    if config.get("date_range"):
        lines.append(f"- 覆盖窗口：{clean_text(config.get('date_range'), 500)}")
    policy = config.get("delta_policy")
    if isinstance(policy, dict):
        lines.append(
            "- Delta policy："
            + clean_text(policy.get("rule"), 240)
            + f" Lookback={clean_text(policy.get('index_lookback_days'), 20)} days; continuing={clean_text(policy.get('continuing_mode'), 40)}."
        )
    if config.get("summary"):
        lines.append(f"- 一句话：{clean_text(config.get('summary'), 500)}")
    lines.append("")

    for section in config.get("sections", []):
        if not isinstance(section, dict):
            continue
        lines.append(f"## {clean_text(section.get('title'), 160)}")
        lines.append("")
        items = section.get("items") or []
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            title_text = clean_text(item.get("title") or item.get("source_title") or f"Item {index}", 220)
            lines.append(f"{index}. **{title_text}**")
            if item.get("category") or item.get("novelty"):
                bits = [clean_text(item.get("category"), 120), clean_text(item.get("novelty"), 80)]
                lines.append("   标签：" + " / ".join(bit for bit in bits if bit))
            if item.get("facts"):
                lines.append(f"   事实：{clean_text(item.get('facts'), 1200)}")
            if item.get("judgment"):
                lines.append(f"   判断：{clean_text(item.get('judgment'), 900)}")
            if item.get("relevance"):
                lines.append(f"   对你的启发：{clean_text(item.get('relevance'), 900)}")
            if item.get("delta_note"):
                lines.append(f"   Delta：{clean_text(item.get('delta_note'), 500)}")
            source_title = clean_text(item.get("source_title") or "source", 300)
            source_url = clean_text(item.get("source_url"), 1200)
            if source_url:
                lines.append(f"   来源：[{source_title}]({source_url})")
            elif source_title:
                lines.append(f"   来源：{source_title}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def cmd_context(args: argparse.Namespace) -> int:
    index_path = Path(args.index).expanduser().resolve() if args.index else default_index_path(Path.cwd())
    records = load_index(index_path)
    today = date.fromisoformat(args.date) if args.date else datetime.now().date()
    recent = recent_records(records, today, args.days)
    latest_by_story: dict[str, dict[str, Any]] = {}
    for record in recent:
        sid = clean_text(record.get("story_id"))
        if sid:
            latest_by_story[sid] = record
    rows = sorted(latest_by_story.values(), key=lambda row: clean_text(row.get("last_seen")), reverse=True)[: args.limit]
    for row in rows:
        print(
            " | ".join(
                [
                    clean_text(row.get("story_id"), 120),
                    f"last_seen={clean_text(row.get('last_seen'), 20)}",
                    f"status={clean_text(row.get('status'), 40)}",
                    clean_text(row.get("summary"), 220),
                    clean_text(row.get("source_url"), 180),
                ]
            )
        )
    return 0


def cmd_index_config(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser().resolve()
    index_path = Path(args.index).expanduser().resolve() if args.index else default_index_path(config_path)
    config = normalize_briefing_config(load_json(config_path), config_path, require_source_url=True)
    seen_date = infer_date(config, config_path, args.date)
    records = [index_record_for(item, config, seen_date, args.status) for item in iter_items(config)]
    raise SystemExit("Direct index-config writes are disabled; use daily_pipeline.py finalize after verification.")
    print(f"Indexed {len(records)} items into {index_path}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve() if args.output else config_path.with_name(config_path.stem + "_delta.json")
    index_path = Path(args.index).expanduser().resolve() if args.index else default_index_path(config_path)
    config = normalize_briefing_config(load_json(config_path), config_path, require_source_url=True)
    today = infer_date(config, config_path, args.date)
    transformed, manifest, index_updates = transform_config(
        config=config,
        index_records=load_index(index_path),
        today=today,
        lookback_days=args.days,
        continuing_mode=args.continuing_mode,
    )
    write_json(output_path, transformed)
    manifest_path = Path(args.manifest).expanduser().resolve() if args.manifest else output_path.with_name(output_path.stem + "_manifest.json")
    write_json(manifest_path, manifest)
    if args.markdown_output:
        markdown_path = Path(args.markdown_output).expanduser().resolve()
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown(transformed), encoding="utf-8")
    if args.update_index:
        print("Index update deferred: daily_pipeline.py finalize owns the verified index commit.")
    print(f"Wrote delta config: {output_path}")
    print(f"Wrote manifest: {manifest_path}")
    if args.markdown_output:
        print(f"Wrote markdown: {Path(args.markdown_output).expanduser().resolve()}")
    print(
        "Counts: "
        + ", ".join(f"{key}={value}" for key, value in manifest["counts"].items())
        + "; indexed=0"
    )
    return 0


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    context = subparsers.add_parser("context", help="Print compact recent-story context for the next briefing prompt.")
    context.add_argument("--index", help="Story index JSONL. Defaults to news/_index/story_index.jsonl.")
    context.add_argument("--date", help="Reference date, YYYY-MM-DD. Defaults to today.")
    context.add_argument("--days", type=int, default=7, help="Recent-story lookback window.")
    context.add_argument("--limit", type=int, default=60, help="Maximum lines to print.")
    context.set_defaults(func=cmd_context)

    index_config = subparsers.add_parser("index-config", help="Append all items from an existing briefing config to the story index.")
    index_config.add_argument("--config", required=True, help="Briefing feedback config JSON.")
    index_config.add_argument("--index", help="Story index JSONL. Defaults to news/_index/story_index.jsonl.")
    index_config.add_argument("--date", help="Seen date, YYYY-MM-DD. Defaults from config/path.")
    index_config.add_argument("--status", default="seen", help="Status to store in the index.")
    index_config.set_defaults(func=cmd_index_config)

    apply = subparsers.add_parser("apply", help="Rewrite a candidate briefing config into delta-first sections.")
    apply.add_argument("--config", required=True, help="Candidate briefing feedback config JSON.")
    apply.add_argument("--output", help="Output delta config JSON.")
    apply.add_argument("--index", help="Story index JSONL. Defaults to news/_index/story_index.jsonl.")
    apply.add_argument("--manifest", help="Output manifest JSON.")
    apply.add_argument("--markdown-output", help="Optional Markdown report generated from the delta config.")
    apply.add_argument("--date", help="Briefing date, YYYY-MM-DD. Defaults from config/path.")
    apply.add_argument("--days", type=int, default=7, help="Recent-story lookback window.")
    apply.add_argument(
        "--continuing-mode",
        choices=["one-line", "skip"],
        default="one-line",
        help="How to handle recently seen stories without material updates.",
    )
    apply.add_argument("--update-index", action="store_true", help="Deprecated compatibility flag; index commit is deferred to daily_pipeline finalize.")
    apply.set_defaults(func=cmd_apply)

    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
