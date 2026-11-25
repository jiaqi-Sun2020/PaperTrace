from copy import deepcopy

import pytest
from bs4 import BeautifulSoup
from test_reading_analysis import fixture, write
from reading_analysis import validate_reading_analysis
from reading_scan import validate_scan
from paper_history_ui import render_paper_history
from markdown_reader_to_html import build_paper_summary_panel


def result(kind="standalone", **changes):
    return dict({"kind": kind, "subject": "可识别性", "finding": "参数由观测唯一确定",
                 "scope": "仅对满秩情形", "source_anchors": ["S001"]}, **changes)


def brief(*rows):
    return {"headline": "满秩是可识别的充分条件", "items": list(rows)}


@pytest.mark.parametrize("count", [1, 3, 7])
def test_all_findings_visible_and_grounded_before_full_summary(tmp_path, count):
    _, _, summary, _ = fixture(tmp_path)
    rows = [result(subject=f"问题 {i}") for i in range(count)]
    if count > 1:
        rows[-1] = result("comparison", subject="测量法", finding="误差更小",
                          metric="均方根误差", baseline="等样本的最小二乘估计")
    summary["result_brief"] = brief(*rows)
    assert not validate_scan(summary, {}, {"S001"}, required=True)
    soup = BeautifulSoup(build_paper_summary_panel(summary, tmp_path, False, []), "html.parser")
    panel = soup.select_one(".result-brief")
    assert panel.find_previous_sibling().name == "h2"
    assert panel.find_next_sibling(class_="paper-summary-overview")
    assert len(panel.select("li")) == count and not panel.select("details")
    for row in rows:
        link = panel.find("a", string=row["subject"])
        li = link.find_parent("li")
        assert link["href"] == "#S001" and row["finding"] in li.text and row["scope"] in li.text
        if row["kind"] == "comparison":
            assert row["baseline"] in li.text and li.find_parent("section").h4.text == row["metric"]
        else:
            assert "对照：" not in li.text


@pytest.mark.parametrize("bad", [result("comparison", metric="耗时"), result("comparison", baseline="模型乙"),
                                 result(source_anchors=["absent"]), result("standalone", baseline="臆造"),
                                 result(scope="")])
def test_incomplete_or_unbound_findings_fail(bad):
    assert validate_scan({"result_brief": brief(bad)}, {}, {"S001"}, required=True)


def test_roles_not_inferred_from_cites_and_details_keep_original(tmp_path):
    _, history, _, _ = fixture(tmp_path)
    base = history["nodes"][0]
    for i, label in enumerate(["证明方法", "比较基线"]):
        node = deepcopy(base)
        node.update(current=False, id=f"prior{i}", title=f"Original title {i}")
        node["reading_role"] = dict(label=label, topic="局部化", explanation="特定用途 <不能当标签>",
                                    source_anchors=["S001"])
        history["nodes"].append(node)
        history["relations"].append({"from": "current", "to": node["id"], "type": "cites",
                                    "explanation": "理由", "evidence": {"excerpt": "quote", "url": base["url"], "locator": "p1"}})
    soup = BeautifulSoup(render_paper_history(history), "html.parser")
    for i, label in enumerate(["证明方法", "比较基线"]):
        detail = soup.find(id=f"history-prior{i}")
        assert detail.parent.h3.select_one(".history-role").text == label
        assert detail.h4.text == f"Original title {i}" and "引用" in detail.text
        assert detail.select_one(".history-source-links a")["href"] == "#S001"
        assert "<不能当标签>" in detail.parent.select_one(".history-contribution").text
    assert validate_scan({"result_brief": brief(result())}, history, {"S001"}, required=True)
    base["reading_role"] = dict(label="本文工作", topic="对象", explanation="限定结论", source_anchors=["S001"])
    assert not validate_scan({"result_brief": brief(result())}, history, {"S001"}, required=True)
    external = history["nodes"][1]["reading_role"]
    external.update(source_anchors=[], evidence_relation=["current", "prior0", "cites"])
    assert not validate_scan({"result_brief": brief(result())}, history, {"S001"}, required=True)
    external["evidence_relation"][1] = "prior1"
    assert validate_scan({"result_brief": brief(result())}, history, {"S001"}, required=True)


def test_contract_gate_and_downgrade(tmp_path):
    import json
    records, _, summary, _ = fixture(tmp_path)
    wiki = tmp_path / "reader_wiki"
    path = wiki / "reading_analysis_contract.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    write(path, dict(contract, reading_scan_version=1))
    errors = validate_reading_analysis(tmp_path, records, summary)[2]
    assert any("result_brief" in e for e in errors) and any("reading_role" in e for e in errors)
    write(wiki / "completion_run_state.json", {"reading_scan_version": 1})
    write(path, contract)
    assert any("removed" in e for e in validate_reading_analysis(tmp_path, records, summary)[2])
