"""Run the reproducible HW6 short-term-memory comparison through HTTP.

This module deliberately knows only about the public FastAPI endpoint.  It does
not import the application, connect to MongoDB, call Ollama directly, or load an
embedding model.  The runner is therefore easy to inspect before an experiment
is started and cannot bypass the API's normal memory lifecycle.
"""

from __future__ import annotations

import csv
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# These are the three comparison labels required by the HW6 experiment.  The
# separate sessions keep one window's conversation from leaking into another.
SHORT_TERM_WINDOWS = (4, 12, 30)
USER_ID_PREFIX = "hw6-experiment-8844"
MODEL_NAME = "qwen3:8b"
SEED = 8844
VERIFY_SEED = 268844

# These are hypothetical documentation rates, not Ollama billing rates.  They
# make the report reproducible without implying that local inference incurred a
# real hosted-model charge.
INPUT_RATE_PER_1K = 0.001
OUTPUT_RATE_PER_1K = 0.002

OUTPUT_DIRECTORY = (
    Path(__file__).resolve().parents[1] / "reports" / "hw06" / "raw"
)
CSV_OUTPUT = OUTPUT_DIRECTORY / "short_term_comparison.csv"
JSONL_OUTPUT = OUTPUT_DIRECTORY / "short_term_comparison.jsonl"

PREFERENCE = "distributed systems"
SETUP_MESSAGES = (
    "My preferred study topic for this DATA 260 project is distributed systems.",
    "Please remember that preference while helping me with this graduate-course project.",
)
FOLLOW_UP_MESSAGE = "Which study topic did I say I preferred?"


@dataclass
class ProbeResult:
    """One window's bounded three-request experiment result."""

    probe_id: str
    short_term_n: int
    user_id: str
    session_id: str
    turn_number: int
    seed: int
    verify_seed: int
    model: str
    request_messages: list[str]
    follow_up_message: str
    http_status: int | None
    error: str | None
    elapsed_ms: float | None
    response_body: dict[str, Any] | None
    memory_used: dict[str, Any] | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    model_latency_ms: float | None
    component_tokens: dict[str, int] | None
    response_quality_score: str
    expected_preference: str
    preference_appeared: bool | None
    status: str
    input_rate_per_1k: float
    output_rate_per_1k: float
    estimated_cost: float | None
    cost_note: str


def _api_base_url() -> str:
    """Return the configured API base URL without requiring application code."""

    return os.environ.get("HW6_API_BASE_URL", "http://127.0.0.1:8744").rstrip("/")


def _timeout_seconds() -> float:
    """Read a positive HTTP timeout, using the CPU-safe default of 420 seconds."""

    raw_value = os.environ.get("HW6_EXPERIMENT_TIMEOUT", "420")
    try:
        timeout = float(raw_value)
    except ValueError as exc:
        raise ValueError("HW6_EXPERIMENT_TIMEOUT must be numeric") from exc
    if timeout <= 0:
        raise ValueError("HW6_EXPERIMENT_TIMEOUT must be greater than zero")
    return timeout


def _post_chat(base_url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    """Send one chat request and return an honest response or error record.

    There is intentionally no retry loop.  A slow local model or an unavailable
    response is evidence about that run and should not be silently duplicated.
    """

    request = urllib.request.Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw_body = response.read().decode("utf-8")
            body = json.loads(raw_body)
            return {
                "http_status": response.status,
                "response_body": body,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError:
            body = {"raw_body": raw_body}
        return {
            "http_status": exc.code,
            "response_body": body,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": None,
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "http_status": None,
            "response_body": None,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _extract_usage(body: dict[str, Any] | None) -> tuple[int | None, int | None, int | None]:
    """Read usage fields when the API provides them, without inventing counts."""

    usage = body.get("usage", {}) if isinstance(body, dict) else {}
    return (
        usage.get("prompt_tokens"),
        usage.get("completion_tokens"),
        usage.get("total_tokens"),
    )


def _extract_component_metrics(
    body: dict[str, Any] | None,
) -> tuple[float | None, dict[str, int] | None]:
    """Read model latency and estimated prompt components when returned."""

    usage = body.get("usage", {}) if isinstance(body, dict) else {}
    latency = usage.get("latency_ms")
    components = body.get("component_tokens") if isinstance(body, dict) else None
    return latency, components if isinstance(components, dict) else None


def _estimate_cost(
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    """Estimate hypothetical cost only when both token counts are available."""

    if input_tokens is None or output_tokens is None:
        return None
    return round(
        input_tokens / 1000 * INPUT_RATE_PER_1K
        + output_tokens / 1000 * OUTPUT_RATE_PER_1K,
        8,
    )


def _preference_was_returned(body: dict[str, Any] | None) -> bool | None:
    """Check the answer text while keeping unavailable results explicitly unknown."""

    if not isinstance(body, dict):
        return None
    answer = body.get("answer")
    if not isinstance(answer, str):
        return None
    return PREFERENCE.lower() in answer.lower()


def run_window(short_term_n: int, base_url: str, timeout: float) -> ProbeResult:
    """Run one deterministic setup-and-follow-up sequence for a window."""

    user_id = f"{USER_ID_PREFIX}-{short_term_n}"
    session_id = f"hw6-window-{short_term_n}"
    messages = [*SETUP_MESSAGES, FOLLOW_UP_MESSAGE]
    print(
        f"Testing SHORT_TERM_N={short_term_n} in separate session {session_id}. "
        "Separate sessions prevent memory from leaking between windows."
    )
    print("Sending three bounded requests; no automatic retry will be performed.")

    final_result: dict[str, Any] = {
        "http_status": None,
        "response_body": None,
        "elapsed_ms": None,
        "error": None,
    }
    for message in messages:
        final_result = _post_chat(
            base_url,
            {
                "user_id": user_id,
                "session_id": session_id,
                "message": message,
                "short_term_n": short_term_n,
            },
            timeout,
        )
        if final_result["error"] or final_result["http_status"] != 200:
            print(
                f"Window {short_term_n}: request unavailable or failed; "
                "the window is recorded without retrying."
            )
            break

    body = final_result.get("response_body")
    input_tokens, output_tokens, total_tokens = _extract_usage(body)
    model_latency_ms, component_tokens = _extract_component_metrics(body)
    preference_appeared = _preference_was_returned(body)
    if final_result.get("error"):
        result_status = "unknown"
    elif final_result.get("http_status") == 200 and preference_appeared:
        result_status = "pass"
    elif final_result.get("http_status") == 200:
        result_status = "fail"
    else:
        result_status = "unknown"
    return ProbeResult(
        probe_id=f"short-term-window-{short_term_n}",
        short_term_n=short_term_n,
        user_id=user_id,
        session_id=session_id,
        turn_number=len(messages),
        seed=SEED,
        verify_seed=VERIFY_SEED,
        model=MODEL_NAME,
        request_messages=messages,
        follow_up_message=FOLLOW_UP_MESSAGE,
        http_status=final_result.get("http_status"),
        error=final_result.get("error"),
        elapsed_ms=final_result.get("elapsed_ms"),
        response_body=body,
        memory_used=body.get("memory_used") if isinstance(body, dict) else None,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        model_latency_ms=model_latency_ms,
        component_tokens=component_tokens,
        response_quality_score="unscored",
        expected_preference=PREFERENCE,
        preference_appeared=preference_appeared,
        status=result_status,
        input_rate_per_1k=INPUT_RATE_PER_1K,
        output_rate_per_1k=OUTPUT_RATE_PER_1K,
        estimated_cost=_estimate_cost(input_tokens, output_tokens),
        cost_note="Hypothetical estimate only; local Ollama usage is not actual hosted billing.",
    )


def _write_outputs(results: list[ProbeResult]) -> None:
    """Write the two requested evidence formats under the HW6 raw directory."""

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    records = [asdict(result) for result in results]
    with JSONL_OUTPUT.open("w", encoding="utf-8", newline="") as output_file:
        for record in records:
            output_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    fieldnames = list(records[0]) if records else ["probe_id", "status"]
    with CSV_OUTPUT.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            csv_record = dict(record)
            csv_record["request_messages"] = json.dumps(
                csv_record["request_messages"], ensure_ascii=False
            )
            csv_record["response_body"] = json.dumps(
                csv_record["response_body"], ensure_ascii=False
            )
            csv_record["memory_used"] = json.dumps(
                csv_record["memory_used"], ensure_ascii=False
            )
            writer.writerow(csv_record)


def main() -> None:
    """Run all three windows and write their actual, non-retried results."""

    timeout = _timeout_seconds()
    base_url = _api_base_url()
    print(f"HW6 short-term-memory experiment using API {base_url}.")
    print(f"Each request uses a {timeout:g}-second timeout and no automatic retry.")
    results = [run_window(window, base_url, timeout) for window in SHORT_TERM_WINDOWS]
    _write_outputs(results)
    print(f"Wrote {len(results)} results to {CSV_OUTPUT} and {JSONL_OUTPUT}.")


if __name__ == "__main__":
    main()
