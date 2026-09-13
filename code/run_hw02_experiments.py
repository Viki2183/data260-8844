"""Run DATA 260 Homework 2 graph experiments."""

import csv
import io
import json
import sys
import time
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Add the repository root so project modules can be imported.
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from code.hw2_graph import run_graph


CASES_DIR = REPOSITORY_ROOT / "reports" / "hw02" / "cases"
RAW_DIR = REPOSITORY_ROOT / "reports" / "hw02" / "raw"
RUN_LOG_PATH = REPOSITORY_ROOT / "reports" / "hw02" / "RUN_LOG.txt"


def utc_timestamp() -> str:
    """Return the current UTC time in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def load_schema_input() -> dict[str, Any]:
    """Load the frozen input used by the experiments."""
    input_path = CASES_DIR / "schema_input.json"

    with input_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def classify_result(result: dict[str, Any]) -> str:
    """Classify a run according to completion and retry behavior."""
    if not result.get("completed", False):
        return "Hit turn ceiling"

    turn_count = int(result.get("turn_count", 0))

    if turn_count <= 3:
        return "Valid first attempt"

    if turn_count <= 5:
        return "Valid after 1 retry"

    return "Valid after 2+ retries"


def run_one(
    input_data: dict[str, Any],
    max_turns: int,
    run_number: int,
    experiment_name: str,
) -> dict[str, Any]:
    """Run one graph execution and save its real console output."""
    started_at = utc_timestamp()
    started_clock = time.perf_counter()

    captured_output = io.StringIO()

    try:
        with redirect_stdout(captured_output):
            result = run_graph(
                title=input_data["title"],
                content=input_data["content"],
                email=input_data["email"],
                model=input_data.get("model", "qwen3:8b"),
                temperature=float(input_data.get("temperature", 0.0)),
                max_turns=max_turns,
                strict=bool(input_data.get("strict", True)),
            )

        status = "pass" if result.get("completed", False) else "ceiling"

    except Exception as error:
        result = {
            "completed": False,
            "error": str(error),
            "turn_count": 0,
        }
        status = "error"

    elapsed_ms = (time.perf_counter() - started_clock) * 1000
    classification = classify_result(result)

    record = {
        "experiment": experiment_name,
        "run_number": run_number,
        "started_at": started_at,
        "elapsed_ms": round(elapsed_ms, 2),
        "status": status,
        "classification": classification,
        "max_turns": max_turns,
        "result": result,
        "console_output": captured_output.getvalue(),
    }

    with RUN_LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(
            f"\n===== {experiment_name} RUN {run_number} =====\n"
        )
        log_file.write(f"Started: {started_at}\n")
        log_file.write(f"Status: {status}\n")
        log_file.write(f"Classification: {classification}\n")
        log_file.write(f"Elapsed ms: {elapsed_ms:.2f}\n")
        log_file.write(captured_output.getvalue())
        log_file.write(json.dumps(result, indent=2))
        log_file.write("\n")

    print(
        f"{experiment_name} run {run_number}: "
        f"{classification}, {elapsed_ms:.0f} ms"
    )

    return record


def write_json(path: Path, data: Any) -> None:
    """Write formatted JSON to a file."""
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def write_summary_csv(path: Path, records: list[dict[str, Any]]) -> None:
    """Write machine-readable experiment results."""
    columns = [
        "experiment",
        "run_number",
        "started_at",
        "elapsed_ms",
        "status",
        "classification",
        "max_turns",
    ]

    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()

        for record in records:
            writer.writerow(
                {
                    column: record.get(column, "")
                    for column in columns
                }
            )


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculate objective counts and latency measurements."""
    classifications = {}

    for record in records:
        label = record["classification"]
        classifications[label] = classifications.get(label, 0) + 1

    completed_records = [
        record
        for record in records
        if record["status"] == "pass"
    ]

    mean_latency = (
        sum(record["elapsed_ms"] for record in records)
        / len(records)
        if records
        else 0
    )

    completion_rate = (
        len(completed_records) / len(records)
        if records
        else 0
    )

    return {
        "run_count": len(records),
        "completion_count": len(completed_records),
        "completion_rate": round(completion_rate, 4),
        "mean_latency_ms": round(mean_latency, 2),
        "classifications": classifications,
    }


def main() -> None:
    """Run all required HW2 experiments."""
    CASES_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    input_data = load_schema_input()

    with RUN_LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(
            f"\n\n===== EXPERIMENT SESSION {utc_timestamp()} =====\n"
        )

    all_records = []
    summaries = {}

    # Required schema-validation experiment: 30 runs.
    schema_records = [
        run_one(
            input_data=input_data,
            max_turns=10,
            run_number=run_number,
            experiment_name="schema_validation",
        )
        for run_number in range(1, 31)
    ]

    all_records.extend(schema_records)
    summaries["schema_validation"] = summarize(schema_records)

    write_json(
        RAW_DIR / "schema_validation_results.json",
        schema_records,
    )

    write_summary_csv(
        RAW_DIR / "schema_validation_results.csv",
        schema_records,
    )

    # Required ceiling comparison: 20 runs at each ceiling.
    ceiling_records = []

    for ceiling in (2, 10):
        experiment_name = f"ceiling_{ceiling}"

        records = [
            run_one(
                input_data=input_data,
                max_turns=ceiling,
                run_number=run_number,
                experiment_name=experiment_name,
            )
            for run_number in range(1, 21)
        ]

        ceiling_records.extend(records)
        summaries[experiment_name] = summarize(records)

    all_records.extend(ceiling_records)

    write_json(
        RAW_DIR / "ceiling_comparison_results.json",
        ceiling_records,
    )

    write_summary_csv(
        RAW_DIR / "ceiling_comparison_results.csv",
        ceiling_records,
    )

    # Required adversarial input and five runs.
    adversarial_input = {
        **input_data,
        "title": "???",
        "content": (
            "%%%% ??? 12345 !!! "
            "No meaningful package or vulnerability information."
        ),
    }

    write_json(
        CASES_DIR / "adversarial_input.json",
        adversarial_input,
    )

    adversarial_records = [
        run_one(
            input_data=adversarial_input,
            max_turns=10,
            run_number=run_number,
            experiment_name="adversarial",
        )
        for run_number in range(1, 6)
    ]

    all_records.extend(adversarial_records)
    summaries["adversarial"] = summarize(adversarial_records)

    write_json(
        RAW_DIR / "adversarial_results.json",
        adversarial_records,
    )

    write_summary_csv(
        RAW_DIR / "all_experiment_results.csv",
        all_records,
    )

    write_json(
        RAW_DIR / "experiment_summary.json",
        summaries,
    )

    print("\n===== EXPERIMENT SUMMARY =====")
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()