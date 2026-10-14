"""Selectable native diagrams. Domain validation remains reader-skill-owned."""
import html

TYPES = {"sequence":"操作顺序", "data_flow":"数据流", "supports":"论证支持", "contrast":"对照"}
BASES = {"source":"原文", "derivation":"推导", "teaching":"教学说明"}


def render_logic_diagram(d):
    esc = lambda v: html.escape(str(v), quote=True)
    nodes, edges = d["nodes"], d["edges"]
    names = {n["id"]:n["label"] for n in nodes}
    linear = len(edges) == len(nodes)-1 and all(e["from"] == nodes[i]["id"] and e["to"] == nodes[i+1]["id"] and e["type"] != "contrast" for i,e in enumerate(edges))
    def connector(e):
        symbol = "⇄" if e["type"] == "contrast" else "↓"
        return f'<span class="logic-connector" data-relation="{esc(e["type"])}"><span>{esc(e["label"])}</span><span class="logic-arrow" aria-hidden="true">{symbol}</span><small>{TYPES[e["type"]]} / {BASES[e["basis"]]}</small></span>'
    rows = []
    if linear:
        for i,n in enumerate(nodes):
            rows.append(f'<li class="logic-step"><span class="logic-node">{esc(n["label"])}</span>{connector(edges[i]) if i < len(edges) else ""}</li>')
        body = '<ol class="logic-path">' + ''.join(rows) + '</ol>'
    else:
        for e in edges:
            rows.append(f'<li class="logic-link"><span class="logic-node">{esc(names[e["from"]])}</span>{connector(e)}<span class="logic-node">{esc(names[e["to"]])}</span></li>')
        body = '<ul class="logic-links">' + ''.join(rows) + '</ul>'
    conditions = ''.join(f'<li>{esc(v)}</li>' for v in d["conditions"])
    conditions_html = f'<ul class="logic-conditions">{conditions}</ul>' if conditions else ''
    refs = ' '.join(f'<a href="#{esc(a)}">{esc(a)}</a>' for a in d["source_anchors"])
    return f'<div class="logic-diagram logic-{esc(d["kind"])}" role="group" data-logic-version="1" aria-label="{esc(d["title"])}"><h4>{esc(d["title"])}</h4>{body}{conditions_html}<p class="logic-sources">依据 {refs}</p></div>'


def render_summary_logic(items, render_text, render_sources):
    rows = [f'<li><div class="argument-role">{html.escape(str(i.get("role") or "论证环节"))}</div><div class="argument-content">{render_text(i["text"])}{render_sources(i.get("source_anchors"))}</div></li>' for i in items]
    return '<p class="argument-caption">论证推进，不表示物理因果或所有步骤都在同一实验中发生。</p><ol class="argument-map">' + ''.join(rows) + '</ol>'


def logic_diagram_styles():
    return '''<style>
#readerDocument{container-type:inline-size;container-name:reader}
.logic-diagram{--logic-surface:var(--reader-panel-bg);--logic-ink:var(--reader-text);--logic-edge:var(--reader-link);color:var(--logic-ink);margin:0 0 1rem;padding:0 0 1rem;border-bottom:1px solid var(--reader-border);min-width:0}
.logic-diagram h4{font-size:.94rem;line-height:1.5;margin:0 0 .8rem;font-weight:600;color:var(--logic-ink)}
.logic-path,.logic-links{list-style:none!important;padding:0!important;margin:0!important;display:grid;gap:0;min-width:0}
.logic-step{margin:0!important}.logic-node{display:block;min-width:0;padding:.65rem .8rem;background:var(--logic-surface);border:1px solid var(--reader-border);border-left:3px solid var(--logic-edge);border-radius:6px;line-height:1.65;overflow-wrap:anywhere}
.logic-connector{display:flex;flex-direction:column;align-items:center;text-align:center;padding:.35rem .5rem;line-height:1.5;gap:.1rem;color:var(--logic-ink);font-size:.85rem}.logic-connector small{font-size:.74rem;color:var(--logic-ink)}
.logic-arrow{color:var(--logic-edge);font-size:1.15rem;font-weight:700;line-height:1}.logic-link{display:grid;gap:0;margin:0 0 .6rem!important}
.logic-conditions{margin:.7rem 0 0!important;padding-left:1.2rem!important;font-size:.86rem;line-height:1.65}.logic-sources{font-size:.78rem;margin:.65rem 0 0!important}.logic-sources a{color:var(--reader-link);margin-right:.35rem}
.argument-caption{font-size:.85rem;line-height:1.6}.argument-map{list-style:none;padding:0!important;display:grid;gap:.8rem}.argument-map>li{display:grid;grid-template-columns:8rem minmax(0,1fr);gap:1rem;margin:0!important}
.argument-role{font-weight:600;color:var(--reader-link);border-left:3px solid var(--reader-link);padding-left:.75rem;line-height:1.6}.argument-content{line-height:1.8;min-width:0}.argument-content .summary-sources{display:block;margin-top:.4rem}
.logic-diagram a:focus-visible{outline:2px solid var(--reader-link);outline-offset:3px}
@container reader (max-width:1000px){.bilingual-block.has-notes .pair-grid{grid-template-columns:minmax(0,1fr) minmax(0,1fr)}.bilingual-block.has-notes .reader-notes{grid-column:1/-1}body.original-collapsed .bilingual-block.has-notes .pair-grid{grid-template-columns:minmax(0,1fr)}}
@container reader (min-width:1001px){.bilingual-block.has-notes .pair-grid{grid-template-columns:minmax(0,1.05fr) minmax(0,.95fr) minmax(260px,.85fr)}}
@container reader (max-width:620px){.pair-grid,.bilingual-block.has-notes .pair-grid{grid-template-columns:minmax(0,1fr)}.argument-map>li{grid-template-columns:1fr;gap:.35rem}}
@container reader (min-width:700px){.figure-card .logic-link{grid-template-columns:minmax(0,1fr) minmax(7rem,.7fr) minmax(0,1fr);align-items:center}}
@media print{#readerDocument{container-type:normal}.logic-diagram,.argument-map{break-inside:auto}.logic-node,.logic-step,.argument-map>li{break-inside:avoid}.logic-diagram{--logic-surface:#fff;--logic-ink:#111;--logic-edge:#222}}
</style>'''
