# DATA260 HW8 AI Use Statement

Student: Vrishin KunnathamParambath | SID4: 8844

Repository: https://github.com/Viki2183/data260-8844  
Collaborators with repository access: `Sbnikitha` and `supriyaselvanganesan`  
HW8 tag: `hw8` at the final packaging commit

## (1) What I used AI for versus what I did myself

I used AI/Codex for repository inspection, assignment reading, HW8-only code
implementation support, offline test design, controlled local Kafka commands,
evidence organization, screenshot preparation, and report/PDF preparation. I
selected the test data and scope, approved live operations, reviewed source
changes, inspected the raw evidence, and made the final submission decisions
myself.

## (2) One incorrect output and one independent verification

The first hand-built PDF opened as a blank document. I independently verified
the generated PDF by opening it, checking that it rendered pages, checking the
`%PDF-` header, and searching its extracted text. I also independently checked
the live Docker logs, Kafka topic metadata, JSONL/CSV evidence, offline tests,
and the final verification output.

## (3) How I detected the problem

The blank viewer result did not match the expected report content. The PDF
render check exposed the problem before submission. Separately, comparing the
live poison writer log with the harness output showed that the later-valid
message check had to be run explicitly; the corrected live2 run records that
message reaching `s8844_drafts` with `blocked_by_poison=false`.

## (4) What I changed and why it works now

I replaced the unreliable hand-built PDF output with Chrome headless rendering,
then verified both HW8 PDFs. I added the isolated FastAPI service and
`homework_demo.py` live evidence, structured full-stage agent logs, the
post-DLT later-valid check, and normalized consumer-death evidence that records
the real Writer crash, Kafka redelivery, output, commit, and restart. The
verifier now validates the corrected live2 evidence paths and records the
configuration and packaging metadata. Historical before-fix runs were not
captured, so I did not invent them.

No hidden chain-of-thought is stored or reported. Evidence contains observable
requests, responses, topics, partitions, offsets, timestamps, process names,
outcomes, and safe bounded failure metadata only.
