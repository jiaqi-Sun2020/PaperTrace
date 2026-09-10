import importlib.util
from pathlib import Path
import sys


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "extract_pdf_bundle.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("extract_pdf_bundle_caption", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_discovers_caption_when_pdf_joins_number_and_title():
    found = MODULE.discover_caption_lines("Figure 2Overview of the architecture.\nBody text")
    assert found == ["Figure 2Overview of the architecture."]


def test_discovers_caption_with_space_before_title():
    found = MODULE.discover_caption_lines("Figure 6 Roadmap for memory models.\nBody text")
    assert found == ["Figure 6 Roadmap for memory models."]


def test_discovers_table_with_joined_number_and_title():
    found = MODULE.discover_caption_lines("Table 14End-to-end latency results.\nBody text")
    assert found == ["Table 14End-to-end latency results."]


def test_does_not_treat_prose_reference_as_caption():
    assert MODULE.discover_caption_lines("Figure 2 shows the architecture.") == []


def test_does_not_treat_joined_prose_reference_as_caption():
    assert MODULE.discover_caption_lines("Figure 8further shows the latency breakdown.") == []
