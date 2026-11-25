"""Validate authored, paper-specific reading cues; never derive claims from citations."""


def validate_scan(summary, history, anchors, *, required):
    errors = []

    def has_text(row, key):
        return isinstance(row.get(key), str) and bool(row[key].strip())

    def citations(row, where, *, allow_empty=False):
        refs = row.get("source_anchors")
        if (not isinstance(refs, list) or (not refs and not allow_empty)
                or any(not isinstance(a, str) or not a or a not in anchors for a in refs)):
            errors.append(where + ": missing or unknown source_anchors")

    if required or "result_brief" in summary:
        brief = summary.get("result_brief")
        if not isinstance(brief, dict) or not has_text(brief, "headline"):
            errors.append("result_brief requires a concise, paper-specific headline")
        rows = brief.get("items") if isinstance(brief, dict) else None
        if not isinstance(rows, list) or not rows:
            errors.append("result_brief.items requires the paper's principal findings")
        else:
            for i, row in enumerate(rows, 1):
                where = f"result_brief.items[{i}]"
                if not isinstance(row, dict) or not all(has_text(row, k) for k in ("subject", "finding", "scope")):
                    errors.append(where + ": supply subject, finding and scope")
                    continue
                if row.get("kind") == "comparison":
                    if not all(has_text(row, k) for k in ("metric", "baseline")):
                        errors.append(where + ": a comparison needs its metric and named baseline")
                elif row.get("kind") != "standalone" or row.get("baseline") is not None:
                    errors.append(where + ": use comparison or standalone without a baseline")
                if row.get("metric") is not None and not has_text(row, "metric"):
                    errors.append(where + ": metric must be nonempty text when supplied")
                citations(row, where)

    for node in history.get("nodes", []):
        if not required and "reading_role" not in node:
            continue
        role = node.get("reading_role")
        where = f"history node {node.get('id')} reading_role"
        if not isinstance(role, dict) or not all(has_text(role, k) for k in ("label", "topic", "explanation")):
            errors.append(where + ": supply the actual role label, topic and explanation")
            continue
        # A successor's actual use may only be documented in its own paper.
        # Point to a specific, separately evidence-validated edge, not an arbitrary URL.
        edge_ref = role.get("evidence_relation")
        match = isinstance(edge_ref, list) and len(edge_ref) == 3 and node.get("id") in edge_ref[:2] and any(
            [edge.get("from"), edge.get("to"), edge.get("type")] == edge_ref
            for edge in history.get("relations", []))
        if edge_ref is not None and not match:
            errors.append(where + ": unknown or unrelated evidence_relation")
        citations(role, where, allow_empty=match or (role["label"] == "关系待核实" and not node.get("current")))
    return errors
