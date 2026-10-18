# DATA260 Homework 6

## Project metadata

- Student: Vrishin KunnathamParambath
- SID4: 8844
- Repository: https://github.com/Viki2183/data260-8844
- Branch: `hw6-development`
- PORT_BASE: 8744
- PREFIX: `s8844`
- DOMAIN_ID: 4
- SEED: 8844
- VERIFY_SEED: 268844
- Model: Ollama `qwen3:8b`
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`
- Hardware: Intel Core i7-10750H CPU, approximately 16 GB RAM

## Purpose and relationship to HW1–HW5

HW6 extends the existing DATA260 application. The FastAPI application,
MySQL-backed vulnerability-reporting behavior, frontend, MCP components, and
historical HW1–HW5 evidence remain the foundation. MySQL remains responsible
for the existing relational application; MongoDB adds the HW6 document and
memory features without replacing the prior database design.

## Architecture

Part 1 adds a MongoDB `documents` collection behind separate PyMongo
configuration, repository, schema, validator, and FastAPI-router modules.
Part 2 adds `messages`, `summaries`, and `episodes`. Recent messages provide
short-term context, session summaries compress older turns, lifetime summaries
retain durable cross-session information, and embedded episodic facts support
similarity retrieval. File memory is deliberately separate: it consolidates
`MEMORY.md` using the 40-line/24-hour policy, while MongoDB keeps raw
conversation evidence.

## Experiments and evidence

The measured fourth policy is **summary replacement**: when the effective context
exceeds threshold 12, summary replacement removes older eligible messages from
the prompt and retains the session summary plus the newest messages. Raw MongoDB
messages remain preserved. The baseline is N=12; policy savings are prompt-token
savings only, latency is reported but not claimed to improve, and the replacement
count is unavailable because the response schema did not expose it. File memory
remains a separate 40-line/24-hour consolidation system.

The Part 3 runner used the same 30-message conversation for N=4, N=12, and
N=30: 25 setup messages and five fixed probes. It completed 90 requests with no
automatic retries and recorded prompt tokens, latency, component-token
estimates, quality scores, and hypothetical cost projections.

### Fourth measured policy comparison

A separate live run measured the summary-replacement policy with
`short_term_n=30` and threshold `12`. It used a new user/session and sent 30
additional requests without retries; it was not merged into the original
90-record JSONL. All 30 requests succeeded. The mean prompt tokens were
1189.333, mean completion tokens 178.367, mean total tokens 1367.7, mean model
latency 60020.074 ms, mean estimated component prompt 1300.2, and automated
probe quality 4.2/5. The policy cost was $624.3504 using the existing
hypothetical cost formula, giving 136.434 measured prompt-token savings versus
the N=12 baseline and quality change 0.0.

The policy was active because the effective memory window was bounded at 13
messages from turn 7 onward, and the current user message appeared exactly
once on every turn. Exact internal replacement counts were unavailable because
the response schema did not expose that metadata; no replacement count is
invented. The separate policy evidence is authoritative for this comparison,
while the original 90-turn evidence remains unchanged.

Phase 1 corrected the derived cost calculation without changing the raw JSONL.
The formula uses hypothetical rates of $1 per 1,000,000 input tokens and $5 per
1,000,000 output tokens. N=12 is the named measured-prompt baseline. Corrected
totals are $504.4194 for N=4, $656.7306 for N=12, and $585.3405 for N=30.
Under the quality threshold of 4.0, N=4 is best and N=12 is worst by corrected
total cost. Component-token and raw-history estimates remain separate from
measured Ollama prompt tokens.

Measured model prompt tokens are `response_body.usage.prompt_tokens`, mirrored
to the top-level `prompt_tokens` field and obtained from model usage metadata.
Estimated component tokens use deterministic `ceil(words × 1.3)` estimates for
the prompt sections. The raw-history token estimate is a derived comparison
baseline from prior conversation text, not a model usage value.

| Window | Measured prompt mean | Estimated component mean | Mean short-term messages | Maximum retained |
|---:|---:|---:|---:|---:|
| N=4 | 827.733 | 595.767 | 3.867 | 4 |
| N=12 | 1325.767 | 1275.100 | 10.8 | 12 |
| N=30 | 967.800 | 2559.967 | 22.5 | 30 |

N=30 retained more short-term messages than N=12 and had the larger estimated
short-term component, but measured Ollama prompt means were non-monotonic. The
N=30 evidence contains 30 records, measured prompt tokens from 90 to 1898, and
final ten values all 1026. Estimated component totals exceeded `num_ctx=2048`
from turn 11 onward, with mean 2559.967. Context trimming is highly likely, but
the raw evidence has no explicit truncation flag, so truncation is not proven
directly. N=30 did not reliably represent a full 30-message prompt after turn
10; its quality, latency, prompt-token, and cost comparisons are therefore
limited. The summary-replacement policy also uses a capped effective window,
so comparisons involving N=30 must be interpreted with this limitation.

The values -105, -496, and -2824 are estimated component-minus-raw-history
values, not measured cost savings.

Important evidence includes `RUN_LOG.txt`, `METRICS.md`, `AI_USE.md`,
`memory_probes.yaml`, `verification.json`, the raw CRUD/chat/command/lifetime
artifacts, the Part 3 JSONL and aggregate files, and the screenshots directory.
The stale command artifact and recorder-level unavailable chat artifact are
preserved and explicitly distinguished from authoritative later evidence.

The current command policy is authoritative: `/memory` reports MongoDB and
file-memory metadata, `/compact` consolidates `MEMORY.md` while preserving raw
messages, `/dream` persistently adds verified non-sensitive facts after
deduplication, and `/help` explains all commands. The older preview-only
response text remains only in historical raw evidence and was not rewritten.

The legacy 75-line file-memory artifacts are preserved as backups. The required
offline fixture has exactly 55 physical lines, three duplicate groups, and
three contradiction pairs. Its consolidated artifact has 21 non-empty,
non-comment lines and records kept, superseded, reason, and missed-detection
fields for every contradiction. The current conversation screenshot shows the
student identity and ten USER/ASSISTANT messages without a SyntaxError. The
verified CRUD screenshot set documents POST create (HTTP 201), GET one
document (HTTP 200), PUT update (HTTP 200), invalid validation (HTTP 422), and
DELETE of the temporary document (HTTP 204 with an empty body):
`15_crud_create_201.png`, `16_crud_get_200.png`, `17_crud_update_200.png`,
`18_crud_invalid_422.png`, and `19_crud_delete_204.png`.

An earlier historical compact test recorded MongoDB messages 50 -> 50, while
the session-summary sequence reached 6 and the lifetime-summary count reached
1. It is not the authoritative final count table below. The offline
generated-function check
returned passed=true with deterministic output, duplicate removal, contradiction
detection, and both threshold checks true. The three-pair fixture audit recorded
all three contradictions with zero misses. Both files and MongoDB persist by
design across process restart, unlike in-memory state; this was not a dedicated
restart benchmark. The file 40-line trigger bounds file growth and MongoDB
indexes support query scalability, but no many-session scalability benchmark
was recorded.

The authoritative artifact `compact_counts_live_success.json` supersedes the
earlier incomplete compact records for before/after counts. It records one
properly encoded HTTP 200 `/compact` request for `hw6-session-4`, elapsed time
153434.637 ms, no retry, no normal chat request, and preserved raw messages.

| Metric | Before | After |
|---|---:|---:|
| MongoDB messages | 18 | 18 |
| MongoDB summaries | 10 | 11 |
| MongoDB episodes | 35 | 38 |
| File physical lines | 43 | 43 |
| File non-comment lines | 20 | 20 |
| File facts | 28 | 29 |

The separate successful compact artifact records HTTP 200, elapsed time
130973.166 ms, and the exact answer “Older messages were compacted into a
session summary and durable facts; raw messages were preserved.” It records the
memory metadata fields `short_term_count`, `short_term_messages`,
`session_summary`, `lifetime_summary`, `episodic_facts`, and `file_memory`, but
does not invent their unrecorded values. The earlier malformed-body HTTP 422
attempt remains a separate failed artifact. The newer
`compact_counts_live_success.json` is authoritative for complete counts and
records `facts_added=3`, `summary_created=true`,
`lifetime_summary_created=false`, and `raw_messages_preserved=true`. Neither
the failed 422 artifact nor the earlier incomplete artifacts was deleted or
overwritten.

The authoritative 18 -> 18 message count is scoped to `hw6-session-4`, not the
whole user or database. The older 50-message verifier count and larger
screenshot totals are historical/global snapshots. `facts_added=3` means three
MongoDB episodic facts; file memory separately increased from 28 to 29 facts,
while physical and non-comment line counts remained 43 and 20. The earlier
48/25 MEMORY.md values were pre-compaction; 43/20 are the current post-compaction
values for the authoritative run.

## Useful commands

Run FastAPI from the repository root in HW6 testing mode:

```powershell
$env:HW6_SKIP_MYSQL_INIT='1'
$env:HF_HOME='C:\Projects\data260-8844\.hw6-hf-cache'
$env:HF_HUB_CACHE='C:\Projects\data260-8844\.hw6-hf-cache\hub'
$env:SENTENCE_TRANSFORMERS_HOME='C:\Projects\data260-8844\.hw6-hf-cache\sentence-transformers'
$env:HW6_FILE_MEMORY_PATH='C:\Projects\data260-8844\MEMORY.md'
C:\Projects\data260-8844\.venv-hw6\Scripts\python.exe -m uvicorn code.web_application.main:app --app-dir C:\Projects\data260-8844 --host 127.0.0.1 --port 8744
```

Run the read-only verifier:

```powershell
$env:HW6_API_BASE_URL='http://127.0.0.1:8744'
$env:HW6_MONGODB_URI='mongodb://127.0.0.1:27017'
C:\Projects\data260-8844\.venv-hw6\Scripts\python.exe code\verify_hw06.py
```

## Remaining packaging steps

The current verifier snapshot recorded PASS=53, FAIL=0, and WARNING=0 for its
checks. Its database counts are historical rather than a current live query.
Screenshots exist under `reports/hw06/screenshots/`; readability still requires
manual review. Final Git commit/tag/push and collaborator-access confirmation
were not performed in this phase.
