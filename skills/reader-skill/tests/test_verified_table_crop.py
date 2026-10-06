import hashlib
import json
from pathlib import Path
import sys

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from reader_wiki_compile import figure_table_ledger


def fixture(tmp_path):
    (tmp_path / 'assets').mkdir()
    (tmp_path / 'reader_wiki').mkdir()
    page = Image.new('RGB', (100, 100), 'white')
    for x in range(20, 60):
        for y in range(20, 60):
            page.putpixel((x, y), (x, y, 100))
    page.save(tmp_path / 'assets/page.png')
    page.crop((20, 20, 60, 60)).save(tmp_path / 'assets/table.png')
    digest = lambda rel: hashlib.sha256((tmp_path / rel).read_bytes()).hexdigest()
    metadata = {'id':'T001', 'representation':'tight_crop', 'asset_path':'assets/table.png',
                'asset_sha256':digest('assets/table.png'), 'bbox':[20,20,60,60],
                'bbox_units':'source-page-pixels','source_page_image':'assets/page.png',
                'source_page_image_sha256':digest('assets/page.png')}
    source = {'tables':[{'id':'T001','page':1,'source_page_image':'assets/page.png'}]}
    markdown = '<a id="T001"></a>\n### Table\n![T001](assets/table.png)\n**Original caption:** Table I\n**中文表注:** 表一\n'
    return metadata, source, markdown


@pytest.mark.parametrize('mutation', ['valid','tampered_pixels','wrong_bbox','unbound_image','full_page'])
def test_crop_requires_exact_source_pixels(tmp_path, mutation):
    metadata, source, markdown = fixture(tmp_path)
    if mutation == 'tampered_pixels':
        Image.new('RGB', (40,40), 'red').save(tmp_path / 'assets/table.png')
        metadata['asset_sha256'] = hashlib.sha256((tmp_path / 'assets/table.png').read_bytes()).hexdigest()
    elif mutation == 'wrong_bbox':
        metadata['bbox'] = [21,21,61,61]
    elif mutation == 'unbound_image':
        markdown = markdown.replace('assets/table.png','assets/other.png')
    elif mutation == 'full_page':
        metadata['bbox'] = [0,0,100,100]
        Image.open(tmp_path / 'assets/page.png').save(tmp_path / 'assets/table.png')
        metadata['asset_sha256'] = hashlib.sha256((tmp_path / 'assets/table.png').read_bytes()).hexdigest()
    (tmp_path / 'reader_wiki/object_inventory.json').write_text(json.dumps({'objects':[metadata]}),encoding='utf8')
    rows, errors = figure_table_ledger(markdown, source, tmp_path)
    assert rows[0]['has_verified_tight_crop'] == (mutation == 'valid')
    assert bool(errors) == (mutation != 'valid')


def test_semantic_table_stays_supported(tmp_path):
    _, source, _ = fixture(tmp_path)
    markdown = '<a id="T001"></a>\n|Model|Score|\n|---|---|\n|A|1|\n**Original caption:** Table I\n**中文表注:** 表一\n'
    rows, errors = figure_table_ledger(markdown, source, tmp_path)
    assert not errors and rows[0]['has_semantic_table']
