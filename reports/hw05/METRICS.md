# HW5 Fault-Injection Metrics

The experiment used VERIFY_SEED=268844, 50 calls per failure rate, three total rates, and a maximum of two retries after the initial attempt.

| Injected failure rate | Calls | Successes | Success rate | Mean latency (ms) | P99 latency (ms) |
|---:|---:|---:|---:|---:|---:|
| 0% | 50 | 50 | 100% | 1.602 | 2.007 |
| 20% | 50 | 50 | 100% | 1.587 | 1.733 |
| 50% | 50 | 44 | 88% | 1.433 | 1.993 |

The retry demonstrations verified three cases: first-attempt success, recovery after one failure, and failure after all allowed retries. The 20% injected-failure condition still achieved a 100% observed success rate because bounded retries recovered the transient failures. At 50%, retries improved availability but six calls still failed after the retry budget was exhausted.

This policy is appropriate for interactive use because it limits waiting time and prevents an unbounded retry loop. For batch processing, I would allow a larger retry budget, a longer timeout, and slower backoff because batch jobs can tolerate additional delay in exchange for higher eventual completion.