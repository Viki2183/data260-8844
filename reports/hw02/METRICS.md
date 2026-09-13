# DATA 260 Homework 2 Metrics

## Configuration

- Student: Vrishin Dharmesh Kunnatham Parambath
- SID4: 8844
- PORT_BASE: 8744
- SEED: 8844
- VERIFY_SEED: 268844
- DOMAIN: Open-source package vulnerabilities
- Model: qwen3:8b
- Temperature: 0.0
- Hardware: Windows 11 laptop with Docker Desktop
- Frozen input: `reports/hw02/cases/schema_input.json`

## Schema Validation Experiment

The frozen input was run through the graph 30 times using a maximum turn ceiling of 10.

| Outcome | Count |
|---|---:|
| Valid first attempt | 30 |
| Valid after 1 retry | 0 |
| Valid after 2 or more retries | 0 |
| Hit turn ceiling | 0 |

Completion rate: 30/30 = 100%

Mean latency: 178,399.88 ms

All 30 runs produced valid Planner output on the first attempt. No validation retries were required.

## Turn Ceiling Comparison

Each ceiling was tested 20 times using the same frozen input and model settings.

| Turn ceiling | Runs | Completed | Completion rate | Mean latency |
|---:|---:|---:|---:|---:|
| 2 | 20 | 0 | 0% | 71,869.60 ms |
| 10 | 20 | 20 | 100% | 157,746.71 ms |

A ceiling of 2 was too small because the graph normally requires a Supervisor turn, a Planner turn, and a Reviewer turn before it can finish. All 20 runs reached the ceiling.

A ceiling of 10 completed all 20 runs successfully. Although the larger ceiling allows more execution time, it provides enough room for the Planner, Reviewer, and possible correction loops.

I selected a turn ceiling of 10 for deployment because it achieved a 100% completion rate in this experiment.

## Adversarial Experiment

The adversarial input was stored at:

`reports/hw02/cases/adversarial_input.json`

It was run five times with a maximum turn ceiling of 10.

| Outcome | Count |
|---|---:|
| Completed | 5 |
| Hit turn ceiling | 0 |

Completion rate: 5/5 = 100%

Observed ceiling rate: 0/5 = 0%

Mean latency: 134,891.41 ms

The adversarial input did not reach the turn ceiling in these five runs. The model and fallback validation logic still produced acceptable structured output. Because the observed ceiling rate was zero, the result is reported as measured rather than claiming that the adversarial case reliably causes failure.

## Reproducibility

The raw results are stored under:

- `reports/hw02/raw/schema_validation_results.json`
- `reports/hw02/raw/schema_validation_results.csv`
- `reports/hw02/raw/ceiling_comparison_results.json`
- `reports/hw02/raw/ceiling_comparison_results.csv`
- `reports/hw02/raw/adversarial_results.json`
- `reports/hw02/raw/all_experiment_results.csv`
- `reports/hw02/raw/experiment_summary.json`

The complete console output and timestamps are stored in:

`reports/hw02/RUN_LOG.txt`