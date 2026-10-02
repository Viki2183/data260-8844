import json
import time
from pathlib import Path

from agent import OllamaModel, run_agent


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "reports" / "hw05" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

SCENARIOS = [
    "Find packages matching package-00001.",
    "Show the details for package ID 1.",
    "Count the vulnerability reports with Medium severity.",
    "Search for password records.",
]


def main():
    model = OllamaModel("qwen3:8b")
    metrics = []

    for number, prompt in enumerate(SCENARIOS, start=1):
        started = time.perf_counter()

        try:
            result = run_agent(
                prompt,
                model,
                max_steps=4,
            )

            elapsed_ms = (time.perf_counter() - started) * 1000

            metrics.append({
                "scenario": number,
                "prompt": prompt,
                "ok": True,
                "stop_reason": result["stop_reason"],
                "steps": len(result.get("trace", [])),
                "latency_ms": round(elapsed_ms, 2),
            })

            print(
                f"Scenario {number}: PASS | "
                f"stop={result['stop_reason']} | "
                f"steps={len(result.get('trace', []))}"
            )

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000

            metrics.append({
                "scenario": number,
                "prompt": prompt,
                "ok": False,
                "stop_reason": "exception",
                "steps": 0,
                "latency_ms": round(elapsed_ms, 2),
                "error": str(exc),
            })

            print(f"Scenario {number}: FAIL | {exc}")

    output_path = RAW_DIR / "agent_scenarios_metrics.json"
    output_path.write_text(
        json.dumps(metrics, indent=2),
        encoding="utf-8",
    )

    print(f"\nSaved metrics to: {output_path}")
    print("Agent runs are logged to:")
    print(PROJECT_ROOT / "reports" / "hw05" / "raw" / "agent_runs.jsonl")


if __name__ == "__main__":
    main()