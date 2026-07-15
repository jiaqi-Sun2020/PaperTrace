# Teaching feedback contract

`teaching_feedback.json` has `teaching_feedback_version: 1`, a `teach-` session ID, selected stable profile concept ID/name, profile source refs, non-empty actual evidence, prompt-use flags, misconception, unresolved question, proposed status, proposed review schedule, confidence, and `provenance: adaptive-teach`.

The only importer is `reader-learner/scripts/import_teaching_feedback.py`, normally called through `feedback_visible_wiki_pipeline.py teaching-feedback`. It validates before mutation and then uses the existing profile backup and atomic writer.
