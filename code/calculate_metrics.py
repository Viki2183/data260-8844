import json
import math
from collections import Counter
from pathlib import Path


RESULTS_PATH = Path(
    "reports/hw01/raw/nondeterminism_results.json"
)

METRICS_JSON_PATH = Path(
    "reports/hw01/raw/nondeterminism_metrics.json"
)

METRICS_MD_PATH = Path(
    "reports/hw01/METRICS.md"
)


def percentile(values: list[float], percent: float) -> float:
    """Calculate a percentile using linear interpolation."""

    ordered = sorted(values)

    if not ordered:
        return 0.0

    position = (len(ordered) - 1) * percent
    lower = math.floor(position)
    upper = math.ceil(position)

    if lower == upper:
        return ordered[lower]

    fraction = position - lower

    return (
        ordered[lower]
        + (ordered[upper] - ordered[lower]) * fraction
    )


def normalize_tag(tag: str) -> str:
    return " ".join(tag.lower().strip().split())


def calculate_for_temperature(
    results: list[dict],
    temperature: float,
) -> dict:
    selected = [
        result
        for result in results
        if float(result["temperature"]) == temperature
    ]

    if len(selected) != 20:
        raise ValueError(
            f"Expected 20 runs for temperature {temperature}, "
            f"but found {len(selected)}."
        )

    tag_sets = [
        tuple(sorted(
            normalize_tag(tag)
            for tag in result["tags"]
        ))
        for result in selected
    ]

    distinct_tag_sets = len(set(tag_sets))

    tags_by_run = [
        set(normalize_tag(tag) for tag in result["tags"])
        for result in selected
    ]

    common_tags = set.intersection(*tags_by_run)

    tag_run_counts = Counter()

    for run_tags in tags_by_run:
        tag_run_counts.update(run_tags)

    one_run_tags = sorted(
        tag
        for tag, count in tag_run_counts.items()
        if count == 1
    )

    latencies = [
        float(result["latency_ms"])
        for result in selected
    ]

    return {
        "temperature": temperature,
        "run_count": len(selected),
        "distinct_tag_sets": distinct_tag_sets,
        "tags_in_all_20_runs": sorted(common_tags),
        "tags_in_exactly_one_run": one_run_tags,
        "latency_p50_ms": round(
            percentile(latencies, 0.50),
            2,
        ),
        "latency_p95_ms": round(
            percentile(latencies, 0.95),
            2,
        ),
        "latency_p99_ms": round(
            percentile(latencies, 0.99),
            2,
        ),
    }


def display_list(values: list[str]) -> str:
    return ", ".join(values) if values else "None"


def main() -> None:
    results = json.loads(
        RESULTS_PATH.read_text(encoding="utf-8")
    )

    if len(results) != 40:
        raise ValueError(
            f"Expected 40 total runs, found {len(results)}."
        )

    metrics_07 = calculate_for_temperature(results, 0.7)
    metrics_00 = calculate_for_temperature(results, 0.0)

    complete_metrics = {
        "input_file": str(RESULTS_PATH),
        "total_runs": len(results),
        "temperature_0.7": metrics_07,
        "temperature_0.0": metrics_00,
    }

    METRICS_JSON_PATH.write_text(
        json.dumps(complete_metrics, indent=2),
        encoding="utf-8",
    )

    markdown = f"""# DATA 260 HW1 Metrics

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
| Distinct tag sets | {metrics_07["distinct_tag_sets"]} | {metrics_00["distinct_tag_sets"]} |
| Tags in all 20 runs | {display_list(metrics_07["tags_in_all_20_runs"])} | {display_list(metrics_00["tags_in_all_20_runs"])} |
| Tags in exactly one run | {display_list(metrics_07["tags_in_exactly_one_run"])} | {display_list(metrics_00["tags_in_exactly_one_run"])} |

## Latency

| Metric | Temperature 0.7 | Temperature 0.0 |
|---|---:|---:|
| Latency p50 (ms) | {metrics_07["latency_p50_ms"]} | {metrics_00["latency_p50_ms"]} |
| Latency p95 (ms) | {metrics_07["latency_p95_ms"]} | {metrics_00["latency_p95_ms"]} |
| Latency p99 (ms) | {metrics_07["latency_p99_ms"]} | {metrics_00["latency_p99_ms"]} |

## Interpretation

The higher-temperature results show how much output variation two users can receive from identical input. The temperature 0.0 results show the pipeline's behavior under more deterministic generation.

Variation is acceptable when suggesting optional discovery tags because several relevant phrasings can help users find the same content. Variation is not acceptable when assigning a security severity or vulnerability identifier because inconsistent values could cause incorrect prioritization or tracking.
"""

    METRICS_MD_PATH.write_text(
        markdown,
        encoding="utf-8",
    )

    print(json.dumps(complete_metrics, indent=2))
    print(f"\nCreated {METRICS_JSON_PATH}")
    print(f"Created {METRICS_MD_PATH}")


if __name__ == "__main__":
    main()