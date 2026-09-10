#!/usr/bin/env python3
"""Algorithm discovery must register definitions, not prose references."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "skills" / "nature-reader" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from extract_pdf_bundle import classify_block, split_page_blocks  # noqa: E402


def main() -> int:
    raw = """Algorithm 2 is discussed below in ordinary prose.

Algorithm 2 Reflecting streaming circuit
Require: a register
1: prepare the register
2: apply the shift

Algorithm 3 assembles one substep and Figure 5 shows the circuit.

Algorithm 3 Single-axis sweep
1: rotate
2: collide
3: stream
"""
    algorithms = [block for block in split_page_blocks(raw) if classify_block(block) == "algorithm"]
    if len(algorithms) != 2:
        raise AssertionError(f"expected two algorithm definitions, found {len(algorithms)}: {algorithms!r}")
    if not algorithms[0].startswith("Algorithm 2 Reflecting"):
        raise AssertionError("Algorithm 2 definition boundary was not preserved")
    if not algorithms[1].startswith("Algorithm 3 Single-axis"):
        raise AssertionError("Algorithm 3 definition boundary was not preserved")
    for prose in (
        "Algorithm 2 is discussed below in ordinary prose.",
        "Algorithm 3 assembles one substep and Figure 5 shows the circuit.",
    ):
        if classify_block(prose) == "algorithm":
            raise AssertionError(f"prose reference was registered as an algorithm: {prose}")
    print("algorithm discovery tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
