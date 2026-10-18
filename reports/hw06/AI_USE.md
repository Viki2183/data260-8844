# DATA260 HW6 AI Use Statement

AI assistance was used during implementation, verification, evidence
organization, and documentation. The student remains responsible for
understanding and explaining the resulting design and code.

## What AI helped with, and what the student did

AI assistance helped with architecture planning, code scaffolding, validation
logic, offline and read-only test harnesses, report organization, and
explanatory comments. The student supplied the repository and homework
requirements, selected the DATA260 continuation path, provided configuration
and environment details, ran commands and local services, reviewed outputs,
and decided whether to continue after failures. The student remains
responsible for understanding and defending the implementation.

## An incorrect output or issue that was verified

Real issues were preserved and investigated rather than hidden:

- the initial HTTP 500 came from launching FastAPI where the repository-level `src` package was not importable;
- an early slash-command test used stale FastAPI PID 21012 and is explicitly non-authoritative;
- the default Hugging Face cache was not writable;
- the Part 3 aggregate initially used a mismatched current-message field name;
- `chat_turn_04.json` recorded the POST result as unavailable even though later server evidence verified completion.

## How the issues were detected

Detection used observed HTTP statuses and persisted MongoDB state, Uvicorn
process inspection, source inspection, read-only MongoDB queries, raw JSONL
hash comparison, and verifier failures. The Part 3 correction confirmed that
the raw JSONL remained unchanged while only the three derived aggregate files
were regenerated.

## What was changed

Observed corrections included launching Uvicorn from the repository root with
`--app-dir`, moving Hugging Face caches to a writable project-local directory,
adding HW6-only model timeout/reasoning/output controls, correcting verifier
field handling, correcting Part 3 aggregation to use
`current_user_message`, implementing file-memory consolidation and command
integration, and preserving stale and recorder-level evidence instead of
overwriting it.

Actual execution results were accepted only after local verification. Failed
tests, unavailable recorder values, slow CPU inference, and stale-process
evidence were retained honestly. No fabricated timestamps, token values,
latencies, counts, screenshots, or PDF claims were added.

Historical HW1–HW5 code, reports, screenshots, logs, notebooks, raw outputs,
and tags were preserved.
