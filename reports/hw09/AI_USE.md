# DATA260 Homework 9 AI Use Disclosure

- Student: Vrishin KunnathamParambath
- SID4: 8844
- Repository: https://github.com/Viki2183/data260-8844
- Submission tag: `hw9`

## Tools and models

OpenAI Codex using a GPT-5 model assisted with repository inspection, scoped
implementation work, tests, evidence organization, report drafting, and PDF
preparation. The student selected the project scope, reviewed the source diffs,
ran or observed the verification commands, captured the terminal screenshots,
and approved the final submission artifacts.

The semantic cache uses local normalized embeddings from
`sentence-transformers/all-MiniLM-L6-v2`. Ollama `qwen3:8b` was installed,
loaded, and warmed during live verification. The preserved HW8 Kafka pipeline
and the Part 4 agent variants are deterministic and are not represented as
Ollama-generated answers.

## Verification boundary

Redis Stack, MySQL, Kafka, the authenticated endpoint, the view counter, vector
search, threshold sweep, and stale-answer invalidation were exercised against
local services. Part 4 results came from real deterministic executions. Offline
fakes were used only by unit tests and are identified separately from live
evidence. Ruff was unavailable and no Ruff pass is claimed.

No measurements, timestamps, screenshots, model behavior, or successful tests
were fabricated. The six terminal screenshots were captured manually with the
student name and SID4 visible; cropped copies remove only unused terminal space.
