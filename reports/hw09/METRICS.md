# DATA260 Homework 9 Metrics

- Student: Vrishin KunnathamParambath
- SID4: 8844
- Prefix: `s8844`
- Code semantic threshold: `0.85`
- Recommended deployment threshold: `0.95`

## Part 1 – View counter

- Accesses tested: 25
- Redis count reached: 25
- MySQL synchronization points: 10 and 20
- Test report: 5005
- Original database value restored: yes

## Part 2 – Authenticated semantic cache

| Request | Cache status | Similarity | Latency |
|---|---:|---:|---:|
| Cold first request | miss | 0.0 | 36,177.985 ms |
| Exact duplicate | hit | 1.0 | 24.930 ms |
| Paraphrase | hit | 0.93005 | 72.601 ms |
| Different query | miss | 0.489112 | 3,197.389 ms |

Warm ten-query experiment:

- Total queries: 10
- Cached: 6
- Non-cached: 4
- Hit rate: 60.0%
- Mean cached latency: 21.844 ms
- Mean non-cached latency: 3,075.926 ms
- Cold model/embedding initialization excluded: yes

## Part 3 – Threshold sweep

| Threshold | Hit rate | False-hit rate | Mean latency | Total cost |
|---:|---:|---:|---:|---:|
| 0.75 | 62.5% | 15.0% | 20.864 ms | 45 |
| 0.80 | 55.0% | 15.0% | 17.477 ms | 48 |
| 0.85 | 50.0% | 15.0% | 14.863 ms | 50 |
| 0.90 | 42.5% | 12.5% | 14.440 ms | 48 |
| 0.95 | 37.5% | 10.0% | 17.927 ms | 45 |

Cost model: `misses × 1 + false_hits × 5`.

## Part 4 – Agent variants

| Variant | Correct | Incorrect | Average attempts | Average latency |
|---|---:|---:|---:|---:|
| Baseline | 7 | 3 | 1.0 | 0.02010 ms |
| Evaluator Repair | 10 | 0 | 1.3 | 0.02296 ms |
| Lesson Memory | 8 | 2 | 1.0 | 0.75096 ms |
| Validated Improvement | 8 | 2 | 1.0 | 0.59373 ms |

These Part 4 timings measure deterministic local rules and JSON access, not
model generation.
