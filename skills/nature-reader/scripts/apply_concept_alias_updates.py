#!/usr/bin/env python3
"""Apply reviewed concept-name and Chinese-alias updates mechanically."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("concept_candidates", type=Path)
    parser.add_argument("updates", type=Path)
    args = parser.parse_args()
    data = json.loads(args.concept_candidates.read_text(encoding="utf-8"))
    updates = json.loads(args.updates.read_text(encoding="utf-8"))
    changed = 0
    for concept in data.get("concepts", []):
        name = concept.get("canonical_name")
        update = updates.get(name)
        if not update:
            continue
        if update.get("canonical_name"):
            concept["canonical_name"] = update["canonical_name"]
        if "aliases_en" in update:
            concept["aliases_en"] = update["aliases_en"]
        aliases = list(concept.get("aliases_zh") or [])
        for alias in update.get("add_aliases_zh", []):
            if alias not in aliases:
                aliases.append(alias)
        concept["aliases_zh"] = aliases
        changed += 1
    args.concept_candidates.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"updated_concepts": changed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
