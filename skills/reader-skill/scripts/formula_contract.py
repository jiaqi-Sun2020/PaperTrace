#!/usr/bin/env python3
"""Shared semantic checks for authored reader formulas.

The immutable PDF extraction may remain noisy in ``source_map.json``.  Formal
reader prose may not: display formulas are explicit, atomic components and the
surrounding prose must not carry a second plaintext copy of the same equation.
"""

from __future__ import annotations

import re


DISPLAY_MATH_RE = re.compile(r"(\\\[[\s\S]*?\\\]|\$\$[\s\S]*?\$\$)")
ALL_MATH_RE = re.compile(
    r"(\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$\$[\s\S]*?\$\$|(?<!\\)\$(?!\s)(?:\\.|[^$]){1,1600}?(?<!\\)\$)"
)
INLINE_MATH_RE = re.compile(
    r"(\\\([\s\S]*?\\\)|(?<!\\)\$(?!\s)(?:\\.|[^$]){1,1600}?(?<!\\)\$)"
)
COMPOUND_DISPLAY_RE = re.compile(r"\\q(?:uad|quad)|\\begin\{(?:align\*?|aligned|gather\*?|gathered)\}")
RELATION_RE = re.compile(r"(?:=|\\propto|\\leq?|\\geq?|\\approx|\\sim|←|→|∝|≤|≥|≈)")
RAW_EQUATION_RE = re.compile(
    r"(?<![\w\\])(?P<lhs>[A-Za-zΑ-ωα-ω][A-Za-z0-9Α-ωα-ω_{}^'(),\[\]|*+-]{0,48})"
    r"\s*(?P<relation>=|←|→|∝|≤|≥|≈)\s*"
    r"(?P<rhs>[^\s,.;:，。；：]{2,120})"
)
RAW_TEX_COMMAND_RE = re.compile(r"\\(?:[A-Za-z]{2,}|[A-Za-z](?=[_^{]))")
RAW_SCRIPT_SYNTAX_RE = re.compile(
    r"(?<![\w\\])(?:[A-Za-z][A-Za-z0-9]*)(?:_\{[A-Za-z0-9,+\-]+\}|\^\{?[-+A-Za-z0-9]+\}?)+"
)
PDF_MATH_FRAGMENT_PATTERNS = (
    (
        "detached accent/hat glyph",
        re.compile(r"(?m)(?<![A-Za-z])[bB]\s*\n\s*(?:K|A|M|B|C)(?:\b|[_A-Za-z])"),
    ),
    (
        "split Greek subscript/superscript",
        re.compile(r"[\u0391-\u03a9\u03b1-\u03c9]\d*\s*\n\s*[A-Za-z](?:[A-Za-z0-9]|\))"),
    ),
    (
        "split indexed mathematical symbol",
        re.compile(r"(?m)(?:^|\n)\s*(?:K|A|B|M|L|s|c|g|e|u|x|y|n|m)\s*\n\s*(?:ij|ji|ii|jj|warm|true|fu|uu|tr|iter|step)\b", re.I),
    ),
)

# These glyphs are valid *inside* a LaTeX node, but cannot be safely rendered
# as ordinary prose.  They are a reliable signal that PDF-layout mathematics
# escaped reconstruction.  Keep the set deliberately mathematical rather than
# treating all Greek letters as errors: names such as “Neyman” remain prose.
RAW_UNICODE_MATH_RE = re.compile(r"[∂∝∑Σ]")
SOURCE_PDF_MATH_FRAGMENT_PATTERNS = (
    ("split indexed identifier", re.compile(r"(?m)\b[A-Za-z][A-Za-z0-9]{0,24}\s*\n\s*(?:ij|ji|ii|jj)\b")),
    ("split bracketed matrix entry", re.compile(r"(?m)\[[A-Za-z]\s*[−-]\s*\d+\s*\n\s*\]\s*(?:ij|ji|ii|jj)\b")),
    ("split displayed relation", re.compile(r"(?m)\b[A-Za-z][A-Za-z0-9]{0,24}\s*\n\s*=\s*\n\s*(?:[PΣ∑]|[A-Za-z0-9])")),
)

SOURCE_MATH_INVENTORY_CONTRACT = "source-math-inventory-v1"


def display_components(text: str) -> list[str]:
    return [match.group(0) for match in DISPLAY_MATH_RE.finditer(text or "")]


def math_body(component: str) -> str:
    value = component.strip()
    if value.startswith("$$") and value.endswith("$$"):
        return value[2:-2].strip()
    if value.startswith(r"\[") and value.endswith(r"\]"):
        return value[2:-2].strip()
    return value


def compact_math(value: str) -> str:
    value = re.sub(r"\\(?:left|right|mathrm|operatorname|text|mathbf|mathcal|widehat|hat)", "", value)
    value = re.sub(r"[\\{}_^\s]", "", value)
    return value.casefold()


def math_components(text: str) -> list[str]:
    """Return every explicit inline or display math component in order."""

    return [match.group(0) for match in ALL_MATH_RE.finditer(text or "")]


def prose_without_math(text: str) -> str:
    """Remove explicit math before looking for leaked TeX in prose."""

    return ALL_MATH_RE.sub(" ", text or "")


def raw_math_leak_issues(text: str, *, field: str) -> list[str]:
    """Reject TeX and PDF-layout math fragments outside explicit delimiters.

    MathJax never guesses where mathematics starts.  A formal reader must make
    that boundary explicit in every prose block, including ordinary paragraph
    records that happen to contain inline mathematics.
    """

    prose = prose_without_math(text)
    issues: list[str] = []
    command = RAW_TEX_COMMAND_RE.search(prose)
    if command:
        preview = re.sub(r"\s+", " ", prose[max(0, command.start() - 24): command.end() + 48]).strip()
        issues.append(f"{field}: raw TeX command outside math delimiters: {preview[:100]}")
    script = RAW_SCRIPT_SYNTAX_RE.search(prose)
    if script:
        issues.append(f"{field}: subscript/superscript syntax outside math delimiters: {script.group(0)[:80]}")
    for label, pattern in PDF_MATH_FRAGMENT_PATTERNS:
        fragment = pattern.search(prose)
        if fragment:
            preview = re.sub(r"\s+", " ", fragment.group(0)).strip()
            issues.append(f"{field}: raw PDF math fragment ({label}): {preview[:80]}")
    return issues


def source_math_evidence_issues(text: str, *, field: str) -> list[str]:
    """Find formula-layout residue in immutable source evidence only.

    This stricter detector drives the bootstrap decision to require an
    inventory.  It intentionally does not reinterpret legacy prose records at
    render time, where harmless experimental inequalities may be readable
    ordinary text.  Once an inventory is required, every reconstructed
    component is verified exactly by ``source_math_inventory_issues``.
    """

    issues = raw_math_leak_issues(text, field=field)
    for label, pattern in SOURCE_PDF_MATH_FRAGMENT_PATTERNS:
        fragment = pattern.search(text or "")
        if fragment:
            preview = re.sub(r"\s+", " ", fragment.group(0)).strip()
            issues.append(f"{field}: raw PDF math fragment ({label}): {preview[:80]}")
    glyph = RAW_UNICODE_MATH_RE.search(text or "")
    if glyph:
        preview = re.sub(r"\s+", " ", (text or "")[max(0, glyph.start() - 24): glyph.end() + 48]).strip()
        issues.append(f"{field}: Unicode mathematical glyph outside a reconstructed component: {preview[:100]}")
    return issues


def canonical_math_signature(component: str) -> str:
    value = component.strip()
    if value.startswith("$$") and value.endswith("$$"):
        value = value[2:-2]
    elif value.startswith((r"\(", r"\[")) and value.endswith((r"\)", r"\]")):
        value = value[2:-2]
    elif value.startswith("$") and value.endswith("$"):
        value = value[1:-1]
    replacements = {
        r"\lvert": "|",
        r"\rvert": "|",
        r"\le ": r"\leq ",
        r"\ge ": r"\geq ",
        "α": r"\alpha",
        "σ": r"\sigma",
        "ρ": r"\rho",
        "λ": r"\lambda",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    value = re.sub(r"\\(?:left|right)", "", value)
    value = re.sub(r"\s+", "", value)
    # Sentence punctuation belongs to the surrounding prose, even when a
    # source author placed it just inside an inline delimiter.  It cannot
    # change the mathematical component and must not create a false bilingual
    # mismatch.
    return value.rstrip(".,;:。；，：")


def bilingual_math_issues(original: str, zh: str, *, block_id: str = "block") -> list[str]:
    """Require the same explicit mathematical components in both languages."""

    original_signatures = [canonical_math_signature(item) for item in math_components(original)]
    zh_signatures = [canonical_math_signature(item) for item in math_components(zh)]
    if original_signatures == zh_signatures:
        return []
    if len(original_signatures) != len(zh_signatures):
        return [
            f"{block_id}: bilingual math count mismatch: "
            f"Original={len(original_signatures)}, Chinese={len(zh_signatures)}"
        ]
    for index, (left, right) in enumerate(zip(original_signatures, zh_signatures), start=1):
        if left != right:
            return [f"{block_id}: bilingual math component {index} differs between Original and Chinese"]
    return []


def source_math_inventory_issues(
    metadata: object,
    original: str,
    zh: str,
    *,
    block_id: str,
) -> list[str]:
    """Validate an authored, source-bound formula component inventory.

    A source formula block is not complete merely because one TeX expression
    exists somewhere in it.  The inventory is the explicit human-authored
    assertion of every reconstructed source component, in source order.  It
    lets the completion gate verify three independently useful facts: no raw
    PDF math remains in either language, Original covers every declared source
    component, and Chinese preserves exactly the same components.
    """

    if not isinstance(metadata, dict):
        return [f"{block_id}: object metadata is not an object"]
    inventory = metadata.get("source_math_inventory")
    if not isinstance(inventory, dict):
        return [f"{block_id}: equation source block requires source_math_inventory"]
    if inventory.get("contract") != SOURCE_MATH_INVENTORY_CONTRACT:
        return [f"{block_id}: source_math_inventory must declare {SOURCE_MATH_INVENTORY_CONTRACT}"]
    if inventory.get("status") != "complete":
        return [f"{block_id}: source_math_inventory status must be complete"]
    components = inventory.get("components")
    if not isinstance(components, list) or not components:
        return [f"{block_id}: source_math_inventory requires a non-empty components list"]

    errors: list[str] = []
    expected: list[str] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(components, start=1):
        if not isinstance(item, dict):
            errors.append(f"{block_id}: source_math_inventory component {index} must be an object")
            continue
        identifier = str(item.get("id") or "").strip()
        signature = str(item.get("signature") or "").strip()
        presentation = str(item.get("presentation") or "").strip()
        if not identifier or identifier in seen_ids:
            errors.append(f"{block_id}: source_math_inventory component {index} needs a unique id")
        seen_ids.add(identifier)
        if not signature:
            errors.append(f"{block_id}: source_math_inventory component {index} needs a signature")
            continue
        if presentation not in {"inline", "display"}:
            errors.append(f"{block_id}: source_math_inventory component {index} has invalid presentation")
        expected.append(canonical_math_signature(signature))
    if errors:
        return errors

    original_actual = [canonical_math_signature(value) for value in math_components(original)]
    zh_actual = [canonical_math_signature(value) for value in math_components(zh)]
    for language, actual in (("Original", original_actual), ("Chinese", zh_actual)):
        if actual != expected:
            if len(actual) != len(expected):
                errors.append(
                    f"{block_id}: {language} math inventory count mismatch: expected={len(expected)}, actual={len(actual)}"
                )
            else:
                for index, (wanted, found) in enumerate(zip(expected, actual), start=1):
                    if wanted != found:
                        errors.append(f"{block_id}: {language} math inventory component {index} differs from source inventory")
                        break
    errors.extend(bilingual_math_issues(original, zh, block_id=block_id))
    return errors


def display_lhs_signatures(text: str) -> set[str]:
    signatures: set[str] = set()
    for component in display_components(text):
        body = math_body(component)
        relation = RELATION_RE.search(body)
        if not relation:
            continue
        lhs = compact_math(body[: relation.start()])
        if len(lhs) >= 1:
            signatures.add(lhs)
    return signatures


def plaintext_duplicate_issues(text: str, *, field: str) -> list[str]:
    """Conservatively catch a plaintext equation duplicated by a display.

    Inline symbols remain legal.  A row is rejected only when plaintext has an
    explicit relation and its normalized left-hand side matches a display
    component in the same language field.
    """

    signatures = display_lhs_signatures(text)
    if not signatures:
        return []
    prose = ALL_MATH_RE.sub(" ", text)
    issues: list[str] = []
    for match in RAW_EQUATION_RE.finditer(prose):
        lhs = compact_math(match.group("lhs"))
        if lhs in signatures:
            preview = re.sub(r"\s+", " ", match.group(0)).strip()
            issues.append(f"{field}: plaintext duplicates display formula: {preview[:90]}")
    return issues


def atomic_formula_issues(text: str, *, field: str) -> list[str]:
    issues: list[str] = []
    if r"\n" in (text or ""):
        issues.append(f"{field}: literal \\n escape remains; use real Markdown paragraph breaks")
    for index, component in enumerate(display_components(text), start=1):
        body = math_body(component)
        if COMPOUND_DISPLAY_RE.search(body):
            issues.append(
                f"{field}: display formula {index} contains multiple logical formulas; "
                "render one formula per display (use split/multline only to wrap one formula)"
            )
    issues.extend(raw_math_leak_issues(text, field=field))
    issues.extend(plaintext_duplicate_issues(text, field=field))
    return issues
