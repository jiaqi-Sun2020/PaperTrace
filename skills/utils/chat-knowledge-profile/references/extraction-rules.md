# Extraction Rules

Extract conservatively from chat sessions.

## Source Hierarchy

Prefer user-authored turns for profile state. Assistant turns can support topic discovery, but they must not by themselves establish that the user knows, does not know, prefers, or endorses something.

## Strong Signals

Treat these as high-confidence only when said by the user:

- "remember", "以后", "记住", "始终", "默认"
- "I prefer", "我喜欢", "我希望", "优先"
- "I don't understand", "不懂", "不理解", "卡住"
- "I understand", "我懂了", "我会用", "掌握"
- explicit project rules such as "不要", "必须", "交给", "归 ... 负责"

## Weak Signals

Treat as `unrated` or low-confidence:

- A concept merely appears in assistant output.
- A topic appears once without the user saying it is important.
- The user asks a one-off operational question.
- An assistant-generated summary says the user is interested in something.
- A topic appears in an imported title but never appears in the user's own words.

## Candidate Mapping

- Requests for explanation, confusion, "what is X" -> `concept_status` with `unknown` or `learning`.
- "I understand X" -> `concept_status` with `known`.
- "I can explain/apply X" -> `concept_status` with `mastered`.
- "Explain from first principles", "公式推导", "例子", "物理直觉" -> `learning_preference`.
- Repeated research topics such as quantum walks, QML, photonics, agents -> `research_interest`.
- Durable workflow statements -> `workflow_preference` or `project_rule`.
- Output style preferences -> `writing_style`.

## Reader-Learner Handoff Contract

Every `concept_status` candidate must become a strict reader-feedback item:

- `concept`: short stable label, not a sentence or full selected text.
- `concept_id`: slug derived from the concept.
- `concept_type`: one of the `reader-learner` valid concept types, usually `term`.
- `status`: one of `mastered`, `known`, `learning`, `unknown`, `unrated`.
- `annotation_kind`: `concept`.
- `source_anchor`: the evidence `chat-evt-*` id.
- `block_id` and `bilingual_block_id`: the same event id unless a more specific turn anchor exists.
- `source_excerpt` and `original_context`: bounded evidence text.

If these fields are missing, do not apply the patch.

## Sensitive Data

Skip files whose path or name contains:

`.env`, `secret`, `secrets`, `credential`, `credentials`, `token`, `password`, `passwd`, `apikey`, `api_key`, `private_key`, `id_rsa`, `.pem`, `.p12`, `.pfx`, `cookie`, `session`.

Also skip individual events containing obvious credential values such as `sk-...`, `Bearer ...`, `api_key=...`, or `password=...`.

Do not print skipped file contents.
