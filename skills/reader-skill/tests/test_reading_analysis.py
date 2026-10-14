import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "utils/lean-html-skill/scripts"))
from reading_analysis import validate_reading_analysis, validate_history, notes_digest, file_hash, declare_reading_analysis, strong_identity_keys
from paper_history_ui import render_paper_history
from reader_wiki_compile import load_authored_paper_summary
from markdown_reader_to_html import render_document


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def fixture(tmp_path):
    records = [{"stable_id":"block:S001", "source_anchor":"S001", "record_kind":"block", "original":"A reported rule connects input to output.", "notes":"给定明确输入，按原文规则改变记录，结果只支持该条件内的结论。"}]
    write(tmp_path / "source_map.json", {"blocks":[{"id":"S001"}]})
    wiki = tmp_path / "reader_wiki"
    declare_reading_analysis(tmp_path)
    # This fixture intentionally represents the original analysis-v1 contract.
    contract = json.loads((wiki / 'reading_analysis_contract.json').read_text())
    contract.pop('logic_visualization_version', None)
    write(wiki / 'reading_analysis_contract.json', contract)
    node = {"id":"current", "identity":{"arxiv":"2601.00001"}, "current":True, "title":"Example", "url":"https://arxiv.org/abs/2601.00001", "summary":"对象明确", "question":"问题", "method":"动作", "advance":"进展", "results":"条件内的结果", "limitations":"范围", "dates":[{"kind":"preprint", "date":"2026-01-01", "source_url":"https://arxiv.org/abs/2601.00001"}], "source_anchors":["S001"]}
    history = {"schema_version":1,"source_map_sha256":file_hash(tmp_path / "source_map.json"),"status":"partial","checked_as_of":"2026-10-13","nodes":[node],"relations":[],"searches":[],"gaps":["Network unavailable; no successor claim."]}
    entry = {"text":"这一段使用明确前提推进具体操作，结论保留原文适用条件，并指向下一步可检查的证据。","source_anchors":["S001"]}
    summary = {"schema_version":2,"language":"zh-CN","overview":dict(entry,text=entry["text"]*3),"what_it_does":[entry,entry],"how_it_works":[entry,entry,entry],"why_it_matters":[entry,entry],"evidence_and_limitations":[entry],"logic_chain":[dict(entry,role="question"),dict(entry,role="conclusion")]}
    write(wiki / "paper_history.json", history)
    write(wiki / "paper_summary.json", summary)
    review = {"review_type":"self_review","reviewed_record_ids":["block:S001"],"bound_content":{"notes_sha256":notes_digest(records),"history_sha256":file_hash(wiki / "paper_history.json"),"summary_sha256":file_hash(wiki / "paper_summary.json")},"rounds":[{"round":i,"result":"pass","judgment":"Actual scoped check","limitation":"Not proof of learning","quotes":[{"record_id":"block:S001","text":"按原文规则改变记录"}]} for i in range(1,9)]}
    write(wiki / "reading_analysis_review.json", review)
    return records, history, summary, review


def test_declared_contract_pass_and_unknown_history(tmp_path):
    records, history, summary, _ = fixture(tmp_path)
    assert validate_reading_analysis(tmp_path,records,summary)[2] == []
    history["nodes"][0]["dates"] = [{"kind":"unknown","date":None}]
    history["nodes"][0]["url"] = None
    history["status"] = "not_checked"
    assert validate_history(history,{"S001"},file_hash(tmp_path / "source_map.json")) == []
    output = render_paper_history(history)
    assert "日期未核实" in output and 'href="None"' not in output


def test_old_reader_and_v1_summary_remain_readable(tmp_path):
    records, history, summary, _ = fixture(tmp_path)
    (tmp_path / "reader_wiki/reading_analysis_contract.json").unlink()
    assert validate_reading_analysis(tmp_path,records,summary) == ({},{},[])
    summary["schema_version"] = 1
    summary.pop("logic_chain")
    write(tmp_path / "reader_wiki/paper_summary.json",summary)
    loaded, errors = load_authored_paper_summary(tmp_path,{"blocks":[{"id":"S001"}]},records,required=True)
    assert loaded["schema_version"] == 1 and not errors


def test_stale_or_missing_review_and_missing_note_fail(tmp_path):
    records, _, summary, review = fixture(tmp_path)
    records[0]["notes"] = ""
    errors = validate_reading_analysis(tmp_path,records,summary)[2]
    assert any("missing/non-specific" in e for e in errors)
    assert any("stale" in e for e in errors)
    review["rounds"][0]["quotes"][0]["text"] = "Invented quote"
    write(tmp_path / "reader_wiki/reading_analysis_review.json",review)
    assert any("not present" in e for e in validate_reading_analysis(tmp_path,records,summary)[2])
    (tmp_path / "reader_wiki/reading_analysis_review.json").unlink()
    assert any("missing" in e for e in validate_reading_analysis(tmp_path,records,summary)[2])


def test_removed_declaration_cannot_downgrade(tmp_path):
    records, _, summary, _ = fixture(tmp_path)
    write(tmp_path / "reader_wiki/completion_run_state.json",{"reading_analysis_version":1})
    (tmp_path / "reader_wiki/reading_analysis_contract.json").unlink()
    assert "removed" in validate_reading_analysis(tmp_path,records,summary)[2][0]


def test_identity_dates_and_unbound_relation_rejected(tmp_path):
    _, history, _, _ = fixture(tmp_path)
    other = copy.deepcopy(history["nodes"][0]); other["current"] = False; other["id"] = "other"
    history["nodes"].append(other)
    history["relations"] = [{"from":"current","to":"other","type":"extends","explanation":"Later is not enough", "evidence":{"url":"https://arxiv.org/abs/2601.00001","excerpt":"not a source quote","locator":"abstract","checked_on":"2026-10-13"}}]
    other["dates"][0]["date"] = "2026-99-40"
    errors = validate_history(history,{"S001"},history["source_map_sha256"])
    assert any("duplicate strong" in e for e in errors)
    assert any("local source anchor" in e for e in errors)
    assert any("dates require" in e for e in errors)


def test_quote_must_exist_at_real_source(tmp_path):
    records, history, summary, review = fixture(tmp_path)
    other = copy.deepcopy(history["nodes"][0]); other.update(id="other",identity={"arxiv":"2602.00002"},current=False)
    history["nodes"].append(other)
    history["relations"] = [{"from":"current","to":"other","type":"cites","explanation":"Actual citation", "evidence":{"url":"https://arxiv.org/abs/2601.00001","excerpt":"Fabricated", "source_anchor":"S001","locator":"abstract","checked_on":"2026-10-13"}}]
    write(tmp_path / "reader_wiki/paper_history.json",history)
    assert any("absent from its source" in e for e in validate_reading_analysis(tmp_path,records,summary)[2])


def test_history_escape_and_embedded_data(tmp_path):
    _, history, _, _ = fixture(tmp_path)
    history["nodes"][0]["title"] = '</script><img src=x onerror=alert(1)>'
    output = render_paper_history(history)
    assert '&lt;img' in output and '<img src=x' not in output
    assert output.count('</script>') == 1
    embedded = output.split('id="paper-history-data">')[1].split('</script>')[0]
    assert json.loads(embedded) == history


def test_standalone_c_record_is_not_swallowed(tmp_path):
    md = '<a id="S001"></a>\n**Source:** p.1 S001\n\n**Original:** Source.\n\n**中文:** 原文。\n\n**注释:** 第一段逻辑。\n\n<a id="C001"></a>\n**Source:** p.2 C001\n\n**Original:** Caption.\n\n**中文:** 图注。\n\n**注释:** 必须完整保留的图注逻辑。'
    output, _ = render_document(md,tmp_path,False,[])
    assert 'id="C001"' in output and '必须完整保留的图注逻辑' in output
    assert output.count('class="bilingual-block has-notes"') == 2


def test_strong_ids_normalize_without_title_merge():
    assert strong_identity_keys({"doi":"https://doi.org/10.1234/ABC","arxiv":"https://arxiv.org/abs/2601.00001v3"}) == {"doi:10.1234/abc","arxiv:2601.00001"}
    assert strong_identity_keys({"title":"Same title"}) == set()


def test_new_bundle_feature_survives_discovery_resume(tmp_path):
    write(tmp_path / "source_map.json", {"paper":{"source_pdf_sha256":"same-pdf"},"blocks":[]})
    declare_reading_analysis(tmp_path,bind_frozen=False)
    pending = json.loads((tmp_path / "reader_wiki/reading_analysis_contract.json").read_text())
    assert pending["source_map_binding"] == "pending_freeze"
    assert pending['logic_visualization_version'] == 1
    write(tmp_path / "source_map.json", {"paper":{"source_pdf_sha256":"same-pdf"},"blocks":[{"id":"F001"}]})
    declare_reading_analysis(tmp_path,bind_frozen=True)
    frozen = json.loads((tmp_path / "reader_wiki/reading_analysis_contract.json").read_text())
    assert frozen["source_map_sha256"] == file_hash(tmp_path / "source_map.json")
    assert frozen["source_map_binding"] == "frozen"


def test_formal_status_refresh_replaces_old_failure_fields(tmp_path,monkeypatch):
    import completion_state
    import pytest
    write(tmp_path / "reader_wiki/formal_status.json",{"completion_status":"incomplete","preflight_status":"fail"})
    write(tmp_path / "reader_wiki/completion_run_state.json",{"status":"pass"})
    write(tmp_path / "reader_wiki/preflight_manifest.json",{"status":"pass"})
    (tmp_path / "reader_interactive.html").write_text("<html>current</html>")
    monkeypatch.setattr(completion_state,"reader_is_formal_ready",lambda p:(True,[]))
    with pytest.raises(ValueError,match="current passing audit"):
        completion_state.clear_stale_after_audit(tmp_path)
    write(tmp_path / "reader_wiki/formal_artifact_manifest.json",{"formal_status":"pass","artifacts":{"html":{"sha256":file_hash(tmp_path / "reader_interactive.html")}}})
    completion_state.clear_stale_after_audit(tmp_path)
    status = json.loads((tmp_path / "reader_wiki/formal_status.json").read_text())
    assert status["completion_status"] == status["preflight_status"] == "pass"
