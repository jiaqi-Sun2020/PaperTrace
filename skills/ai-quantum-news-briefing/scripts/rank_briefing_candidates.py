#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministically rank and quota-select daily briefing candidates.

The ranker is intentionally metadata-first and auditable. It first rejects
items that cannot satisfy the publication evidence contract, then computes a
separate academic or social-news score, and finally applies a deterministic
MMR-style diversity selection with delivery quotas.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from briefing_contract import canonical_url, normalize_briefing_config
from news_delta import classify_item, load_index, recent_records


ALGORITHM_VERSION = "news-ranker-v1"
ACADEMIC_DOMAINS = {
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
    "npjqi.springeropen.com",
}
DEFAULT_RANKING_POLICY: dict[str, Any] = {
    "enabled": True,
    "algorithm_version": ALGORITHM_VERSION,
    "deterministic": True,
    "academic": {
        "minimum_items": 7,
        "target_items": 8,
        "maximum_items": 8,
        "minimum_new_items": 4,
        "maximum_new_items": 6,
        "minimum_non_arxiv_items": 2,
        "maximum_continuing_items": 3,
        "maximum_items_per_topic": 3,
    },
    "social": {
        "minimum_items": 10,
        "target_items": 12,
        "maximum_items": 14,
        "minimum_new_or_material_update": 7,
        "maximum_continuing_items": 3,
        "minimum_reputable_media_items": 3,
        "minimum_primary_official_items": 3,
        "minimum_source_classes": 3,
        "maximum_items_per_organization": 2,
        "maximum_items_per_topic": 3,
    },
}


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def clean_text(value: Any, limit: int = 4000) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def merged_policy(value: Any) -> dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    merged = dict(DEFAULT_RANKING_POLICY)
    merged.update({key: val for key, val in raw.items() if key not in {"academic", "social"}})
    merged["academic"] = {**DEFAULT_RANKING_POLICY["academic"], **(raw.get("academic") or {})}
    merged["social"] = {**DEFAULT_RANKING_POLICY["social"], **(raw.get("social") or {})}
    merged["algorithm_version"] = ALGORITHM_VERSION
    merged["deterministic"] = True
    return merged


def domain_of(value: Any) -> str:
    try:
        domain = urlsplit(canonical_url(value)).netloc.lower()
    except ValueError:
        return ""
    return domain[4:] if domain.startswith("www.") else domain


def is_academic_domain(domain: str) -> bool:
    return any(domain == known or domain.endswith("." + known) for known in ACADEMIC_DOMAINS)


def parse_iso_date(value: Any) -> date | None:
    match = re.search(r"(20\d{2}-\d{2}-\d{2})", clean_text(value, 120))
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(1))
    except ValueError:
        return None


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def explicit_signal(item: dict[str, Any], name: str, fallback: float) -> float:
    signals = item.get("ranking_signals") or {}
    if isinstance(signals, dict) and name in signals:
        try:
            return clamp(float(signals[name]))
        except (TypeError, ValueError):
            return fallback
    return fallback


def source_class_for(item: dict[str, Any], kind: str) -> str:
    explicit = clean_text(item.get("source_class"), 120).lower().replace("-", "_").replace(" ", "_")
    if explicit:
        return explicit
    evidence = clean_text(item.get("evidence_level"), 240).lower()
    domain = domain_of(item.get("source_url"))
    if kind == "academic":
        return "arxiv_preprint" if domain == "arxiv.org" else "formal_academic"
    if "reputable media" in evidence or "independent media" in evidence:
        return "reputable_media"
    if any(word in evidence for word in ["government", "regulator", "public authority"]):
        return "government_or_regulator"
    if "executive" in evidence and "social" in evidence:
        return "executive_social"
    if "social" in evidence:
        return "official_company_social"
    if "official" in evidence:
        return "official_primary"
    if "media" in evidence:
        return "reputable_media"
    return "other_verified"


def organization_for(item: dict[str, Any], kind: str) -> str:
    explicit = clean_text(item.get("organization"), 160).lower()
    if explicit:
        return explicit
    if kind == "social":
        return domain_of(item.get("source_url"))
    return ""


def topic_for(item: dict[str, Any]) -> str:
    explicit = clean_text(item.get("topic"), 160).lower()
    if explicit:
        return explicit
    concepts = item.get("concepts") or []
    if isinstance(concepts, list) and concepts:
        return clean_text(concepts[0], 160).lower()
    return clean_text(item.get("category"), 160).lower()


def evidence_fraction(item: dict[str, Any], kind: str, source_class: str) -> float:
    evidence = clean_text(item.get("evidence_level"), 240).lower()
    domain = domain_of(item.get("source_url"))
    if kind == "academic":
        if domain == "arxiv.org":
            return 0.56
        if "proceedings" in evidence or domain in {"openreview.net", "openaccess.thecvf.com", "proceedings.mlr.press", "neurips.cc", "aclanthology.org"}:
            return 0.88
        return 1.0
    mapping = {
        "government_or_regulator": 1.0,
        "reputable_media": 0.92,
        "official_primary": 0.78,
        "official_company_social": 0.58,
        "executive_social": 0.52,
        "other_verified": 0.60,
    }
    return mapping.get(source_class, 0.50)


def text_signals(item: dict[str, Any]) -> tuple[str, set[str]]:
    text = " ".join(
        clean_text(item.get(field), 3000)
        for field in ("title", "facts", "judgment", "relevance", "source_excerpt", "category")
    ).lower()
    concepts = item.get("concepts") or []
    tokens = set(re.findall(r"[a-z0-9][a-z0-9+_.-]{2,}|[\u4e00-\u9fff]{2,}", text))
    if isinstance(concepts, list):
        tokens.update(clean_text(value, 120).lower() for value in concepts if clean_text(value, 120))
    return text, tokens


def keyword_fraction(text: str, words: Iterable[str], cap: int = 4) -> float:
    hits = sum(1 for word in words if word.lower() in text)
    return clamp(hits / max(1, cap))


def recency_fraction(item: dict[str, Any], today: date) -> float:
    published = parse_iso_date(item.get("published_at"))
    if not published:
        return 0.0
    age = max(0, (today - published).days)
    return clamp(1.0 - age / 14.0)


def novelty_fraction(novelty: str) -> float:
    return {"new": 1.0, "material_update": 0.85, "continuing": 0.25}.get(novelty, 0.0)


def score_item(item: dict[str, Any], kind: str, today: date, novelty: str) -> dict[str, Any]:
    source_class = source_class_for(item, kind)
    text, _ = text_signals(item)
    recency = recency_fraction(item, today)
    novelty_value = 0.65 * novelty_fraction(novelty) + 0.35 * recency
    number_specificity = clamp(len(re.findall(r"\b\d+(?:\.\d+)?%?|\[\[\d+|doi|arxiv", text)) / 4.0)
    relevance_default = keyword_fraction(
        text,
        ["quantum", "量子", "hamilton", "哈密顿", "dynamics", "动力学", "graph", "图", "error correction", "纠错", "agent", "智能体"],
        5,
    )
    evidence = evidence_fraction(item, kind, source_class)

    if kind == "academic":
        technical_default = keyword_fraction(
            text,
            ["theorem", "proof", "algorithm", "experiment", "benchmark", "simulation", "定理", "证明", "算法", "实验", "模拟", "误差"],
            5,
        )
        reproducibility_default = keyword_fraction(
            text,
            ["code", "github", "data", "dataset", "open source", "supplement", "代码", "数据", "开源", "附录", "exhaustive"],
            4,
        )
        components = {
            "evidence": 25 * evidence,
            "novelty": 15 * novelty_value,
            "technical_contribution": 20 * explicit_signal(item, "technical_contribution", technical_default),
            "specificity": 15 * explicit_signal(item, "specificity", number_specificity),
            "relevance": 15 * explicit_signal(item, "relevance", relevance_default),
            "reproducibility": 10 * explicit_signal(item, "reproducibility", reproducibility_default),
        }
    else:
        impact_default = keyword_fraction(
            text,
            ["regulation", "policy", "law", "deployment", "funding", "energy", "labor", "education", "监管", "政策", "部署", "融资", "能源", "就业", "教育"],
            4,
        )
        materiality_default = keyword_fraction(
            text,
            ["released", "launched", "announced", "approved", "signed", "invested", "发布", "上线", "宣布", "批准", "签署", "投资"],
            3,
        )
        corroboration_default = clamp(float(item.get("corroborating_source_count") or 0) / 2.0)
        components = {
            "evidence": 25 * evidence,
            "public_impact": 20 * explicit_signal(item, "public_impact", impact_default),
            "materiality": 15 * explicit_signal(item, "materiality", materiality_default),
            "novelty": 15 * novelty_value,
            "relevance": 10 * explicit_signal(item, "relevance", relevance_default),
            "corroboration": 10 * explicit_signal(item, "corroboration", corroboration_default),
            "specificity": 5 * explicit_signal(item, "specificity", number_specificity),
        }

    penalties: dict[str, float] = {}
    if any(word in text for word in ["rumor", "unconfirmed", "传闻", "未经证实"]):
        penalties["unverified_language"] = -100.0
    if kind == "social" and any(word in text for word in ["revolutionary", "game-changing", "震撼", "颠覆", "史上最强"]):
        penalties["promotional_language"] = -7.0
    base_score = clamp(sum(components.values()) + sum(penalties.values()), 0.0, 100.0)
    return {
        "algorithm_version": ALGORITHM_VERSION,
        "base_score": round(base_score, 3),
        "components": {key: round(value, 3) for key, value in components.items()},
        "penalties": {key: round(value, 3) for key, value in penalties.items()},
        "source_class": source_class,
        "organization": organization_for(item, kind),
        "topic": topic_for(item),
        "novelty": novelty,
    }


def eligibility_failures(item: dict[str, Any], kind: str) -> list[str]:
    failures: list[str] = []
    url = clean_text(item.get("source_url"), 1600)
    domain = domain_of(url)
    evidence = clean_text(item.get("evidence_level"), 240).lower()
    if not url.startswith("https://") or not domain:
        failures.append("unsafe_or_missing_https_source")
    if not clean_text(item.get("source_title"), 500):
        failures.append("missing_source_title")
    if not clean_text(item.get("evidence_fingerprint"), 240):
        failures.append("missing_evidence_fingerprint")
    if not parse_iso_date(item.get("published_at")):
        failures.append("missing_or_invalid_published_at")
    if not clean_text(item.get("facts"), 3000) or not clean_text(item.get("judgment"), 2000) or not clean_text(item.get("relevance"), 1500):
        failures.append("missing_fact_judgment_or_relevance")
    if any(word in evidence for word in ["candidate", "rumor", "unverified"]):
        failures.append("candidate_or_unverified_evidence")
    if kind == "academic" and not is_academic_domain(domain):
        failures.append("not_a_paper_level_academic_source")
    if kind == "social" and is_academic_domain(domain):
        failures.append("academic_source_in_social_pool")
    return failures


def similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    _, left_tokens = text_signals(left)
    _, right_tokens = text_signals(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def is_reputable(source_class: str) -> bool:
    return source_class == "reputable_media"


def is_primary_official(source_class: str) -> bool:
    return source_class in {"official_primary", "government_or_regulator"}


def constraint_reason(candidate: dict[str, Any], selected: list[dict[str, Any]], kind: str, policy: dict[str, Any]) -> str:
    novelty = candidate["score"]["novelty"]
    topic = candidate["score"]["topic"]
    organization = candidate["score"]["organization"]
    if kind == "academic":
        if novelty == "new" and sum(row["score"]["novelty"] == "new" for row in selected) >= int(policy["maximum_new_items"]):
            return "maximum_new_items"
        if novelty == "continuing" and sum(row["score"]["novelty"] == "continuing" for row in selected) >= int(policy["maximum_continuing_items"]):
            return "maximum_continuing_items"
    else:
        if novelty == "continuing" and sum(row["score"]["novelty"] == "continuing" for row in selected) >= int(policy["maximum_continuing_items"]):
            return "maximum_continuing_items"
        if organization and sum(row["score"]["organization"] == organization for row in selected) >= int(policy["maximum_items_per_organization"]):
            return "maximum_items_per_organization"
    if topic and sum(row["score"]["topic"] == topic for row in selected) >= int(policy["maximum_items_per_topic"]):
        return "maximum_items_per_topic"
    return ""


def need_bonus(candidate: dict[str, Any], selected: list[dict[str, Any]], kind: str, policy: dict[str, Any]) -> float:
    score = candidate["score"]
    if kind == "academic":
        bonus = 0.0
        new_count = sum(row["score"]["novelty"] == "new" for row in selected)
        formal_count = sum(row["score"]["source_class"] != "arxiv_preprint" for row in selected)
        if new_count < int(policy["minimum_new_items"]) and score["novelty"] == "new":
            bonus += 45.0
        if formal_count < int(policy["minimum_non_arxiv_items"]) and score["source_class"] != "arxiv_preprint":
            bonus += 50.0
        return bonus
    bonus = 0.0
    active_count = sum(row["score"]["novelty"] in {"new", "material_update"} for row in selected)
    reputable_count = sum(is_reputable(row["score"]["source_class"]) for row in selected)
    official_count = sum(is_primary_official(row["score"]["source_class"]) for row in selected)
    classes = {row["score"]["source_class"] for row in selected}
    if active_count < int(policy["minimum_new_or_material_update"]) and score["novelty"] in {"new", "material_update"}:
        bonus += 45.0
    if reputable_count < int(policy["minimum_reputable_media_items"]) and is_reputable(score["source_class"]):
        bonus += 35.0
    if official_count < int(policy["minimum_primary_official_items"]) and is_primary_official(score["source_class"]):
        bonus += 35.0
    if len(classes) < int(policy["minimum_source_classes"]) and score["source_class"] not in classes:
        bonus += 25.0
    return bonus


def select_candidates(candidates: list[dict[str, Any]], kind: str, policy: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = [candidate for candidate in candidates if not candidate["eligibility_failures"]]
    selected: list[dict[str, Any]] = []
    trace: list[dict[str, Any]] = []
    target = min(int(policy["target_items"]), int(policy["maximum_items"]))
    remaining = list(eligible)
    while remaining and len(selected) < target:
        ranked: list[tuple[tuple[Any, ...], dict[str, Any], float, float, float]] = []
        for candidate in remaining:
            cap_reason = constraint_reason(candidate, selected, kind, policy)
            if cap_reason:
                continue
            max_similarity = max((similarity(candidate["item"], row["item"]) for row in selected), default=0.0)
            score = candidate["score"]
            source_classes = {row["score"]["source_class"] for row in selected}
            topics = {row["score"]["topic"] for row in selected}
            diversity_bonus = (8.0 if score["source_class"] not in source_classes else 0.0) + (5.0 if score["topic"] not in topics else 0.0)
            quota_bonus = need_bonus(candidate, selected, kind, policy)
            organization_penalty = 8.0 * sum(row["score"]["organization"] == score["organization"] and bool(score["organization"]) for row in selected)
            topic_penalty = 6.0 * sum(row["score"]["topic"] == score["topic"] and bool(score["topic"]) for row in selected)
            marginal = score["base_score"] + diversity_bonus + quota_bonus - 20.0 * max_similarity - organization_penalty - topic_penalty
            tie = (
                round(marginal, 6),
                score["base_score"],
                clean_text(candidate["item"].get("published_at"), 100),
                clean_text(candidate["item"].get("evidence_fingerprint"), 240),
            )
            ranked.append((tie, candidate, marginal, diversity_bonus, max_similarity))
        if not ranked:
            break
        _, chosen, marginal, diversity_bonus, max_similarity = max(ranked, key=lambda row: row[0])
        selected.append(chosen)
        remaining.remove(chosen)
        trace.append(
            {
                "rank": len(selected),
                "story_id": clean_text(chosen["item"].get("story_id"), 240),
                "base_score": chosen["score"]["base_score"],
                "selection_score": round(marginal, 3),
                "diversity_bonus": round(diversity_bonus, 3),
                "maximum_similarity": round(max_similarity, 4),
            }
        )
    return selected, trace


def selection_metrics(selected: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    novelty = Counter(row["score"]["novelty"] for row in selected)
    classes = Counter(row["score"]["source_class"] for row in selected)
    metrics: dict[str, Any] = {
        "selected": len(selected),
        "novelty": dict(novelty),
        "source_classes": dict(classes),
        "topics": dict(Counter(row["score"]["topic"] for row in selected if row["score"]["topic"])),
        "organizations": dict(Counter(row["score"]["organization"] for row in selected if row["score"]["organization"])),
    }
    if kind == "academic":
        metrics["non_arxiv"] = sum(row["score"]["source_class"] != "arxiv_preprint" for row in selected)
    else:
        metrics["new_or_material_update"] = sum(row["score"]["novelty"] in {"new", "material_update"} for row in selected)
        metrics["reputable_media"] = sum(is_reputable(row["score"]["source_class"]) for row in selected)
        metrics["primary_official"] = sum(is_primary_official(row["score"]["source_class"]) for row in selected)
    return metrics


def rank_briefing_config(
    config: dict[str, Any],
    index_records: list[dict[str, Any]],
    today: date,
    lookback_days: int,
) -> dict[str, Any]:
    canonical = normalize_briefing_config(config, require_source_url=True)
    policy = merged_policy(config.get("ranking_policy"))
    if not policy.get("enabled", True):
        return canonical
    recent = recent_records(index_records, today, lookback_days)
    candidates: dict[str, list[dict[str, Any]]] = {"academic": [], "social": []}
    for section in canonical.get("sections", []):
        section_title = clean_text(section.get("title"), 200)
        for item in section.get("items", []):
            copied = dict(item)
            copied["section_title"] = section_title
            kind = "academic" if is_academic_domain(domain_of(copied.get("source_url"))) else "social"
            novelty, _ = classify_item(copied, recent)
            copied["novelty"] = novelty
            score = score_item(copied, kind, today, novelty)
            failures = eligibility_failures(copied, kind)
            if score["penalties"].get("unverified_language"):
                failures.append("unverified_language")
            candidates[kind].append({"item": copied, "score": score, "eligibility_failures": sorted(set(failures))})

    # Fail closed on repeated story identities or canonical URLs. Keep the
    # strongest deterministic record and retain every rejected duplicate in
    # the candidate ledger for auditability.
    for kind in ("academic", "social"):
        ordered = sorted(
            candidates[kind],
            key=lambda row: (
                row["score"]["base_score"],
                clean_text(row["item"].get("published_at"), 100),
                clean_text(row["item"].get("evidence_fingerprint"), 240),
            ),
            reverse=True,
        )
        seen_story_ids: set[str] = set()
        seen_urls: set[str] = set()
        for candidate in ordered:
            story_id = clean_text(candidate["item"].get("story_id"), 240)
            source_url = canonical_url(candidate["item"].get("source_url"))
            if story_id in seen_story_ids or source_url in seen_urls:
                candidate["eligibility_failures"] = sorted(set(candidate["eligibility_failures"] + ["duplicate_candidate"]))
            else:
                seen_story_ids.add(story_id)
                seen_urls.add(source_url)

    selected_by_kind: dict[str, list[dict[str, Any]]] = {}
    trace_by_kind: dict[str, list[dict[str, Any]]] = {}
    for kind in ("academic", "social"):
        selected_by_kind[kind], trace_by_kind[kind] = select_candidates(candidates[kind], kind, policy[kind])

    sections: list[dict[str, Any]] = []
    for kind, title in (("academic", "Academic research and venue evidence"), ("social", "社会新闻")):
        items: list[dict[str, Any]] = []
        for rank, candidate in enumerate(selected_by_kind[kind], start=1):
            item = dict(candidate["item"])
            item.pop("section_title", None)
            item["ranking"] = {
                **candidate["score"],
                "eligible": True,
                "selected": True,
                "rank": rank,
                "selection_score": trace_by_kind[kind][rank - 1]["selection_score"],
                "selection_reason": "evidence gate passed; selected by deterministic score, quota, and diversity constraints",
                "exclusion_reasons": [],
            }
            items.append(item)
        if items:
            sections.append({"title": title, "items": items})

    ledger: list[dict[str, Any]] = []
    selected_candidate_ids = {
        id(row)
        for selected_rows in selected_by_kind.values()
        for row in selected_rows
    }
    for kind in ("academic", "social"):
        for candidate in candidates[kind]:
            story_id = clean_text(candidate["item"].get("story_id"), 240)
            selected = id(candidate) in selected_candidate_ids
            reasons = list(candidate["eligibility_failures"])
            if not selected and not reasons:
                reasons.append("below_target_or_constrained")
            ledger.append(
                {
                    "story_id": story_id,
                    "kind": kind,
                    "eligible": not candidate["eligibility_failures"],
                    "selected": selected,
                    "base_score": candidate["score"]["base_score"],
                    "novelty": candidate["score"]["novelty"],
                    "source_class": candidate["score"]["source_class"],
                    "organization": candidate["score"]["organization"],
                    "topic": candidate["score"]["topic"],
                    "exclusion_reasons": reasons,
                }
            )

    ranked = dict(canonical)
    ranked["sections"] = sections
    ranked["ranking_policy"] = policy
    ranked["ranking_manifest"] = {
        "algorithm_version": ALGORITHM_VERSION,
        "generated_for_date": today.isoformat(),
        "lookback_days": lookback_days,
        "candidate_counts": {kind: len(rows) for kind, rows in candidates.items()},
        "eligible_counts": {kind: sum(not row["eligibility_failures"] for row in rows) for kind, rows in candidates.items()},
        "selected_counts": {kind: len(rows) for kind, rows in selected_by_kind.items()},
        "metrics": {kind: selection_metrics(selected_by_kind[kind], kind) for kind in ("academic", "social")},
        "selection_trace": trace_by_kind,
        "candidate_ledger": ledger,
    }
    return ranked


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--days", type=int, default=7)
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = Path(args.config).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    with config_path.open("r", encoding="utf-8-sig") as handle:
        config = json.load(handle)
    ranked = rank_briefing_config(config, load_index(Path(args.index).expanduser().resolve()), date.fromisoformat(args.date), args.days)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(ranked, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(ranked.get("ranking_manifest", {}), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
