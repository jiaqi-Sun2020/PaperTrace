import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from extract_pdf_bundle import split_page_blocks, POST_REFERENCE_HEADING_RE

def main():
    assert not POST_REFERENCE_HEADING_RE.match('W. Data-efficient graph grammar learning for molecular')
    assert POST_REFERENCE_HEADING_RE.match('A. Implementation')
    assert POST_REFERENCE_HEADING_RE.match('A Theoretical analysis')
    assert POST_REFERENCE_HEADING_RE.match('B Algorithmic Details')
    assert not POST_REFERENCE_HEADING_RE.match('A Novel graph learning method. Journal, 2021.')
    blocks = split_page_blocks('A Theoretical analysis\nA.1 Preliminaries\nRecall the definition.')
    assert blocks[0] == 'A Theoretical analysis'
    blocks = split_page_blocks('Running header\nA. Implementation\nFor all the models, we use layers.')
    assert 'A. Implementation' in blocks
    assert any(b.startswith('For all') for b in blocks)
    print('bibliography/appendix boundary tests passed')

if __name__ == '__main__':
    main()
