"""Source-bound authored diagrams inside notes; no inference or generation."""
import json
import re

FENCE = re.compile(r"(?m)^```reader-logic[ \t]*\r?\n([\s\S]*?)^```[ \t]*(?:\r?\n|$)")
EDGE_TYPES = {"sequence", "data_flow", "supports", "contrast"}


def validate_logic_diagram(d, anchors=None):
    if not isinstance(d, dict) or type(d.get("version")) is not int or d.get("version") != 1:
        return ["reader-logic requires version 1"]
    errors = []
    if d.get("kind") not in {"flow", "argument", "comparison", "role"}:
        errors.append("unsupported reader-logic kind")
    if not isinstance(d.get("title"), str) or not d["title"].strip():
        errors.append("reader-logic lacks a descriptive title")
    nodes = d.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        return errors + ["reader-logic lacks nodes"]
    ids = []
    for n in nodes:
        if not isinstance(n, dict):
            errors.append("reader-logic node must be an object")
            continue
        nid = n.get("id")
        if not isinstance(nid, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", nid):
            errors.append("reader-logic node ID is unsafe")
        ids.append(str(nid))
        if not isinstance(n.get("label"), str) or not n["label"].strip():
            errors.append("reader-logic node lacks label")
    if len(ids) != len(set(ids)):
        errors.append("reader-logic node IDs must be unique")
    edges = d.get("edges")
    if not isinstance(edges, list):
        return errors + ["reader-logic edges must be a list"]
    linked = set()
    for e in edges:
        if not isinstance(e, dict):
            errors.append("reader-logic edge must be an object")
            continue
        if e.get("from") not in ids or e.get("to") not in ids or e.get("from") == e.get("to"):
            errors.append("reader-logic edge has invalid endpoints")
        linked.update([str(e.get("from")), str(e.get("to"))])
        if e.get("type") not in EDGE_TYPES or e.get("basis") not in {"source", "derivation", "teaching"}:
            errors.append("reader-logic edge requires relation type and evidence identity")
        if not isinstance(e.get("label"), str) or not e["label"].strip():
            errors.append("reader-logic edge lacks actual relationship")
    if len(nodes) > 1 and set(ids) != linked:
        errors.append("reader-logic has disconnected/unexplained nodes")
    if d.get("kind") == "role" and (len(nodes) != 1 or edges):
        errors.append("role card must not fabricate a chain")
    if d.get("kind") == "comparison" and any(e.get("type") != "contrast" for e in edges if isinstance(e, dict)):
        errors.append("comparison edges must be contrast")
    conditions = d.get("conditions")
    if not isinstance(conditions, list) or any(not isinstance(v, str) or not v.strip() for v in conditions):
        errors.append("reader-logic conditions must be explicit text entries")
    refs = d.get("source_anchors")
    if not isinstance(refs, list) or not refs or any(not isinstance(a, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", a) for a in refs):
        errors.append("reader-logic needs safe source anchors")
    elif anchors is not None and any(a not in anchors for a in refs):
        errors.append("reader-logic cites unknown source anchor")
    return errors


def split_logic_notes(text):
    text = str(text or "")
    parts, offset = [], 0
    for match in FENCE.finditer(text):
        parts.append(("prose", text[offset:match.start()]))
        try:
            diagram = json.loads(match.group(1))
        except ValueError as exc:
            raise ValueError("reader-logic contains invalid JSON") from exc
        errors = validate_logic_diagram(diagram)
        if errors:
            raise ValueError("; ".join(errors))
        parts.append(("diagram", diagram))
        offset = match.end()
    parts.append(("prose", text[offset:]))
    if any(re.search(r"(?m)^```reader-logic\b", v) for k, v in parts if k == "prose"):
        raise ValueError("unterminated/malformed reader-logic fence")
    return parts


def diagrams_in_notes(text):
    return [v for k, v in split_logic_notes(text) if k == "diagram"]


def notes_prose(text):
    return "\n\n".join(v.strip() for k, v in split_logic_notes(text) if k == "prose" and v.strip())
