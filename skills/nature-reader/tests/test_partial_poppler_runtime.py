"""Minimal Poppler bundles may provide only pdftoppm, with pypdf for evidence."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import extract_pdf_bundle as extract
import preflight_reader_bundle as preflight


def test_missing_pdftotext_uses_existing_fidelity_checked_fallback(monkeypatch, tmp_path):
    monkeypatch.setattr(extract.shutil, 'which', lambda _: None)
    page = SimpleNamespace(extract_text=lambda: 'A source paragraph with a ﬁ ligature.')
    monkeypatch.setattr(extract, 'PdfReader', lambda _: SimpleNamespace(pages=[page]))
    assert extract.extract_reading_order_pages(tmp_path / 'paper.pdf', 1) == ['A source paragraph with a fi ligature.']


def test_page_render_can_use_pdftoppm(monkeypatch, tmp_path):
    monkeypatch.setattr(extract.shutil, 'which', lambda name: 'pdftoppm' if name == 'pdftoppm' else None)
    commands = []
    def render(args):
        commands.append(args)
        Path(args[-1] + '-1.png').write_bytes(b'rendered-source-evidence')
    monkeypatch.setattr(extract, 'run', render)
    result = extract.source_page_paths(tmp_path, tmp_path / 'paper.pdf', 1)
    assert commands[0][:4] == ['pdftoppm', '-png', '-r', '144']
    assert result[0]['source_page_image'] == 'assets/source_pages/page-01.png'
    assert result[0]['sha256'] == extract.sha256_file(tmp_path / result[0]['source_page_image'])


def test_embedded_images_can_use_pypdf(monkeypatch, tmp_path):
    monkeypatch.setattr(extract.shutil, 'which', lambda _: None)
    page = SimpleNamespace(images=[SimpleNamespace(name='Im1.png', data=b'original-image-bytes')])
    monkeypatch.setattr(extract, 'PdfReader', lambda _: SimpleNamespace(pages=[page]))
    result = extract.extract_embedded_images(tmp_path, tmp_path / 'paper.pdf')
    assert (tmp_path / result[0]['path']).read_bytes() == b'original-image-bytes'
    assert result[0]['sha256'] == extract.sha256_file(tmp_path / result[0]['path'])


def test_supplementary_caption_tokens_remain_distinct():
    rows = [{'caption_original': 'Figure S1: appendix'},
            {'caption_original': 'Figure 1: main'},
            {'caption_original': 'Table S3: resources'}]
    assert preflight.registered_caption_tokens(rows) == {'figure:s1', 'figure:1', 'table:s3'}


def test_external_object_references_are_not_local_caption_candidates(tmp_path):
    pages = tmp_path / 'raw' / 'pages'
    pages.mkdir(parents=True)
    (pages / 'page-01.txt').write_text(
        'Table 2 of ref. 48 supplies parameters.\nFigure S1: Local appendix figure.\n'
        'Table I of ref. 60 supplies a baseline.\nTable S1: Local appendix table.\n', encoding='utf-8')
    candidates = preflight.caption_candidates(tmp_path)
    assert len(candidates['figures']) == len(candidates['tables']) == 1
    assert candidates['tables'][0]['caption_candidate'].startswith('Table S1:')
