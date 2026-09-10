import importlib.util
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "reader_wiki_compile.py"
sys.path.insert(0, str(MODULE_PATH.parent))
SPEC = importlib.util.spec_from_file_location("reader_wiki_compile", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_algorithm_citation_is_not_an_algorithm_card():
    segment = "**Original:** Algorithm 5 supplies a verification target for this open problem."
    assert MODULE.ALGORITHM_RE.search(segment)
    assert not MODULE.ALGORITHM_LINE_RE.search(segment)


def test_numbered_pseudocode_is_an_algorithm_card():
    segment = "Algorithm 5 Port and verify\n1: transpile U\n2: compare the circuit"
    assert MODULE.ALGORITHM_RE.search(segment)
    assert MODULE.ALGORITHM_LINE_RE.search(segment)
