# Extraction Rules

Extract conservatively from chat sessions.

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

## Candidate Mapping

- Requests for explanation, confusion, "what is X" -> `concept_status` with `unknown` or `learning`.
- "I understand X" -> `concept_status` with `known`.
- "I can explain/apply X" -> `concept_status` with `mastered`.
- "Explain from first principles", "公式推导", "例子", "物理直觉" -> `learning_preference`.
- Repeated research topics such as quantum walks, QML, photonics, agents -> `research_interest`.
- Durable workflow statements -> `workflow_preference` or `project_rule`.
- Output style preferences -> `writing_style`.

## Sensitive Data

Skip files whose path or name contains:

`.env`, `secret`, `secrets`, `credential`, `credentials`, `token`, `password`, `passwd`, `apikey`, `api_key`, `private_key`, `id_rsa`, `.pem`, `.p12`, `.pfx`, `cookie`, `session`.

Do not print skipped file contents.
