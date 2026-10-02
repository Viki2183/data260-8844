import json
import random
import time
from pathlib import Path


VERIFY_SEED = 268844
TOTAL_CALLS = 50
MAX_RETRIES = 2
BACKOFF_SECONDS = 0.005

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "reports" / "hw05" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)


def p99(values):
    ordered = sorted(values)
    index = max(0, int(len(ordered) * 0.99) - 1)
    return ordered[index]


def simulated_operation(rng, failure_rate):
    started = time.perf_counter()

    time.sleep(0.001)

    failed = rng.random() < failure_rate
    elapsed_ms = (time.perf_counter() - started) * 1000

    if failed:
        raise RuntimeError("injected storage failure")

    return elapsed_ms


def call_with_retry(rng, failure_rate):
    started_total = time.perf_counter()
    attempts = 0
    last_error = None

    for attempt in range(MAX_RETRIES + 1):
        attempts += 1

        try:
            simulated_operation(rng, failure_rate)

            total_latency_ms = (
                time.perf_counter() - started_total
            ) * 1000

            return {
                "ok": True,
                "attempts": attempts,
                "latency_ms": round(total_latency_ms, 3),
                "error": None,
            }

        except RuntimeError as exc:
            last_error = str(exc)

            if attempt < MAX_RETRIES:
                delay = BACKOFF_SECONDS * (2 ** attempt)
                time.sleep(delay)

    total_latency_ms = (
        time.perf_counter() - started_total
    ) * 1000

    return {
        "ok": False,
        "attempts": attempts,
        "latency_ms": round(total_latency_ms, 3),
        "error": last_error,
    }


def run_rate(rate):
    rng = random.Random(VERIFY_SEED + int(rate * 100))
    records = []

    for call_number in range(1, TOTAL_CALLS + 1):
        output = call_with_retry(rng, rate)

        records.append({
            "seed": VERIFY_SEED,
            "failure_rate": rate,
            "call_number": call_number,
            **output,
        })

    path = RAW_DIR / f"fault_injection_{int(rate * 100):02d}.jsonl"

    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record) + "\n")

    latencies = [record["latency_ms"] for record in records]
    successes = sum(record["ok"] for record in records)

    return {
        "failure_rate": rate,
        "calls": len(records),
        "successes": successes,
        "success_rate": round(successes / len(records), 4),
        "mean_latency_ms": round(sum(latencies) / len(latencies), 3),
        "p99_latency_ms": round(p99(latencies), 3),
        "raw_file": str(path),
    }


def retry_demos():
    print("Retry demonstrations")

    first_success = [True]
    retry_success = [False, True]
    all_fail = [False, False, False]

    for name, outcomes in [
        ("first_try_success", first_success),
        ("retry_success", retry_success),
        ("all_retries_fail", all_fail),
    ]:
        attempts = len(outcomes)
        succeeded = outcomes[-1]

        print({
            "demo": name,
            "attempts": attempts,
            "ok": succeeded,
        })


def main():
    retry_demos()

    metrics = [
        run_rate(0.0),
        run_rate(0.2),
        run_rate(0.5),
    ]

    metrics_path = RAW_DIR / "fault_injection_metrics.json"

    metrics_path.write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )

    print("\nFault-injection metrics")
    for row in metrics:
        print(json.dumps(row))

    print(f"\nSaved raw records to: {RAW_DIR}")


if __name__ == "__main__":
    main()