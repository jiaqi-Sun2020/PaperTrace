"""Worked-example formula transport: TeX by default, or explicit plain text.

TeX formula fields are display-math fragments without comments. Literal percent
signs must be escaped by an odd backslash run. No automatic rewrite is performed:
changing author content requires a new revision and new review.
"""


def formula_format(step):
    value = step.get("formula_format", "tex")
    if not isinstance(value, str) or value not in {"tex", "text"}:
        raise ValueError("formula_format_requires_tex_or_text")
    return value


def validate_formula(step):
    kind = formula_format(step)
    value = step.get("formula", "")
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError("formula_requires_string")
    if kind == "tex":
        backslashes = 0
        for char in value:
            if char == "%" and backslashes % 2 == 0:
                raise ValueError("tex_formula_unescaped_percent: use \\% for a literal percentage, or formula_format=text")
            backslashes = backslashes + 1 if char == "\\" else 0
    return kind


def markdown_formula(step):
    """Project only an explicitly plain-text formula's literal backslashes."""
    kind = validate_formula(step)
    value = step.get("formula") or ""
    return value.replace("\\", "\\\\") if kind == "text" else value
