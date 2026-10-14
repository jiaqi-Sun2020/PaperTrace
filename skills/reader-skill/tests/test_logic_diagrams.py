import copy
import json
import re
import sys
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'utils/lean-html-skill/scripts'))
from logic_diagrams import diagrams_in_notes, notes_prose, validate_logic_diagram
from logic_diagram_ui import render_logic_diagram, render_summary_logic, logic_diagram_styles
from markdown_reader_to_html import markdown_blocks, render_document, render_tokens, split_tokens
from paper_history_ui import render_paper_history
from reader_theme import reader_theme_css
from test_reading_analysis import fixture, write
from reading_analysis import validate_reading_analysis, notes_digest


def diagram():
    return {'version':1,'kind':'flow','title':'先对齐再比较',
        'nodes':[{'id':'a','label':'低层预测'},{'id':'b','label':'编码到上层'},{'id':'c','label':'同空间距离'}],
        'edges':[{'from':'a','to':'b','type':'data_flow','basis':'source','label':'上层编码器'},
                 {'from':'b','to':'c','type':'sequence','basis':'derivation','label':'对齐后比较'}],
        'conditions':['窗口一，步幅二。'],'source_anchors':['S001']}


def fence(d):
    return '```reader-logic\n'+json.dumps(d,ensure_ascii=False)+'\n```'


def test_roundtrip_prose_and_diagram_and_two_renderers(tmp_path):
    d=diagram(); note=fence(d)+'\n\n必要条件仍在解释中。'
    assert diagrams_in_notes(note)==[d]
    assert notes_prose(note)=='必要条件仍在解释中。'
    assert markdown_blocks(note,tmp_path,False,[]).index('logic-diagram') < markdown_blocks(note,tmp_path,False,[]).index('必要条件仍在解释中')
    md='<a id="S001"></a>\n**Source:** p.1 S001\n\n**Original:** Source.\n\n**中文:** 原文。\n\n**注释:** '+note
    assert render_logic_diagram(d) in render_document(md,tmp_path,False,[])[0]
    # Both public parsing paths funnel through the same block renderer.
    output=render_tokens(split_tokens(md),tmp_path,False,[])[0]
    assert render_logic_diagram(d) in output
    assert '必要条件仍在解释中' in BeautifulSoup(output,'html.parser').select_one('.reader-notes').get_text()


@pytest.mark.parametrize('change',[
    lambda d:d.update(version=2),lambda d:d['edges'][0].update(type='causes'),
    lambda d:d['edges'][0].pop('basis'),lambda d:d['edges'][0].update(to='unknown'),
    lambda d:d['nodes'][1].update(id='a'),lambda d:d.update(kind='role'),
    lambda d:d.update(kind='comparison'),lambda d:d.update(source_anchors=['OTHER']),
    lambda d:d.update(conditions='not a list'),lambda d:d['nodes'].append({'id':'isolated','label':'无依据节点'}),
])
def test_malformed_or_unsupported_relations_fail(change):
    d=diagram();change(d);assert validate_logic_diagram(d,{'S001'})


def test_unknown_or_malformed_fence_not_silently_dropped(tmp_path):
    for text in ['```reader-logic\n{}','```reader-logic\nnot json\n```','```reader-logic\n{"version":9}\n```']:
        with pytest.raises(ValueError):markdown_blocks(text,tmp_path,False,[])
    with pytest.raises(ValueError,match='own line'):
        markdown_blocks('**Reading note:** '+fence(diagram()),tmp_path,False,[])
    assert markdown_blocks('旧解释保留。',tmp_path,False,[])=='<p>旧解释保留。</p>'


def test_diagram_is_text_safe_and_contains_all_boundaries():
    d=diagram();d['nodes'][0]['label']='</script><img src=x onerror=1>'
    out=render_logic_diagram(d); soup=BeautifulSoup(out,'html.parser')
    assert not soup.select('img,script,iframe')
    assert d['nodes'][0]['label'] in soup.get_text()
    assert len(soup.select('.logic-node'))==3
    assert '窗口一，步幅二。' in soup.get_text()
    assert soup.select_one('a')['href']=='#S001'


def test_visual_contract_cannot_use_old_review(tmp_path):
    records,_,summary,review=fixture(tmp_path)
    path=tmp_path/'reader_wiki/reading_analysis_contract.json'
    contract=json.loads(path.read_text());contract['logic_visualization_version']=1;write(path,contract)
    assert any('missing authored' in e for e in validate_reading_analysis(tmp_path,records,summary)[2])
    records[0]['notes']=fence(diagram())+'\n\n'+records[0]['notes']
    assert any('stale' in e for e in validate_reading_analysis(tmp_path,records,summary)[2])
    review['bound_content']['notes_sha256']=notes_digest(records);write(tmp_path/'reader_wiki/reading_analysis_review.json',review)
    assert not validate_reading_analysis(tmp_path,records,summary)[2]
    records[0]['notes']=fence(diagram())
    assert any('must not replace' in e for e in validate_reading_analysis(tmp_path,records,summary)[2])


def test_browser_missing_evidence_does_not_become_visual_pass():
    from adversarial_html_audit import browser_report_issues
    assert browser_report_issues({'status':'pass','html_sha256':'old'},'new')
    assert browser_report_issues({'status':'fail','html_sha256':'new'},'new')
    report={'status':'not_run','html_sha256':'new','reason':'URL policy blocked file scheme','limitation':'No screenshots or computed layout measured'}
    assert not browser_report_issues(report,'new')
    assert report['status']=='not_run'
    assert browser_report_issues({'status':'not_run','html_sha256':'new'},'new')


def test_removed_visual_flag_cannot_silently_downgrade(tmp_path):
    records,_,summary,_=fixture(tmp_path)
    write(tmp_path/'reader_wiki/completion_run_state.json',{'reading_analysis_version':1,'logic_visualization_version':1})
    assert any('visualization declaration removed' in e for e in validate_reading_analysis(tmp_path,records,summary)[2])


def test_integrated_history_keeps_every_node_field_and_evidence(tmp_path):
    _,history,_,_=fixture(tmp_path)
    other=copy.deepcopy(history['nodes'][0]);other.update(id='old',current=False,title='Old · 全标题',summary='前作贡献')
    history['nodes'].append(other)
    history['relations']=[{'from':'current','to':'old','type':'uses','explanation':'只沿用该方法',
        'evidence':{'url':'https://arxiv.org/abs/2601.00001','locator':'section 2','excerpt':'actual evidence'}}]
    out=render_paper_history(history);soup=BeautifulSoup(out,'html.parser')
    assert not soup.select('.history-rail,.history-details')
    assert len(soup.select('.history-node'))==2
    assert len(soup.select('.history-detail:not([open])'))==2
    assert len(soup.select('.history-node[aria-current]'))==1
    for n in history['nodes']:
        for key in ('title','summary','question','method','advance','results','limitations'):
            assert n[key] in soup.get_text()
    assert 'Example 沿用方法 Old' in soup.get_text()
    assert 'actual evidence' in soup.get_text()
    assert json.loads(soup.select_one('#paper-history-data').string)==history


def test_summary_map_preserves_roles_text_and_source():
    items=[{'role':'问题','text':'完整问题','source_anchors':['S001']},{'role':'证据','text':'有限证据','source_anchors':['S002']}]
    out=render_summary_logic(items,lambda t:t,lambda anchors:' '.join(anchors))
    soup=BeautifulSoup(out,'html.parser');assert len(soup.select('.argument-map>li'))==2
    for item in items:
        assert item['role'] in soup.get_text() and item['text'] in soup.get_text()
    assert '不表示物理因果' in soup.get_text()


def ratio(a,b):
    def luminance(h):
        rgb=[int(h[i:i+2],16)/255 for i in (1,3,5)]
        rgb=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
        return sum(v*w for v,w in zip(rgb,[.2126,.7152,.0722]))
    x,y=sorted([luminance(a),luminance(b)])
    return (y+.05)/(x+.05)


def test_all_theme_foreground_surface_and_structural_lines():
    css=reader_theme_css()
    for theme in ('default','sepia','dark','contrast'):
        body=re.search(r':root\[data-theme="'+theme+r'"\]\s*\{([^}]+)',css).group(1)
        tokens=dict(re.findall(r'(--reader-[\w-]+):\s*(#[0-9a-fA-F]{6})',body))
        for bg in ('--reader-card-bg','--reader-panel-bg','--reader-note-bg'):
            assert ratio(tokens['--reader-text'],tokens[bg])>=4.5
            assert ratio(tokens['--reader-link'],tokens[bg])>=4.5
        assert ratio(tokens['--reader-muted'],tokens['--reader-card-bg'])>=3
    assert '@container reader (max-width:1000px)' in logic_diagram_styles()
    assert 'source-pane-width' not in logic_diagram_styles()
