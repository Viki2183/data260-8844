# HW5 Fault-Injection Metrics

The experiment used VERIFY_SEED=268844 and 50 calls at each failure rate. Each call allowed one initial attempt plus two retries. The exponential backoff delays were 5 ms after the first failure and 10 ms after the second failure. Latency measures full wall-clock time, including failed attempts and backoff delays.

| Injected failure rate | Calls | Successes | Success rate | Mean latency | P99 latency |
|---:|---:|---:|---:|---:|---:|
| 0% | 50 | 50 | 100% | 1.521 ms | 1.690 ms |
| 20% | 50 | 50 | 100% | 2.937 ms | 9.515 ms |
| 50% | 50 | 44 | 88% | 8.911 ms | 20.911 ms |

The retry demonstrations covered first-attempt success, recovery after one failed attempt, and failure after all three allowed attempts.

The 20% experiment achieved a 100% success rate because the retry policy recovered the temporary failures. At 50%, retries improved reliability but six calls still failed after the retry budget was exhausted. The increased mean and P99 latency at higher failure rates reflects the added retry and backoff work.

For interactive use, the current policy is reasonable: two retries, 5 ms and 10 ms backoff delays, and bounded execution. For batch processing, I would use up to five retries, a longer operation timeout, a capped exponential backoff, and a larger total time budget because batch jobs can tolerate additional delay.