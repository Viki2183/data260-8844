# DATA260 HW6 Metrics

Student: Vrishin KunnathamParambath
SID4: 8844
Model: `qwen3:8b`
Embedding model: `sentence-transformers/all-MiniLM-L6-v2`
Hardware: Intel Core i7-10750H CPU, approximately 16 GB RAM

These are measured local results unless a row is explicitly labeled as a
hypothetical estimate. Missing recorder values remain unavailable.

## Part 3: same conversation, three short-term windows

### Actual memory policy

The measured fourth policy is **summary replacement**: with `short_term_n=30`
and threshold 12, older eligible messages are replaced by the session summary
once the threshold is exceeded. Recent context is bounded, raw MongoDB
messages remain preserved, and measured savings are compared against N=12 only;
latency is reported but not claimed to improve. File memory remains a separate
40-line/24-hour consolidation system.

The runner sent the same 30-message conversation for N=4, N=12, and N=30:
25 setup messages followed by five fixed probe questions. The run completed 90
successful requests, with no automatic retries.

A fourth, separate live comparison used the summary-replacement policy with
`short_term_n=30` and threshold `12`. It sent 30 additional requests in a new
user/session and did not alter the original 90-turn JSONL. The policy run also
completed 30/30 requests successfully.

| Window | Requests | Mean measured prompt tokens | Mean completion tokens | Mean model latency | Mean quality |
|---:|---:|---:|---:|---:|---:|
| N=4 | 30/30 | 827.733 | 170.733 | 42393.933 ms | 4.2 |
| N=12 | 30/30 | 1325.767 | 172.667 | 54340.642 ms | 4.2 |
| N=30 | 30/30 | 967.8 | 196.667 | 66549.364 ms | 4.0 |

| Summary replacement policy | 30/30 | 1189.333 | 178.367 | 60020.074 ms | 4.2 |

The summary-replacement policy was active because the effective memory window
was bounded at 13 messages from turn 7 onward. The current user message
appeared exactly once on every turn. Exact internal replacement counts are
unavailable because the response schema did not expose that metadata; they are
not inferred here.

Five probes were scored per setting using an automated 1–5 keyword rubric:
N=4 scored 4.2, N=12 scored 4.2, and N=30 scored 4.0. The small difference
limits strong conclusions about answer quality, so the best-setting decision
uses the stated threshold plus measured cost.

Quality used an automated 1–5 keyword rubric, not human ratings. The separate
estimated component-minus-raw-history values are preserved honestly; they are
not measured cost savings. The baseline and component prompt estimate are
different measurement definitions.

## Component-token estimates

### Token measurement definitions and reconciliation

Measured model prompt tokens are `response_body.usage.prompt_tokens`, mirrored to the top-level `prompt_tokens` field and obtained from Ollama usage metadata. Estimated component tokens use deterministic `ceil(words × 1.3)` estimates for the primer, summaries, episodic facts, short-term messages, and current message; they are not Ollama counts. The N=30 evidence contains 30 records, a maximum measured prompt value of 1898, and final ten values all 1026. Estimated component totals exceeded the configured `num_ctx=2048` from turn 11 onward; their mean was 2559.967. Context trimming is highly likely, but the raw evidence has no explicit truncation flag, so truncation is not proven directly. The raw-history token estimate is a derived comparison baseline from prior conversation text; it is not a model usage value.

| Window | Measured prompt mean | Estimated component mean | Mean short-term messages | Maximum retained messages |
|---:|---:|---:|---:|---:|
| N=4 | 827.733 | 595.767 | 3.867 | 4 |
| N=12 | 1325.767 | 1275.100 | 10.8 | 12 |
| N=30 | 967.800 | 2559.967 | 22.5 | 30 |

N=30 did not reliably represent a full 30-message prompt after turn 10. Its quality, latency, prompt-token, and cost comparisons are limited by likely context trimming. The summary-replacement policy also uses a capped effective window, so comparisons involving N=30 must be interpreted with this limitation. The evidence does not prove the exact internal truncation mechanism.

These deterministic estimates come from prompt sections, not the exact Ollama
tokenizer.

| Window | Primer | Session summary | Lifetime summary | Short-term window | Episodic facts | Current user message |
|---:|---:|---:|---:|---:|---:|---:|
| N=4 | 28.0 | 112.5 | 86.0 | 305.033 | 50.9 | 13.333 |
| N=12 | 28.0 | 135.0 | 78.0 | 969.867 | 50.9 | 13.333 |
| N=30 | 28.0 | 139.333 | 83.5 | 2244.9 | 50.9 | 13.333 |

The summary-replacement run had a mean estimated component prompt of 1300.2.
Its measured prompt mean was 1189.333; this remains separate from the
deterministic component estimate.

The current user message is counted once, separately from recent history.

## Corrected baseline comparison

The named baseline is N=12, the existing default. The policy is bounded
per-request short-term window selection. The quality threshold is mean probe
quality >= 4.0. The best setting is the lowest corrected total cost among
settings meeting the threshold; ties use lower latency, then lower measured
prompt tokens. The worst setting is the highest corrected total cost among
settings meeting the threshold.

| Setting | Mean measured prompt tokens | Mean latency | Mean quality | Prompt savings vs N=12 | Prompt savings % | Cost savings vs N=12 | Quality change |
|---|---:|---:|---:|---:|---:|---:|---:|
| N=12 baseline policy | 1325.767 | 54340.642 ms | 4.2 | 0 | 0% | $0 | 0.0 |
| Policy N=4 | 827.733 | 42393.933 ms | 4.2 | 498.034 | 37.566% | $152.3112 | 0.0 |
| Policy N=30 | 967.8 | 66549.364 ms | 4.0 | 357.967 | 27.001% | $71.3901 | -0.2 |
| Summary replacement policy | 1189.333 | 60020.074 ms | 4.2 | 136.434 | 10.291% | $32.3802 | 0.0 |

Under this rule, N=4 is best and N=12 is worst because it has the highest
corrected total cost. N=30 is not labeled worst.

The summary-replacement policy cost is $624.3504 using the same hypothetical
formula below. Its measured prompt savings versus N=12 are 136.434 tokens, or
10.291%, and its quality change is 0.0. This fourth row is a separate measured
policy result, not a relabeling of the N=30 window. The reported policy latency
is a measurement, not an improvement claim. N=30 and the summary-replacement
policy are affected by the likely 2048-token context limit, so their savings and
comparisons are not clean measurements of a full 30-message context.

Measured prompt tokens come from model usage metadata. Estimated component
tokens are deterministic estimates of prompt sections. The raw-history
baseline is a separate runner estimate. These measurements answer different
questions; the evidence does not prove context truncation, double-counting, or
a short-term-window implementation bug.

These are estimated component-minus-raw-history comparison values. They are not
measured cost savings. Negative values mean the estimated component prompt
exceeded the selected raw-history baseline: -105 for N=4, -496 for N=12, and
-2824 for N=30.

## Hypothetical 10,000-conversation projection

```text
input_cost = mean_prompt_tokens_per_turn * 30 * 10000 / 1,000,000 * $1
output_cost = mean_completion_tokens_per_turn * 30 * 10000 / 1,000,000 * $5
total_cost = input_cost + output_cost
```

The rates are hypothetical estimates: $1 per 1,000,000 input tokens and $5
per 1,000,000 output tokens.

| Window | Hypothetical total |
|---:|---:|
| N=4 | $504.4194 |
| N=12 | $656.7306 |
| N=30 | $585.3405 |
| Summary replacement policy | $624.3504 |

These are hypothetical estimates, not Ollama charges. Local Ollama monetary
cost is effectively zero because inference is local, while CPU time, storage,
electricity, and operational attention remain real costs.

## Part 1 and Part 2 measurements

CRUD evidence covers 201, 200, 204, 400, 404, and 422. The retained document
remained present and the temporary delete-test document was removed through
HTTP.

The verified CRUD screenshots provide visual evidence for the principal status
cases: `15_crud_create_201.png` (POST create, HTTP 201),
`16_crud_get_200.png` (GET one document, HTTP 200),
`17_crud_update_200.png` (PUT update, HTTP 200),
`18_crud_invalid_422.png` (invalid request, HTTP 422), and
`19_crud_delete_204.png` (DELETE temporary document, HTTP 204 with an empty
body).

The verified final state recorded one document, 50 messages, seven summaries,
and 41 episodes. The seven summaries were six session summaries plus one
user-scoped lifetime summary.

Session-4 episodic retrieval returned the preferred topic “distributed
systems” and connected it to scalability, fault tolerance, and concurrency.
The fifth user message created a session summary. The lifetime sequence moved
from session summaries 5 to 6 and lifetime summaries 0 to 1.

The authoritative live command evidence recorded HTTP 200 for `/help`,
`/memory`, `/dream`, and `/compact`. The earlier stale-process artifact and
the historical preview-only response text are preserved as non-authoritative
raw evidence; the later live artifact and current source define behavior.

## Part 4 file-memory measurements

| Measurement | Result |
|---|---:|
| Preserved legacy fixture | 75 lines |
| Preserved legacy consolidated artifact | 72 lines total; 61 non-empty/non-comment |
| Required fixture | exactly 55 physical lines |
| Required consolidated artifact | 21 non-empty/non-comment lines |
| Required duplicate groups | 3 |
| Required contradictions detected | 3 |
| Earlier pre-compaction `MEMORY.md` physical lines | 48 |
| Earlier pre-compaction `MEMORY.md` non-empty/non-comment lines | 25 |
| `/dream` non-sensitive facts added | 3 |
| `/dream` duplicate facts skipped | 0 |
| Raw MongoDB messages preserved by `/compact` | Yes |
| Earlier historical `/compact` MongoDB messages | 50 -> 50 |
| Earlier historical session summaries | 5 -> 6 |
| Earlier historical lifetime summaries | 0 -> 1 |
| Earlier historical first lifetime summary | Yes |

The authoritative artifact `compact_counts_live_success.json` supersedes earlier
incomplete compact records for complete before/after counts. It records one
HTTP 200 `/compact` request for `hw6-session-4`, elapsed time 153434.637 ms,
no retry, no normal chat request, and raw-message preservation.

| Metric | Before | After |
|---|---:|---:|
| MongoDB messages | 18 | 18 |
| MongoDB summaries | 10 | 11 |
| MongoDB episodes | 35 | 38 |
| File physical lines | 43 | 43 |
| File non-comment lines | 20 | 20 |
| File facts | 28 | 29 |

The response also recorded `facts_added=3`, `summary_created=true`,
`lifetime_summary_created=false`, and `raw_messages_preserved=true`. The failed
422 artifact and earlier incomplete artifacts remain separate historical records
and were not deleted or overwritten.

The authoritative 18 -> 18 message count is scoped to `hw6-session-4` only;
it is not a whole-user or whole-database total. The earlier 50-message count
and larger screenshot totals are historical/global snapshots. Here,
`facts_added=3` means three MongoDB episodic facts. File memory changed
separately from 28 to 29 facts because one durable file fact was added to the
existing file content; its physical and non-comment line counts remained
43 and 20. The earlier 48/25 MEMORY.md values are a pre-compaction snapshot;
43/20 are the current post-compaction values for the authoritative run.

The file policy consolidates when the file exceeds 40 lines or is older than 24
hours. Duplicate facts are removed deterministically, contradictions remain in
`Needs review`, and file memory is compared with MongoDB memory rather than
silently merged. The current `/dream` behavior is intentionally persistent for
verified, non-sensitive facts: the live test added three facts and skipped zero
duplicates. Older preview-only wording in historical raw files was not
rewritten and is not authoritative. Generated-function verification reported
deterministic output, duplicate removal, contradiction detection, and both
threshold checks. Restart persistence, scalability across many sessions, and a
 dedicated forgetting test are unavailable in the recorded artifacts. The
 generated-function check was executed offline against the 55-line fixture and
 returned `passed=true`, `deterministic=true`, and true results for duplicate
 removal, contradiction detection, the line rule, and the age rule; it reported
 55 input lines, 15 output lines, 5 duplicate occurrences, and 1 contradiction
 detected by that helper. The separate three-pair fixture audit recorded all
 three planted contradiction pairs with zero missed contradictions. By design,
 both persisted files and MongoDB records survive process restart, while
 in-memory state does not; restart persistence was not separately measured.
 The file 40-line trigger bounds file-memory growth, and MongoDB indexes support
 query scalability, but no many-session scalability benchmark was recorded.
An earlier pre-compaction read-only snapshot showed 48 physical lines and 25
non-empty/non-comment lines. The authoritative compact run reports the current
post-compaction file state as 43 physical lines and 20 non-empty/non-comment
lines; those are the current values for this run.

## Limitations

- Quality scores are automated keyword scores, not human evaluations.
- Local Ollama has effectively zero direct API billing, but CPU time and storage are operational costs.
- Negative token savings are measured estimates, not errors.
- Recorder-level unavailable values remain unavailable.
- Screenshot dimensions were not independently verified for this report.
- Final Git commit/tag/push and collaborator-access confirmation were not
  performed in this documentation phase and require a later approved step.
