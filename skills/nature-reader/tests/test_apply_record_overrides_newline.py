import importlib.util
import json
from pathlib import Path
import re


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "apply_record_overrides.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("apply_record_overrides", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_literal_newline_normalization_preserves_tex_nu():
    source = SCRIPT.read_text(encoding="utf-8")
    assert '.replace(r"\\n\\n", "\\n\\n")' in source

    text = r"first\n\nsecond $\nu(s)$"
    normalized = text.replace(r"\n\n", "\n\n")
    assert normalized == "first\n\nsecond $\\nu(s)$"


def test_physical_newline_before_prose_is_not_reparsed_as_tex_command():
    module = _load_module()
    raw = '{"block:S001":{"original":"line one\nline two $\\nu(s)$"}}'
    protected = module.escape_newlines_inside_json_strings(raw)
    escaped = re.sub(
        r'(?<!\\)\\(?!["\\/]|[bfnrt](?![A-Za-z])|u[0-9a-fA-F]{4})',
        r'\\\\',
        protected,
    ).replace(module.PHYSICAL_NEWLINE_SENTINEL, r"\n")
    parsed = json.loads(escaped)
    assert parsed["block:S001"]["original"] == "line one\nline two $\\nu(s)$"


def test_explicit_json_paragraph_escape_before_prose_is_protected():
    module = _load_module()
    raw = r'{"block:S001":{"original":"line one\n\nNext $\nu(s)$"}}'
    protected = module.escape_newlines_inside_json_strings(raw)
    protected = protected.replace(r"\n\n", module.PHYSICAL_NEWLINE_SENTINEL * 2)
    escaped = re.sub(
        r'(?<!\\)\\(?!["\\/]|[bfnrt](?![A-Za-z])|u[0-9a-fA-F]{4})',
        r'\\\\',
        protected,
    ).replace(module.PHYSICAL_NEWLINE_SENTINEL, r"\n")
    parsed = json.loads(escaped)
    assert parsed["block:S001"]["original"] == "line one\n\nNext $\\nu(s)$"
