# DATA260 Homework 10 Metrics

- Student: Vrishin KunnathamParambath
- SID4: 8844
- Branch: `hw6-development`
- Domain: Open-source package vulnerabilities
- Trace identifier: existing `correlation_id` used directly as `trace_id`
- Judge model: local Ollama `qwen3:8b`
- Judge prompt: `hw10-geval-v1`
- Judge temperature: 0
- Judge seed: 8844

## Automated judge

| Metric | Result |
|---|---:|
| Frozen cases | 20 |
| Trials | 3 |
| Successful evaluations | 60/60 |
| MAD | 0.0 |
| Changed scores | 0 |
| Mean absolute change | 0.0 |
| Maximum absolute change | 0 |
| Repeatability | 100% |
| Spearman | null |
| Spearman status | undefined_constant_human_labels |

The same local qwen3:8b judge was run in 3 repeatability trials, with 20 cases per trial. This was 3 trials of one judge, not 3 different judges. Spearman is undefined because every human score is 1 and therefore the human rank vector is constant. MAD 0.0 and repeatability 100% do not establish judge reliability. The judge should not be trusted for deployment gating from this evidence.

## Human labels

- Cases: 20.
- Manual confirmation: completed before freezing and judge execution.
- Scores: 20/20 equal 1/5.
- Case provenance: all 20 are offline reconstructed Writer drafts.
- Direct live Writer cases among the 20: 0.
- Only one genuine raw Writer draft was available: `reports/hw08/raw/part2_agent_journey.jsonl`.
- No diverse v2 set was created because additional drafts would require fabrication or reconstruction.
- Separate live Writer observation: the Writer stage in `hw10-live-miss-e56b8558868c`.

## Part 2 live evaluation

- Live trace ID: `hw10-live-e2e-eval-fdc655292734`.
- Observed path: `cache_lookup → inbox → planner → tasks → writer → drafts → reviewer → final → evaluation`.
- Evidence: `raw/end_to_end/live_evaluation_trace.json`.
- Evaluation status: `completed_with_errors`.
- All four GEval criteria were attempted.
- Plan Quality: unavailable because Ollama/CUDA initialization failed.
- Writer Helpfulness: unavailable because the judge timed out.
- Final Answer Helpfulness: unavailable because the judge timed out.
- Final-vs-Draft Improvement: unavailable because the required scores were unavailable.
- Unavailable scores were not replaced with 0 or 1.
- The live pipeline trace succeeded through the evaluator stage, but judge execution did not complete successfully.

## Latency experiment

| Metric | Result |
|---|---:|
| Total requests | 50 |
| Confirmed cache misses | 50 |
| Accidental hits | 0 |
| Failed requests | 0 |
| Included requests | 50 |
| Excluded requests | 0 |
| Total p50 | 3109.722 ms |
| Total p95 | 3179.057 ms |
| Error rate | 0 failed requests / 50 total requests = 0% |

| Stage | p50 (ms) | p95 (ms) | % of cache-miss end-to-end |
|---|---:|---:|---:|
| Cache lookup | 30.663 | 66.376 | 0.986% |
| Planner | 4.000 | 6.550 | 0.129% |
| Writer | 3.000 | 8.100 | 0.096% |
| Reviewer | 3.000 | 6.550 | 0.096% |
| Queue wait (total) | 3061.381 | 3081.447 | 98.445% |
| Evaluation | unavailable | unavailable | unavailable |

Queue wait was the dominant observable contributor. Further profiling should begin with Kafka pipeline wait and worker scheduling, without assuming that the residual belongs to one worker.

## Methods

- Timestamp convention: UTC ISO-8601 `Z`.
- Duration source: `time.perf_counter_ns`.
- Percentile: linear interpolation on sorted values at index `(n-1) * p / 100`.
- Cache-miss end-to-end percentage: p50 stage latency divided by p50 total latency times 100.
- Cache lookup: HW9 embedding plus Redis-search timing.
- Planner/Writer/Reviewer: matching Kafka publication timestamp boundaries.
- Queue wait: `max(0, agent_latency - planner - writer - reviewer)`.
- Evaluation: not executed per request; unavailable.
- Evaluation p50/p95: unavailable; no evaluation latency values were fabricated.

Raw metrics: `raw/latency_50_cache_misses.jsonl`, `raw/latency_summary.json`, and `raw/judge_validation.json`.
