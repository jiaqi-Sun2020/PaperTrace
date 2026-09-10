#!/usr/bin/env python3
"""End-to-end safety test for profile-feedback to visible-wiki projection."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "skills" / "reader-learner" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from feedback_visible_wiki_pipeline import main as pipeline_main  # noqa: E402
from lint_visible_wiki import lint  # noqa: E402
from profile_v2 import empty_profile_v2, save_json  # noqa: E402


def reader_feedback() -> dict[str, object]:
    return {
        "reader_feedback_version": 2,
        "paper_title": "Clean Reader",
        "reader_path": r"C:\reader",
        "bundle_provenance": {
            "source_map": {"path": r"C:\reader\source_map.json", "sha256": "a" * 64},
            "completion_ledger": {"path": r"C:\reader\reader_wiki\completion_ledger.json", "sha256": "b" * 64},
            "reader_manifest": {"path": r"C:\reader\reader_wiki\reader_manifest.json", "sha256": "c" * 64},
            "structure_validation_report": {"path": r"C:\reader\reader_wiki\structure_validation_report.json", "sha256": "d" * 64},
        },
        "items": [
            {
                "feedback_id": "concept::Hamiltonian::S001",
                "concept": "Hamiltonian",
                "concept_id": "hamiltonian",
                "concept_type": "math_object",
                "status": "learning",
                "source_anchor": "S001",
                "block_id": "S001",
                "bilingual_block_id": "S001",
                "annotation_kind": "concept",
                "source_excerpt": "Hamiltonian directly generates graph dynamics.",
                "selected_language": "original",
                "original_context": "Hamiltonian directly generates graph dynamics.",
                "translation_context": "A Chinese translation.",
                "note": "Need paper-specific usage.",
                "user_question": "How is it made learnable here?",
            }
        ],
    }


def news_feedback() -> dict[str, object]:
    return {
        "title": "News Briefing",
        "date_range": "2026-07-13",
        "items": [
            {
                "concept": "Quantum error correction",
                "status": "unknown",
                "source_title": "Official update",
                "source_url": "https://example.org/news",
                "category": "quantum computing",
                "source_excerpt": "A short source-grounded briefing item.",
                "user_question": "What is the decoding bottleneck?",
            }
        ],
    }


def chat_patch() -> dict[str, object]:
    return {
        "patch_version": 1,
        "generated_from": "chat-knowledge-profile",
        "review_required": True,
        "operations": [],
        "reader_feedback_handoff": {
            "source_kind": "chat_session",
            "generated_from": "chat-knowledge-profile",
            "conversation_import_version": 1,
            "items": [
                {
                    "feedback_id": "chat-mastered::ladder-operators",
                    "concept": "Ladder operators",
                    "concept_id": "ladder-operators",
                    "canonical_concept_id": "ladder-operators",
                    "concept_type": "math_object",
                    "status": "mastered",
                    "annotation_kind": "concept",
                    "source_anchor": "chat-event-1",
                    "block_id": "chat-event-1",
                    "bilingual_block_id": "chat-event-1",
                    "source": "chat_exports/quantum-mechanics-learning.json",
                    "source_title": "Quantum mechanics learning",
                    "source_url": "chatgpt-conversation://test-conversation",
                    "source_excerpt": "How do ladder operators generate oscillator states?",
                    "original_context": "The user explicitly confirmed mastery after reviewing the chat.",
                    "selected_language": "chat_session",
                    "category": "chat_session",
                    "source_kind": "chat_session",
                    "needs_explanation": False,
                    "action": "chat_feedback_user_confirmed_mastery",
                }
            ],
        },
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="feedback_visible_wiki_", dir=ROOT) as temp:
        root = Path(temp)
        profile = root / "knowledge_profile.json"
        feedback = root / "reader_feedback.json"
        wiki = root / "wiki"
        save_json(profile, empty_profile_v2())
        feedback.write_text(json.dumps(reader_feedback(), ensure_ascii=False), encoding="utf-8")
        code = pipeline_main([
            "reader-feedback",
            "--profile", str(profile),
            "--feedback", str(feedback),
            "--wiki", str(wiki),
        ])
        if code != 0:
            raise AssertionError(f"reader-feedback pipeline failed with {code}")
        findings = lint(profile, wiki, require_profile_coverage=True)
        if findings:
            raise AssertionError(findings)
        concept = wiki / "concepts" / "hamiltonian.md"
        coverage = wiki / "maps" / "Profile Coverage.md"
        if not concept.exists() or not coverage.exists():
            raise AssertionError("pipeline did not create visible concept and coverage pages")
        if "C:\\reader" in concept.read_text(encoding="utf-8"):
            raise AssertionError("pipeline leaked a raw local path into a public concept page")
        if "Visible stable concept pages: 1 / 1" not in coverage.read_text(encoding="utf-8"):
            raise AssertionError("coverage map does not prove full stable-concept projection")
        if not list(root.glob("knowledge_profile.json.*.bak")):
            raise AssertionError("feedback import did not create a profile backup")
        news_profile = root / "news_knowledge_profile.json"
        news_feedback_path = root / "news_feedback.json"
        news_wiki = root / "news_wiki"
        save_json(news_profile, empty_profile_v2())
        news_feedback_path.write_text(json.dumps(news_feedback(), ensure_ascii=False), encoding="utf-8")
        news_code = pipeline_main([
            "news-feedback",
            "--profile", str(news_profile),
            "--feedback", str(news_feedback_path),
            "--wiki", str(news_wiki),
        ])
        if news_code != 0:
            raise AssertionError(f"news-feedback pipeline failed with {news_code}")
        news_findings = lint(news_profile, news_wiki, require_profile_coverage=True)
        if news_findings:
            raise AssertionError(news_findings)
        if not news_feedback_path.with_name("news_feedback_reader_feedback.json").exists():
            raise AssertionError("news feedback was not normalized before profile import")
        news_profile_data = json.loads(news_profile.read_text(encoding="utf-8"))
        concept_data = news_profile_data["concepts"].get("quantum-error-correction")
        if not isinstance(concept_data, dict) or concept_data.get("status") != "unknown":
            raise AssertionError("news feedback did not preserve its explicit knowledge status")
        chat_profile = root / "chat_knowledge_profile.json"
        chat_patch_path = root / "chat_profile_patch.json"
        chat_wiki = root / "chat_wiki"
        save_json(chat_profile, empty_profile_v2())
        chat_patch_path.write_text(json.dumps(chat_patch(), ensure_ascii=False), encoding="utf-8")
        chat_code = pipeline_main([
            "chat-feedback",
            "--profile", str(chat_profile),
            "--feedback", str(chat_patch_path),
            "--wiki", str(chat_wiki),
        ])
        if chat_code != 0:
            raise AssertionError(f"chat-feedback pipeline failed with {chat_code}")
        chat_findings = lint(chat_profile, chat_wiki, require_profile_coverage=True)
        if chat_findings:
            raise AssertionError(chat_findings)
        chat_profile_data = json.loads(chat_profile.read_text(encoding="utf-8"))
        chat_concept = chat_profile_data["concepts"].get("ladder-operators")
        if not isinstance(chat_concept, dict) or chat_concept.get("status") != "mastered":
            raise AssertionError("chat feedback did not preserve explicit user-confirmed mastery")
        sources = list(chat_profile_data.get("sources", {}).values())
        if not sources or sources[0].get("source_kind") != "chat_session":
            raise AssertionError("chat feedback did not preserve chat_session provenance")
        if not list(root.glob("chat_knowledge_profile.*.json.bak")):
            raise AssertionError("chat feedback import did not create a profile backup")
        first_chat_snapshot = chat_profile.read_text(encoding="utf-8")
        first_backup_count = len(list(root.glob("chat_knowledge_profile.*.json.bak")))
        repeated_chat_code = pipeline_main([
            "chat-feedback",
            "--profile", str(chat_profile),
            "--feedback", str(chat_patch_path),
            "--wiki", str(chat_wiki),
        ])
        if repeated_chat_code != 0:
            raise AssertionError(f"idempotent chat-feedback rerun failed with {repeated_chat_code}")
        if chat_profile.read_text(encoding="utf-8") != first_chat_snapshot:
            raise AssertionError("idempotent chat-feedback rerun mutated the profile")
        if len(list(root.glob("chat_knowledge_profile.*.json.bak"))) != first_backup_count:
            raise AssertionError("idempotent chat-feedback rerun wrote an unnecessary backup")
        unsafe_profile = root / "unsafe_chat_profile.json"
        unsafe_patch_path = root / "unsafe_chat_patch.json"
        save_json(unsafe_profile, empty_profile_v2())
        unsafe_patch = chat_patch()
        unsafe_patch["reader_feedback_handoff"]["source_kind"] = "reader_bundle"  # type: ignore[index]
        unsafe_patch["reader_feedback_handoff"]["reader_feedback_version"] = 2  # type: ignore[index]
        unsafe_patch_path.write_text(json.dumps(unsafe_patch, ensure_ascii=False), encoding="utf-8")
        unsafe_code = pipeline_main([
            "chat-feedback",
            "--profile", str(unsafe_profile),
            "--feedback", str(unsafe_patch_path),
            "--wiki", str(root / "unsafe_chat_wiki"),
        ])
        if unsafe_code == 0:
            raise AssertionError("chat-feedback accepted a patch impersonating reader feedback")
        unsafe_data = json.loads(unsafe_profile.read_text(encoding="utf-8"))
        if unsafe_data.get("concepts") or unsafe_data.get("events"):
            raise AssertionError("rejected chat patch mutated the profile")
        if list(root.glob("unsafe_chat_profile.*.json.bak")):
            raise AssertionError("rejected chat patch wrote a backup before validation")
    print("feedback-to-visible-wiki pipeline test: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
