"""Chronological timeline with inline disclosure; reader-skill owns the facts."""
import html
import json

RELATIONS = {"cites":"引用", "uses":"沿用方法", "extends":"扩展", "tests":"验证", "challenges":"挑战", "related":"相关工作"}
DATES = {"preprint":"预印本", "published":"正式发表", "revised":"修订", "unknown":"日期未核实"}


def short_name(node):
    return node["title"].split(" · ", 1)[0]


def render_paper_history(history):
    if not history:
        return ""
    esc = lambda v: html.escape(str(v), quote=True)
    nodes = sorted(history["nodes"], key=lambda n:min(d.get("date") or "9999-12-31" for d in n["dates"]))
    names = {n["id"]:short_name(n) for n in nodes}
    rows = []
    for node in nodes:
        target = "history-" + node["id"]
        dates = sorted(node["dates"], key=lambda d:d.get("date") or "9999-12-31")
        all_dates = "；".join("日期未核实" if d["kind"] == "unknown" else f'{d["date"]}（{DATES[d["kind"]]}）' for d in dates)
        first_date = dates[0].get("date") or "日期未核实"
        relations, evidence_rows = [], []
        for edge in history.get("relations", []):
            if node["id"] not in {edge["from"],edge["to"]}:
                continue
            label = f'{names[edge["from"]]} {RELATIONS[edge["type"]]} {names[edge["to"]]}'
            relations.append(label)
            evidence = edge["evidence"]
            evidence_rows.append(f'<li><strong>{esc(label)}</strong><p>{esc(edge["explanation"])}</p><blockquote>{esc(evidence["excerpt"])}</blockquote><a href="{esc(evidence["url"])}" target="_blank" rel="noopener noreferrer">原文依据：{esc(evidence["locator"])}</a></li>')
        relation_text = "；".join(relations) or "暂无已核实的直接关系"
        sources = f'<a href="{esc(node["url"])}" target="_blank" rel="noopener noreferrer">论文原始来源</a>' if node.get("url") else '<span>外部链接尚未核实</span>'
        sources += ' ' + ' '.join(f'<a href="#{esc(a)}">本文 {esc(a)}</a>' for a in node.get("source_anchors",[]))
        current = ' aria-current="true"' if node.get("current") else ''
        current_label = '<span class="history-current-label">当前论文</span>' if node.get("current") else ''
        rows.append(f'''<li class="history-node"{current}>
<div class="history-date">{esc(first_date)}<span>{DATES[dates[0]["kind"]] if dates[0]["kind"] != "unknown" else "待核实"}</span></div>
<div class="history-node-body"><h3>{esc(short_name(node))}{current_label}</h3><p class="history-contribution">{esc(node["summary"])}</p><p class="history-relation">{esc(relation_text)}</p>
<details id="{esc(target)}" class="history-detail"><summary>研究详情与依据</summary><div class="history-detail-content"><h4>{esc(node["title"])}</h4><p class="history-all-dates">{esc(all_dates)}</p>
<section><h5>研究问题与方法</h5><p>{esc(node["question"])}</p><p>{esc(node["method"])}</p></section>
<section><h5>推进与效果条件</h5><p>{esc(node["advance"])}</p><p>{esc(node["results"])}</p></section>
<section><h5>局限与关系依据</h5><p>{esc(node["limitations"])}</p><p class="history-source-links">{sources}</p><ul class="history-evidence">{''.join(evidence_rows)}</ul></section></div></details></div></li>''')
    gaps = ''.join(f'<li>{esc(v)}</li>' for v in history["gaps"])
    scope = ''.join(f'<li>{esc(s.get("query",""))}<p>{esc(s.get("status",""))} <a href="{esc(s["url"])}">检索入口</a></p></li>' for s in history["searches"] if s.get("url","").startswith("https://"))
    status = {"verified":"所列关系已核实", "partial":"部分核实，仍有证据缺口", "not_checked":"外部历史尚未核实"}[history["status"]]
    data = json.dumps(history,ensure_ascii=False).replace("<","\\u003c")
    return f'<section class="paper-history" id="paper-history"><h2>论文历史轴 / Research History</h2><p class="history-intro">沿时间查看相关工作的贡献，再展开核对方法和依据。轴线只表示先后，不表示继承。</p><p class="history-verification">核验截至 {esc(history["checked_as_of"])}；{status}。</p><ol class="history-timeline">{"".join(rows)}</ol><details class="history-scope"><summary>检索范围与证据缺口</summary><ul>{scope}</ul><ul>{gaps}</ul></details><script type="application/json" id="paper-history-data">{data}</script></section>'


def paper_history_styles():
    return '''<style>
.paper-history{color:var(--reader-text);background:var(--reader-card-bg);padding:1.5rem;border:1px solid var(--reader-border);border-radius:8px;margin:0 0 1.5rem;min-width:0;overflow-wrap:anywhere}
.paper-history h2{font-size:1.3rem;line-height:1.4;margin:0 0 .7rem;letter-spacing:0}.history-intro{font-size:.94rem;line-height:1.7;margin:0 0 .5rem}.history-verification{font-size:.82rem;line-height:1.6;margin:0}
.history-timeline{list-style:none;padding:0;margin:1.5rem 0;display:grid}.history-node{display:grid;grid-template-columns:7.3rem minmax(0,1fr);gap:1.2rem;margin:0;position:relative}
.history-node-body{border-left:2px solid var(--reader-muted);padding:0 0 1.5rem 1.2rem;min-width:0;position:relative}.history-node-body:before{content:"";position:absolute;left:-5px;top:6px;width:8px;height:8px;border-radius:50%;background:var(--reader-link)}
.history-node:last-child .history-node-body{padding-bottom:.5rem}.history-date{font-size:.83rem;font-variant-numeric:tabular-nums;line-height:1.65;padding-top:1px}.history-date span{display:block;font-size:.76rem}
.history-node h3{font-size:1.06rem;line-height:1.5;font-weight:600;margin:0 0 .35rem;color:var(--reader-text)}.history-current-label{font-size:.75rem;margin-left:.65rem;color:var(--reader-link);font-weight:600}.history-node[aria-current] .history-node-body{border-left-color:var(--reader-link)}
.history-contribution{line-height:1.75;margin:0 0 .5rem;font-size:.94rem}.history-relation{font-size:.81rem;line-height:1.7;margin:0 0 .3rem;color:var(--reader-text)}
.history-detail{margin:0;border:0;padding:0;border-radius:0}.history-detail summary,.history-scope summary{cursor:pointer;min-height:44px;align-content:center;color:var(--reader-link);font-weight:500;font-size:.86rem;list-style-position:inside}
.history-detail-content{padding:.9rem 0 .5rem}.history-detail h4{font-size:.95rem;font-weight:600;line-height:1.7;margin:0 0 .5rem}.history-all-dates{font-size:.8rem;line-height:1.7}.history-detail h5{font-size:.86rem;line-height:1.6;margin:1rem 0 .4rem;font-weight:600;color:var(--reader-text)}
.history-detail p{font-size:.9rem;line-height:1.8;margin:0 0 .55rem}.history-evidence{padding-left:1.1rem;font-size:.86rem;line-height:1.7}.history-evidence li{margin:.9rem 0}.paper-history blockquote{margin:.5rem 0;padding:.35rem .8rem;border-left:2px solid var(--reader-border);font-size:.85rem;line-height:1.7}
.history-scope{padding-top:.7rem;border-top:1px solid var(--reader-border)}.history-scope li{font-size:.86rem;line-height:1.75;margin:.5rem 0}.paper-history a{color:var(--reader-link)}.history-source-links a{margin-right:.5rem}
.paper-history a:focus-visible,.paper-history summary:focus-visible{outline:2px solid var(--reader-link);outline-offset:3px}.paper-history summary:hover{text-decoration:underline;text-underline-offset:3px}
@container reader (max-width:620px){.paper-history{padding:1rem}.history-node{grid-template-columns:1fr;gap:.25rem}.history-date{padding-left:1.2rem}.history-date span{display:inline;margin-left:.5rem}.history-node-body{padding-left:1.1rem}}
@media(max-width:620px){.history-node{grid-template-columns:1fr;gap:.25rem}.history-date span{display:inline;margin-left:.5rem}}
@media print{.paper-history{break-inside:auto}.history-detail>*,.history-scope>*{display:block!important}.history-detail::details-content,.history-scope::details-content{display:block!important;content-visibility:visible!important}.history-node{break-inside:auto}.history-node h3,.history-date{break-after:avoid}}
</style>'''


def paper_history_script():
    return '''<script>
(function(){
 function revealHash(){var id;try{id=decodeURIComponent(location.hash.slice(1));}catch(e){return;}if(!id.startsWith('history-'))return;var d=document.getElementById(id);if(d&&d.classList.contains('history-detail'))d.open=true;}
 revealHash();window.addEventListener('hashchange',revealHash);
 document.addEventListener('beforeprint',function(){document.querySelectorAll('.paper-history details').forEach(function(d){d.dataset.printWasOpen=d.open?'1':'0';d.open=true;});});
 document.addEventListener('afterprint',function(){document.querySelectorAll('.paper-history details').forEach(function(d){d.open=d.dataset.printWasOpen==='1';});});
})();
</script>'''
