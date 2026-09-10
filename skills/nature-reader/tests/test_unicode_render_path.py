from pathlib import Path


def test_source_page_render_uses_system_temp_directory():
    source = (Path(__file__).parents[1] / "scripts" / "extract_pdf_bundle.py").read_text(encoding="utf-8")

    assert 'TemporaryDirectory(prefix="papertrace_render_")' in source
    assert 'prefix = temp_output_dir / "render"' in source
    assert 'shutil.move(str(source), str(target))' in source
    assert 'prefix = output_dir / "render"' not in source
