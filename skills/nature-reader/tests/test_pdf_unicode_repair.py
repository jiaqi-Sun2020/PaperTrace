import importlib.util
from pathlib import Path
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "extract_pdf_bundle.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("extract_pdf_bundle", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_repairs_missing_tilde_before_math_letter():
    assert MODULE.repair_math_accent_replacements("\ufffd𝐻 and \ufffd𝑊") == "~𝐻 and ~𝑊"


def test_rejects_replacement_character_in_prose():
    with pytest.raises(RuntimeError, match="unrepaired Unicode replacement"):
        MODULE.repair_math_accent_replacements("mem\ufffdry")
