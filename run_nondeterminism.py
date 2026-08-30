import csv
import json
import re
import subprocess
import sys
import time
from pathlib import Path


INPUT_PATH = Path(
    "reports/hw01/cases/nondeterminism_input.json"
)

JSON_OUTPUT_PATH = Path(
    "reports/hw01/raw/nondeterminism_results.json"
)

CSV_OUTPUT_PATH = Path(
    "reports/hw01/raw/nondeterminism_results.csv"
)

RUN_LOG_PATH = Path(
    "reports/hw01/RUN_LOG.txt"
)

TEMPERATURES = [0.7, 0.0]
RUNS_PER_TEMPERATURE = 20


def load_existing_results() -> list[dict]:
    if not JSON_OUTPUT_PATH.exists():
        return []

    try:
        return json.loads(
            JSON_OUTPUT_PATH.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError):
        return []


def extract_finalized_output(output: str) -> dict:
    marker = "--- Finalized Output ---"

    if marker not in output:
        raise ValueError("Finalized Output marker was not found.")

    remaining = output.split(marker, 1)[1].lstrip()
    decoder = json.JSONDecoder()
    result, _ = decoder.raw_decode(remaining)

    return result


def extract_token_stats(output: str) -> dict:
    patterns = {
        "turn_count": r"Turns:\s*(\d+)",
        "input_tokens": r"Input tokens:\s*(\d+)",
        "output_tokens": r"Output tokens:\s*(\d+)",
        "total_tokens": r"Total tokens:\s*(\d+)",
    }

    stats = {}

    for key, pattern in patterns.items():
        match = re.search(pattern, output)
        stats[key] = int(match.group(1)) if match else 0

    return stats


def save_results(results: list[dict]) -> None:
    JSON_OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    JSON_OUTPUT_PATH.write_text(
        json.dumps(results, indent=2),
        encoding="utf-8",
    )

    fieldnames = [
        "temperature",
        "run",
        "tags",
        "summary",
        "latency_ms",
        "turn_count",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "timestamp",
    ]

    with CSV_OUTPUT_PATH.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for result in results:
            csv_result = result.copy()
            csv_result["tags"] = json.dumps(
                csv_result["tags"]
            )
            writer.writerow(csv_result)


def append_log(message: str) -> None:
    timestamp = time.strftime(
        "%Y-%m-%dT%H:%M:%SZ",
        time.gmtime(),
    )

    with RUN_LOG_PATH.open(
        "a",
        encoding="utf-8",
    ) as log_file:
        log_file.write(f"[{timestamp}] {message}\n")


def main() -> None:
    fixed_input = json.loads(
        INPUT_PATH.read_text(encoding="utf-8")
    )

    results = load_existing_results()

    completed = {
        (float(result["temperature"]), int(result["run"]))
        for result in results
    }

    append_log(
        "Started or resumed the nondeterminism experiment."
    )

    for temperature in TEMPERATURES:
        for run_number in range(
            1,
            RUNS_PER_TEMPERATURE + 1,
        ):
            key = (temperature, run_number)

            if key in completed:
                print(
                    f"Skipping completed run: "
                    f"temperature={temperature}, "
                    f"run={run_number}"
                )
                continue

            command = [
                sys.executable,
                "agents_demo.py",
                "--title",
                fixed_input["title"],
                "--content",
                fixed_input["content"],
                "--email",
                fixed_input["email"],
                "--model",
                "qwen3:8b",
                "--temperature",
                str(temperature),
                "--strict",
            ]

            print(
                f"\nStarting temperature={temperature}, "
                f"run={run_number}/{RUNS_PER_TEMPERATURE}"
            )

            append_log(
                f"Starting temperature={temperature}, "
                f"run={run_number}."
            )

            started = time.perf_counter()

            completed_process = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

            latency_ms = (
                time.perf_counter() - started
            ) * 1000

            if completed_process.returncode != 0:
                append_log(
                    f"FAILED temperature={temperature}, "
                    f"run={run_number}: "
                    f"{completed_process.stderr}"
                )

                print(completed_process.stderr)
                print(
                    "The experiment stopped. Fix the error "
                    "and run the script again to resume."
                )
                return

            finalized = extract_finalized_output(
                completed_process.stdout
            )

            token_stats = extract_token_stats(
                completed_process.stdout
            )

            result = {
                "temperature": temperature,
                "run": run_number,
                "tags": finalized["data"]["tags"],
                "summary": finalized["data"]["summary"],
                "latency_ms": round(latency_ms, 2),
                **token_stats,
                "timestamp": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ",
                    time.gmtime(),
                ),
            }

            results.append(result)
            save_results(results)

            append_log(
                f"Completed temperature={temperature}, "
                f"run={run_number}, "
                f"latency_ms={latency_ms:.2f}, "
                f"tags={result['tags']}."
            )

            print(json.dumps(result, indent=2))

    append_log(
        "Completed all 40 nondeterminism runs."
    )

    print(
        "\nAll 40 runs are complete. Results were saved to:"
    )
    print(JSON_OUTPUT_PATH)
    print(CSV_OUTPUT_PATH)


if __name__ == "__main__":
    main()