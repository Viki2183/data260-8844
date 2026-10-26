# DATA260 HW7 AI Use Statement

Student: Vrishin KunnathamParambath | SID4: 8844

Repository: https://github.com/Viki2183/data260-8844  
Collaborator access for `Sbnikitha` and `supriyaselvanganesan`: not independently verified.  
Commit/tag hash: pending final packaging.

## (1) How AI assistance was used

Codex assisted with repository inspection, reading the official HW7 assignment,
reviewing and implementing HW7 authentication, agent, MRKL, prompt-security,
file-tool, migration, and bike-share changes, organizing raw evidence, and
preparing the report and PDFs. The student approved the scope, supplied the
repository and private credentials locally when needed, selected test data,
reviewed outputs, and retained responsibility for submission decisions.

## (2) What was independently reviewed or verified

The student reviewed the source changes, raw evidence, screenshots, offline
checks, JWT results, and local Ollama results. The latest Task B evidence shows
`aggregate -> search` success. The latest Task C evidence shows
`search -> detail -> detail` completed through bounded controller recovery after
an Ollama HTTP 500; it is not described as uninterrupted model success.

## (3) How a problem or limitation was detected

The original pay-per-use bike-share evidence reported $6,830 membership because
it used `included_minutes=0`. Comparing the pricing snapshot, UI calculation,
and raw JSON identified the correct 45 included minutes per ride and the
authoritative $4,780 membership value. The original evidence was preserved and
the corrected evidence was recorded separately.

The agent evidence also exposed premature finals, a detail argument mismatch,
and an Ollama HTTP 500 after Task C detail ID 1. These were recorded rather
than silently converted into normal model success.

## (4) What was changed and why the change works

The HW7 agent now normalizes tool envelopes, converts detail IDs to integers,
supports repeated detail sequences, records adapter failures, and performs one
bounded fixed-plan controller repair only when explicitly configured. The
controller executes the declared read-only handler and reports success only if
all required tools actually succeed. No model retry or hidden chain-of-thought
storage was added.

Measured failures were reported without alteration: the 20-attempt reliability
run recorded 0/20 successes. The current fixed A/B/C comparison rerun recorded
baseline 0/3 and Reflexion 0/3, with all current Reflexion runs stopping at
human_review after two retries. The earlier comparison remains preserved as
raw evidence and is not merged with the current rerun. Full pytest/verifier
execution remained blocked by the managed temporary-sandbox environment;
deterministic offline checks were used where appropriate.

No passwords, password hashes, JWT strings, tokens, or other secrets were
included in the report or evidence.
