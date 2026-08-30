# DATA 260 HW1 Metrics

## Experiment Configuration

- Model: qwen3:8b
- Fixed runs at temperature 0.7: 20
- Fixed runs at temperature 0.0: 20
- Total runs: 40
- Raw JSON: `reports/hw01/raw/nondeterminism_results.json`
- Raw CSV: `reports/hw01/raw/nondeterminism_results.csv`

## Tag Variation

| Metric | Temperature 0.7 | Temperature 0.0 |
|---|---:|---:|
| Distinct tag sets | 7 | 3 |
| Tags in all 20 runs | critical authentication bypass | critical authentication bypass |
| Tags in exactly one run | authentication bypass requests package | unauthorized access |

## Latency

| Metric | Temperature 0.7 | Temperature 0.0 |
|---|---:|---:|
| Latency p50 (ms) | 955924.94 | 599091.85 |
| Latency p95 (ms) | 1224709.49 | 1005474.73 |
| Latency p99 (ms) | 1418972.12 | 1047240.56 |

## Interpretation

The higher-temperature results show how much output variation two users can receive from identical input. The temperature 0.0 results show the pipeline's behavior under more deterministic generation.

Variation is acceptable when suggesting optional discovery tags because several relevant phrasings can help users find the same content. Variation is not acceptable when assigning a security severity or vulnerability identifier because inconsistent values could cause incorrect prioritization or tracking.
