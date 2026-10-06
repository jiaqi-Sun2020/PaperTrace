"""Single owner of unchanged daily delivery defaults and policy identity."""
from __future__ import annotations
import hashlib
import json
from copy import deepcopy
from typing import Any
ALGORITHM_VERSION = "news-ranker-v1"
DEFAULT_RANKING_POLICY: dict[str, Any] = {
    "enabled": True,
    "algorithm_version": ALGORITHM_VERSION,
    "deterministic": True,
    "academic": {
        "minimum_items": 6,
        "target_items": 8,
        "maximum_items": 8,
        "minimum_new_items": 4,
        "maximum_new_items": 8,
        "minimum_non_arxiv_items": 2,
        "maximum_continuing_items": 3,
        "maximum_items_per_topic": 3,
        "ordering": "base_score_desc",
    },
    "social": {
        "minimum_items": 6,
        "target_items": 12,
        "maximum_items": 12,
        "minimum_new_or_material_update": 4,
        "maximum_continuing_items": 3,
        "minimum_reputable_media_items": 3,
        "minimum_primary_official_items": 3,
        "minimum_source_classes": 3,
        "maximum_items_per_organization": 2,
        "maximum_items_per_topic": 3,
    },
}

def policy_snapshot():
    policy=deepcopy(DEFAULT_RANKING_POLICY)
    digest=hashlib.sha256(json.dumps(policy,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")).hexdigest()
    return {"version":1,"sha256":digest,"policy":policy}


def resolve_delivery_defaults(config, *, _check_conflicts=True):
    """Preserve the formal pipeline's existing bounds, reject contradictory copies."""
    result=deepcopy(config)
    ranking=result.get("ranking_policy") or {}
    if not isinstance(ranking,dict):raise ValueError("policy_conflict: ranking_policy must be an object")
    for kind in ("academic","social"):
        configured=result.get(kind+"_delivery")
        if configured is not None and not isinstance(configured,dict):
            raise ValueError("policy_conflict: "+kind+"_delivery must be an object")
        raw=configured or {}
        rank=ranking.get(kind) or {}
        if not isinstance(rank,dict):raise ValueError("policy_conflict: "+kind+" ranking must be an object")
        defaults=DEFAULT_RANKING_POLICY[kind]
        # Historical publication defaults are authoritative when fields are omitted.
        if configured is None:
            if kind=="academic":raw={"required":True,"context_days":7}
            raw={**defaults,**raw}
        if kind=="academic" and raw.get("required") is not True:
            result[kind+"_delivery"]=raw
            continue
        value=dict(raw)
        value["minimum_items"]=max(defaults["minimum_items"],int(raw.get("minimum_items",defaults["minimum_items"])))
        value["target_items"]=max(value["minimum_items"],int(raw.get("target_items",defaults["target_items"])))
        value["maximum_items"]=max(value["target_items"],int(raw.get("maximum_items",defaults["maximum_items"])))
        if kind=="social":
            value["target_items"]=min(defaults["maximum_items"],value["target_items"])
            value["maximum_items"]=min(defaults["maximum_items"],max(value["target_items"],int(raw.get("maximum_items",defaults["maximum_items"]))))
        floors=("minimum_new_items","minimum_non_arxiv_items") if kind=="academic" else (
            "minimum_new_or_material_update","minimum_reputable_media_items","minimum_primary_official_items","minimum_source_classes")
        ceilings=("maximum_continuing_items",) if kind=="academic" else (
            "maximum_continuing_items","maximum_items_per_organization","maximum_items_per_topic")
        for key in floors:value[key]=max(defaults[key],int(raw.get(key,defaults[key])))
        for key in ceilings:value[key]=min(defaults[key],int(raw.get(key,defaults[key])))
        if kind=="academic":value["maximum_new_items"]=min(defaults["maximum_new_items"],max(value["minimum_new_items"],int(raw.get("maximum_new_items",defaults["maximum_new_items"]))))
        if _check_conflicts and rank:
            ranked=resolve_delivery_defaults({kind+"_delivery":{**rank,"required":True}},_check_conflicts=False)[kind+"_delivery"]
            for key in set(raw)&set(rank)&set(defaults):
                # A copied default ranking template is a fallback, not an
                # explicit contradictory override of a stricter delivery field.
                if rank[key] != defaults[key] and value.get(key,raw[key])!=ranked.get(key,rank[key]):
                    raise ValueError("policy_conflict: "+kind+"."+key)
        result[kind+"_delivery"]=value
    return result
