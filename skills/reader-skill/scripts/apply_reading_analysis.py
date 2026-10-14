"""Apply explicitly authored notes/summary/history; no content generation.

Run from the project root: python -B skills/reader-skill/scripts/apply_reading_analysis.py READER AUTHORED_JSON
"""
import argparse
import json
from pathlib import Path
from completion_state import atomic_write_json, load_all_records, record_path, write_record, utc_now, update_run_state, compile_canonical_markdown
from reading_analysis import analysis_records, notes_digest, declare_reading_analysis, file_hash, validate_history


def apply(reader, authored):
    records = load_all_records(reader)
    notes = authored["notes"]
    expected = {r["stable_id"] for r in analysis_records(records)}
    if set(notes) != expected or any(not isinstance(v, str) or not v.strip() for v in notes.values()):
        raise ValueError(f"notes must cover exact non-reference records; missing={sorted(expected-set(notes))}; extra={sorted(set(notes)-expected)}")
    history = authored["history"]
    errors = validate_history(history, {r["source_anchor"] for r in records}, file_hash(reader / "source_map.json"))
    if errors:
        raise ValueError("; ".join(errors))
    wiki = reader / "reader_wiki"
    # Semantic text comes exclusively from the supplied, primary-authored packet.
    summary = json.loads((wiki / "paper_summary.json").read_text(encoding="utf-8"))
    summary["schema_version"] = 2
    summary["logic_chain"] = authored["logic_chain"]
    for record in records:
        if record["stable_id"] in notes:
            record["notes"] = notes[record["stable_id"]]
            record["updated_at"] = utc_now()
            write_record(reader, record)
    atomic_write_json(wiki / "paper_summary.json", summary)
    atomic_write_json(wiki / "paper_history.json", history)
    declare_reading_analysis(reader)
    review = dict(authored["review"])
    review["reviewed_record_ids"] = sorted(notes)
    review["bound_content"] = {"notes_sha256": notes_digest(records), "summary_sha256": file_hash(wiki / "paper_summary.json"), "history_sha256": file_hash(wiki / "paper_history.json")}
    review["reviewed_at"] = utc_now()
    atomic_write_json(wiki / "reading_analysis_review.json", review)
    update_run_state(reader)
    compile_canonical_markdown(reader, materialize_paper=True)
    print(json.dumps({"notes_updated": len(notes), "history_nodes": len(history["nodes"]), "reference_records_untouched": len(records)-len(notes)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reader")
    parser.add_argument("authored_json")
    args = parser.parse_args()
    apply(Path(args.reader).resolve(), json.loads(Path(args.authored_json).read_text(encoding="utf-8")))
