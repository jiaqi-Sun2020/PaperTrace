"""Supplementary evidence in notes must stay within the reading column."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from markdown_reader_to_html import build_html


def test_note_images_are_responsive(tmp_path):
    html = build_html('Evidence', '<article class="reader-notes"><img src="evidence.png"></article>', [], {}, tmp_path)
    rule = re.search(r'\.reader-notes img\s*\{([^}]+)\}', html)
    assert rule is not None
    assert 'max-width: 100%' in rule.group(1)
    assert 'height: auto' in rule.group(1)
    assert 'object-fit: contain' in rule.group(1)
