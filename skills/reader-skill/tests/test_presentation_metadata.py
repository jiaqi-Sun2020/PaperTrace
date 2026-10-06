import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from markdown_reader_to_html import collect_meta


def test_source_bound_presentation_does_not_mutate_source(tmp_path):
    source = {'paper':{'title':'filename','source_pdf_sha256':'hash'}, 'blocks':[{'id':'S001','original_text':'Actual Title\nA Author; B Author'}]}
    source_path = tmp_path / 'source_map.json'
    source_path.write_text(json.dumps(source),encoding='utf8')
    before = source_path.read_bytes()
    assert collect_meta(tmp_path)['title'] == 'filename'
    (tmp_path / 'reader_wiki').mkdir()
    reviewed = {'source_anchor':'S001','source_pdf_sha256':'hash','title':'Actual Title','authors':'A Author; B Author'}
    presentation = tmp_path / 'reader_wiki/presentation_metadata.json'
    presentation.write_text(json.dumps(reviewed),encoding='utf8')
    assert collect_meta(tmp_path)['title'] == 'Actual Title'
    assert collect_meta(tmp_path)['authors'] == 'A Author; B Author'
    assert source_path.read_bytes() == before
    reviewed['title'] = 'Invented Title'
    presentation.write_text(json.dumps(reviewed),encoding='utf8')
    with pytest.raises(ValueError,match='verbatim source-bound'):
        collect_meta(tmp_path)
    reviewed['title'] = 'Actual Title'
    reviewed['source_pdf_sha256'] = 'other'
    presentation.write_text(json.dumps(reviewed),encoding='utf8')
    with pytest.raises(ValueError,match='different source PDF'):
        collect_meta(tmp_path)
