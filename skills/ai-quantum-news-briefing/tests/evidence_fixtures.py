"""Synthetic, fully scoped HTTP evidence for offline tests; never production data."""
from datetime import date, timedelta
from academic_sources import sources_by_id


def evidenced_row(row, window="2026-10-01"):
    source = sources_by_id()[row["source_id"]]
    row["coverage_window"] = window
    row["search_url"] = source["url"].replace("{term}", "quantum")
    row["coverage_claim"] = "discovery_only"
    row.setdefault("matches", [{"title": "Synthetic paper", "published_at": window[:10] + "T12:00:00+08:00"}
                                for _ in range(row.get("candidate_count", 0))])
    for item in row["matches"]:
        item.setdefault("published_at", window[:10] + "T12:00:00+08:00")
    row["candidate_count"] = len(row["matches"])
    row.setdefault("quarantined_count", 0)
    row["evidence"] = {"query_url": row["search_url"], "final_url": row["search_url"],
                       "status_code": 200, "response_hash": "a" * 64,
                       "retrieved_at": (date.fromisoformat(window[-10:]) + timedelta(days=1)).isoformat() + "T01:00:00Z"}
    return row
