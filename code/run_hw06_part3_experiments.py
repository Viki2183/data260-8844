"""Run the reproducible DATA260 HW6 Part 3 memory comparison.

The runner sends the same bounded 30-turn conversation for SHORT_TERM_N values
4, 12, and 30.  It knows only the public HTTP API and writes evidence under
reports/hw06/raw; it never bypasses the application with database writes.
"""

from __future__ import annotations

import csv
import json
import math
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


WINDOWS = (4, 12, 30)
USER_ID_PREFIX = "hw6-part3-user-8844"
SESSION_PREFIX = "hw6-part3-window-"
SEED = 8844
VERIFY_SEED = 268844
MODEL_NAME = "qwen3:8b"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
HARDWARE = "Intel Core i7-10750H CPU, approximately 16 GB RAM"
# These are deliberately hypothetical comparison rates, expressed per
# million tokens.  Ollama is local, so this is not an actual cloud bill.
INPUT_RATE_PER_MILLION = 1.0
OUTPUT_RATE_PER_MILLION = 5.0
QUALITY_THRESHOLD = 4.0
SUMMARY_REPLACEMENT_POLICY_NAME = (
    "Summary replacement policy: replace the oldest eligible message block "
    "with the current session summary while preserving the current user "
    "message and newest messages."
)
OUTPUT_DIRECTORY = Path(__file__).resolve().parents[1] / "reports" / "hw06" / "raw"
RUNS_JSONL = OUTPUT_DIRECTORY / "part3_30_turn_runs.jsonl"
WINDOW_SUMMARY_CSV = OUTPUT_DIRECTORY / "part3_window_summary.csv"
WINDOW_SUMMARY_JSON = OUTPUT_DIRECTORY / "part3_window_summary.json"
PROBE_SCORES_CSV = OUTPUT_DIRECTORY / "part3_probe_scores.csv"
COST_PROJECTION_CSV = OUTPUT_DIRECTORY / "part3_cost_projection.csv"


# The first 25 messages establish the same context for every window.  They
# intentionally include ordinary conversation so the experiment resembles a
# real session instead of a five-line synthetic lookup.
SETUP_MESSAGES = (
    "I am preparing a DATA 260 graduate-course project.",
    "My preferred study topic is distributed systems.",
    "I want to build a reliable graduate-course project.",
    "Reliability matters because the system should behave consistently.",
    "I prefer modular code so each responsibility is easy to understand.",
    "I also prefer testable code with focused checks for each module.",
    "Clear documentation is important for another developer joining the project.",
    "My project should explain both design decisions and verification steps.",
    "I am concerned about scalability as the amount of data grows.",
    "I am also concerned about fault tolerance when one component fails.",
    "A durable design decision is to keep raw records available for auditability.",
    "Another constraint is that previous homework evidence must remain preserved.",
    "I want the memory system to separate recent context from durable facts.",
    "Short-term context should be bounded so prompts stay predictable.",
    "Summaries should preserve useful older conversation information.",
    "Episodic facts should capture important preferences without replacing raw messages.",
    "I would like the API responses to expose measured token and latency metadata.",
    "The local qwen3:8b model runs on CPU and may be slow.",
    "I prefer concise answers with enough explanation to defend the implementation.",
    "The project should keep database responsibilities separate from route handlers.",
    "I want tests to use deterministic fake data when live services are unnecessary.",
    "A useful review question is whether a memory source actually affected the prompt.",
    "Another useful review question is whether a result can be reproduced.",
    "The final report should distinguish observations from estimates.",
    "Please keep these project preferences available for the five questions next.",
)

PROBES = (
    {
        "probe_id": "probe-01-topic",
        "question": "Which study topic did I say I preferred?",
        "expected_fact": "preferred study topic is distributed systems",
        "keywords": ("distributed systems",),
    },
    {
        "probe_id": "probe-02-reliability",
        "question": "What reliability goal did I describe for the project?",
        "expected_fact": "the project should be reliable",
        "keywords": ("reliable", "reliability"),
    },
    {
        "probe_id": "probe-03-design",
        "question": "What did I say about modular and testable code?",
        "expected_fact": "the code should be modular and testable",
        "keywords": ("modular", "testable"),
    },
    {
        "probe_id": "probe-04-documentation",
        "question": "What documentation preference did I mention?",
        "expected_fact": "clear documentation is important",
        "keywords": ("documentation", "documented"),
    },
    {
        "probe_id": "probe-05-scale",
        "question": "What concern did I raise about scalability and fault tolerance?",
        "expected_fact": "the project should address scalability and fault tolerance",
        "keywords": ("scalability", "fault tolerance"),
    },
)

CONVERSATION_MESSAGES = SETUP_MESSAGES + tuple(probe["question"] for probe in PROBES)
assert len(CONVERSATION_MESSAGES) == 30


def api_base_url() -> str:
    """Read the API address without importing application internals."""

    return os.getenv("HW6_API_BASE_URL", "http://127.0.0.1:8744").rstrip("/")


def timeout_seconds() -> float:
    """Return the positive CPU-safe HTTP timeout."""

    raw = os.getenv("HW6_EXPERIMENT_TIMEOUT", "420")
    value = float(raw)
    if value <= 0:
        raise ValueError("HW6_EXPERIMENT_TIMEOUT must be positive")
    return value


def estimate_tokens(text: str) -> int:
    """Estimate tokens deterministically; this is not model tokenizer output."""

    return math.ceil(len((text or "").split()) * 1.3)


def post_chat(base_url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    """Send exactly one request and return an honest result without retrying."""

    request = urllib.request.Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            try:
                body: Any = json.loads(raw)
            except json.JSONDecodeError:
                body = {"raw_body": raw[:10000]}
            return {
                "http_status": response.status,
                "response_body": body,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw_body": raw[:10000]}
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


def usage_fields(body: dict[str, Any] | None) -> dict[str, Any]:
    """Extract measured usage and estimates without inventing unavailable data."""

    usage = body.get("usage", {}) if isinstance(body, dict) else {}
    return {
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "model_latency_ms": usage.get("latency_ms"),
        "component_tokens": body.get("component_tokens") if isinstance(body, dict) else None,
        "memory_used": body.get("memory_used") if isinstance(body, dict) else None,
    }


def score_probe(probe: dict[str, Any], body: dict[str, Any] | None) -> dict[str, Any]:
    """Apply the fixed automated 1--5 rubric to one probe answer."""

    answer = body.get("answer") if isinstance(body, dict) else None
    if not isinstance(answer, str) or not answer.strip():
        return {
            "probe_id": probe["probe_id"],
            "question": probe["question"],
            "response": answer,
            "expected_fact": probe["expected_fact"],
            "matched_keywords": [],
            "quality_score": 1,
            "scoring_reason": "Unavailable or empty answer; automated rubric assigns 1.",
        }
    lowered = answer.lower()
    matched = [keyword for keyword in probe["keywords"] if keyword.lower() in lowered]
    if len(matched) == len(probe["keywords"]):
        score = 5
        reason = "Expected fact and all probe keywords were identified."
    elif matched:
        score = 3
        reason = "Some expected content was present, but the keyword match was incomplete."
    else:
        score = 2
        reason = "The answer was related or non-empty but did not identify the expected fact."
    return {
        "probe_id": probe["probe_id"],
        "question": probe["question"],
        "response": answer,
        "expected_fact": probe["expected_fact"],
        "matched_keywords": matched,
        "quality_score": score,
        "scoring_reason": reason + " This is an automated heuristic, not human evaluation.",
    }


def _mean(values: list[Any]) -> float | None:
    """Average numeric values while ignoring unavailable measurements."""

    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    return round(mean(numeric), 3) if numeric else None


COMPONENT_NAMES = (
    "primer",
    "session_summary",
    "lifetime_summary",
    "short_term_window",
    "episodic_facts",
    "current_user_message",
)


def aggregate_window_records(
    records: list[dict[str, Any]],
    short_term_n: int,
    probe_scores: list[dict[str, Any]],
    conversation_messages: tuple[str, ...] = CONVERSATION_MESSAGES,
) -> dict[str, Any]:
    """Aggregate already-recorded turns without making any service calls.

    The raw response uses ``current_user_message`` as the canonical component
    name, so the derived field keeps that same name.  Negative savings are
    valid estimates: they mean the measured compressed-prompt estimate was
    larger than the selected raw-history baseline.
    """

    successful = [record for record in records if record["http_status"] == 200]
    timed_out = [
        record for record in records
        if record["http_status"] is None
        and record.get("error")
        and "timeout" in record["error"].lower()
    ]
    summary = {
        "window": short_term_n,
        "user_id": records[0].get("user_id") if records else f"{USER_ID_PREFIX}-{short_term_n}",
        "session_id": records[0].get("session_id") if records else f"{SESSION_PREFIX}{short_term_n}",
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "model": MODEL_NAME,
        "embedding_model": EMBEDDING_MODEL,
        "hardware": HARDWARE,
        "total_turns": len(records),
        "successful_turns": len(successful),
        "failed_turns": sum(record["http_status"] not in (None, 200) for record in records),
        "timed_out_turns": len(timed_out),
        "mean_prompt_tokens_per_turn": _mean([record.get("prompt_tokens") for record in records]),
        "mean_completion_tokens_per_turn": _mean([record.get("completion_tokens") for record in records]),
        "mean_total_tokens_per_turn": _mean([record.get("total_tokens") for record in records]),
        "mean_model_latency_ms_per_turn": _mean([record.get("model_latency_ms") for record in records]),
        "mean_elapsed_ms_per_turn": _mean([record.get("elapsed_ms") for record in records]),
        "mean_estimated_prompt_tokens_per_turn": _mean([
            (record.get("component_tokens") or {}).get("estimated_prompt_total")
            for record in records
        ]),
        **{
            f"mean_{name}_tokens": _mean([
                (record.get("component_tokens") or {}).get(name)
                for record in records
            ]) for name in COMPONENT_NAMES
        },
        "mean_quality_score": _mean([record.get("quality_score") for record in probe_scores]),
        "probes_scored": sum(record.get("quality_score") is not None for record in probe_scores),
        "raw_history_token_estimate": estimate_tokens("\n".join(conversation_messages[:-1])),
        "compressed_prompt_token_estimate": (
            (records[-1].get("component_tokens") or {}).get("estimated_prompt_total")
            if records else None
        ),
        "mean_measured_prompt_tokens_per_turn": _mean([
            record.get("prompt_tokens") for record in records
        ]),
        "mean_estimated_component_prompt_tokens_per_turn": _mean([
            (record.get("component_tokens") or {}).get("estimated_prompt_total")
            for record in records
        ]),
        "mean_estimated_raw_history_tokens_per_turn": None,
        "mean_measurement_difference_per_turn": _mean([
            (record.get("prompt_tokens") -
             (record.get("component_tokens") or {}).get("estimated_prompt_total"))
            for record in records
            if isinstance(record.get("prompt_tokens"), (int, float))
            and isinstance((record.get("component_tokens") or {}).get("estimated_prompt_total"), (int, float))
        ]),
        "reconciliation_explanation": (
            "Measured Ollama prompt tokens and component estimates use different "
            "tokenization and accounting definitions; both are preserved."
        ),
        "policy": "bounded per-request short-term window selection",
        "baseline_name": "N=12 measured prompt tokens",
    }
    raw_estimate = summary["raw_history_token_estimate"]
    compressed = summary["compressed_prompt_token_estimate"]
    summary["estimated_token_savings"] = raw_estimate - compressed if compressed is not None else None
    summary["estimated_savings_percentage"] = (
        round(summary["estimated_token_savings"] / raw_estimate * 100, 3)
        if summary["estimated_token_savings"] is not None and raw_estimate
        else None
    )
    summary["mean_estimated_raw_history_tokens_per_turn"] = raw_estimate
    return summary


def build_summary_replacement_fixture(
    short_term_n: int = 12,
    threshold: int = 3,
) -> dict[str, Any]:
    """Build one deterministic fourth-policy result without live services.

    This fixture deliberately reports no model latency or quality score. Its
    token values are prompt-section estimates only, so it cannot be mistaken
    for a measured Ollama experiment or added to the existing 90-turn data.
    """

    import sys

    web_application_dir = str(Path(__file__).resolve().parent / "web_application")
    if web_application_dir not in sys.path:
        sys.path.insert(0, web_application_dir)
    import memory_logic_hw6 as memory_logic

    current_message = "Which study topic did I say I preferred?"
    session_summary = "The user prefers distributed systems for the graduate project."
    messages = [
        {
            "role": "user",
            "content": f"Earlier project message {index}",
            "created_at": index,
        }
        for index in range(short_term_n + 5)
    ]
    messages.append(
        {
            "role": "user",
            "content": current_message,
            "created_at": short_term_n + 5,
        }
    )
    baseline_breakdown = memory_logic.get_memory_usage_breakdown(
        "Helpful assistant.",
        None,
        session_summary,
        messages,
        current_message,
        [],
    )
    replacement = memory_logic.apply_summary_replacement_policy(
        messages,
        session_summary,
        current_message,
        enabled=True,
        threshold=threshold,
    )
    policy_breakdown = memory_logic.get_memory_usage_breakdown(
        "Helpful assistant.",
        None,
        session_summary,
        replacement["messages"],
        current_message,
        [],
    )
    prompt = memory_logic.build_memory_prompt(
        "Helpful assistant.",
        None,
        session_summary,
        replacement["messages"],
        current_message,
        [],
    )
    return {
        "offline_fixture_only": True,
        "policy_name": SUMMARY_REPLACEMENT_POLICY_NAME,
        "short_term_n": short_term_n,
        "threshold": threshold,
        "baseline_name": "N=12 prompt estimate with summary replacement disabled",
        "mean_prompt_token_estimate": policy_breakdown["estimated_prompt_total"],
        "baseline_mean_prompt_token_estimate": baseline_breakdown["estimated_prompt_total"],
        "token_savings_vs_N12_baseline": (
            baseline_breakdown["estimated_prompt_total"]
            - policy_breakdown["estimated_prompt_total"]
        ),
        "mean_latency_ms": None,
        "latency_status": "unavailable; offline fixture did not call a model",
        "mean_quality_score": None,
        "quality_status": "fixture-only; unscored",
        "quality_change_vs_N12": None,
        "messages_replaced": replacement["replaced_message_count"],
        "summary_included": replacement["summary_included"],
        "current_user_message_occurrences": prompt.count(current_message),
        "raw_messages_preserved": True,
        "note": "Estimated prompt values only; not measured Ollama usage.",
    }


def run_window(short_term_n: int, base_url: str, timeout: float, output_file) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run all 30 turns for one window and append each record immediately."""

    user_id = f"{USER_ID_PREFIX}-{short_term_n}"
    session_id = f"{SESSION_PREFIX}{short_term_n}"
    records: list[dict[str, Any]] = []
    probe_scores: list[dict[str, Any]] = []
    print(f"Testing SHORT_TERM_N={short_term_n} in separate session {session_id}.")
    print("The same 30 messages are used for every window; failures are not retried.")
    for turn, message in enumerate(CONVERSATION_MESSAGES, start=1):
        payload = {
            "user_id": user_id,
            "session_id": session_id,
            "message": message,
            "short_term_n": short_term_n,
        }
        print(f"  window={short_term_n} turn={turn}/30", flush=True)
        result = post_chat(base_url, payload, timeout)
        body = result.get("response_body")
        metrics = usage_fields(body)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "window": short_term_n,
            "turn": turn,
            "kind": "probe" if turn > 25 else "setup",
            "seed": SEED,
            "verify_seed": VERIFY_SEED,
            "model": MODEL_NAME,
            "embedding_model": EMBEDDING_MODEL,
            "hardware": HARDWARE,
            "user_id": user_id,
            "session_id": session_id,
            "request": payload,
            **result,
            **metrics,
        }
        if turn > 25:
            score = score_probe(PROBES[turn - 26], body)
            record.update(score)
            probe_scores.append(score)
        else:
            record.update(
                {
                    "probe_id": None,
                    "question": None,
                    "expected_fact": None,
                    "matched_keywords": [],
                    "quality_score": None,
                    "scoring_reason": None,
                }
            )
        output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        output_file.flush()
        records.append(record)
    summary = aggregate_window_records(records, short_term_n, probe_scores)
    return summary, probe_scores


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write dictionaries with stable columns and JSON-encode nested values."""

    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            clean = {
                key: json.dumps(value, ensure_ascii=False)
                if isinstance(value, (dict, list))
                else value
                for key, value in row.items()
            }
            writer.writerow(clean)


def build_cost_rows(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Project hypothetical costs using the required per-million-token rates."""

    rows = []
    for summary in summaries:
        turns = summary["total_turns"] * 10000
        input_tokens = (
            summary["mean_prompt_tokens_per_turn"] * turns
            if summary["mean_prompt_tokens_per_turn"] is not None else None
        )
        output_tokens = (
            summary["mean_completion_tokens_per_turn"] * turns
            if summary["mean_completion_tokens_per_turn"] is not None else None
        )
        input_cost = input_tokens / 1_000_000 * INPUT_RATE_PER_MILLION if input_tokens is not None else None
        output_cost = output_tokens / 1_000_000 * OUTPUT_RATE_PER_MILLION if output_tokens is not None else None
        rows.append({
            "window": summary["window"],
            "conversations": 10000,
            "input_rate_per_million": INPUT_RATE_PER_MILLION,
            "output_rate_per_million": OUTPUT_RATE_PER_MILLION,
            "estimated_input_tokens": input_tokens,
            "estimated_output_tokens": output_tokens,
            "estimated_total_tokens": input_tokens + output_tokens if input_tokens is not None and output_tokens is not None else None,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": input_cost + output_cost if input_cost is not None and output_cost is not None else None,
            "cost_note": "Hypothetical comparison only; Ollama is local with effectively zero direct API billing. CPU time and storage remain operational costs.",
        })
    return rows


def corrected_cost(summary: dict[str, Any]) -> float | None:
    """Return one window's corrected hypothetical total cost."""

    prompt = summary.get("mean_prompt_tokens_per_turn")
    completion = summary.get("mean_completion_tokens_per_turn")
    if prompt is None or completion is None:
        return None
    turns = summary["total_turns"] * 10000
    return (
        prompt * turns / 1_000_000 * INPUT_RATE_PER_MILLION
        + completion * turns / 1_000_000 * OUTPUT_RATE_PER_MILLION
    )


def choose_best_worst(summaries: list[dict[str, Any]]) -> dict[str, Any]:
    """Choose by corrected cost after applying the required quality threshold."""

    available = [
        s for s in summaries
        if s["mean_quality_score"] is not None
        and s["mean_quality_score"] >= QUALITY_THRESHOLD
        and corrected_cost(s) is not None
    ]
    if not available:
        return {"best": None, "worst": None, "reason": "Comparison unavailable because quality or corrected cost was unavailable."}
    best = min(
        available,
        key=lambda s: (
            corrected_cost(s),
            s.get("mean_model_latency_ms_per_turn") or float("inf"),
            s.get("mean_prompt_tokens_per_turn") or float("inf"),
        ),
    )
    worst = max(available, key=corrected_cost)
    return {
        "best": best["window"],
        "worst": worst["window"],
        "quality_threshold": QUALITY_THRESHOLD,
        "reason": "Best is lowest corrected total cost among settings meeting quality >= 4.0; ties use latency then measured prompt tokens. Worst is highest corrected total cost.",
    }


def build_cost_comparison_rows(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compare every window with the configured N=12 measured baseline."""

    baseline = next((s for s in summaries if s["window"] == 12), None)
    if baseline is None:
        return []
    baseline_prompt = baseline.get("mean_prompt_tokens_per_turn")
    baseline_cost = corrected_cost(baseline)
    baseline_quality = baseline.get("mean_quality_score")
    baseline_latency = baseline.get("mean_model_latency_ms_per_turn")
    rows = []
    for summary in summaries:
        prompt = summary.get("mean_prompt_tokens_per_turn")
        total_cost = corrected_cost(summary)
        quality = summary.get("mean_quality_score")
        latency = summary.get("mean_model_latency_ms_per_turn")
        savings = baseline_prompt - prompt if baseline_prompt is not None and prompt is not None else None
        rows.append({
            "window": summary["window"],
            "mean_prompt_tokens": prompt,
            "mean_completion_tokens": summary.get("mean_completion_tokens_per_turn"),
            "input_cost": next((r["input_cost"] for r in build_cost_rows([summary])), None),
            "output_cost": next((r["output_cost"] for r in build_cost_rows([summary])), None),
            "total_cost": total_cost,
            "quality_score": quality,
            "baseline_name": "N=12 measured prompt tokens",
            "savings_versus_baseline": savings,
            "savings_percentage_versus_baseline": (
                savings / baseline_prompt * 100
                if savings is not None and baseline_prompt else None
            ),
            "measured_cost_savings_versus_baseline": (
                baseline_cost - total_cost
                if baseline_cost is not None and total_cost is not None else None
            ),
            "quality_difference_versus_baseline": (
                quality - baseline_quality
                if quality is not None and baseline_quality is not None else None
            ),
            "latency_difference_ms_versus_baseline": (
                latency - baseline_latency
                if latency is not None and baseline_latency is not None else None
            ),
            "estimated_component_minus_raw_history_baseline": summary.get("estimated_token_savings"),
            "comparison_note": "Measured savings use prompt tokens versus N=12; raw-history/component estimates are reported separately.",
        })
    return rows


def regenerate_aggregate_outputs(
    raw_jsonl_path: Path = RUNS_JSONL,
    output_directory: Path = OUTPUT_DIRECTORY,
) -> dict[str, Any]:
    """Rebuild derived aggregate files from existing per-turn evidence only."""

    records = [
        json.loads(line)
        for line in raw_jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    summaries: list[dict[str, Any]] = []
    for window in WINDOWS:
        window_records = [record for record in records if record.get("window") == window]
        probe_scores = [
            {
                key: record.get(key)
                for key in (
                    "probe_id", "question", "response", "expected_fact",
                    "matched_keywords", "quality_score", "scoring_reason",
                )
            }
            for record in window_records
            if record.get("kind") == "probe"
        ]
        summaries.append(aggregate_window_records(window_records, window, probe_scores))

    payload = {
        "homework": "DATA260 HW6",
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "model": MODEL_NAME,
        "embedding_model": EMBEDDING_MODEL,
        "hardware": HARDWARE,
        "same_conversation_for_all_windows": True,
        "conversation_turns": 30,
        "probe_count": 5,
        "rubric": "5 exact and correct; 4 correct with minor incompleteness; 3 partial/vague; 2 related without expected fact; 1 incorrect, empty, or unavailable.",
        "automated_score_note": "Keyword scoring is an automated heuristic, not human evaluation.",
        "windows": summaries,
        "best_worst": choose_best_worst(summaries),
        "cost_projection": build_cost_rows(summaries),
        "cost_comparison": build_cost_comparison_rows(summaries),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "part3_window_summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    write_csv(output_directory / "part3_window_summary.csv", summaries)
    write_csv(output_directory / "part3_cost_projection.csv", payload["cost_projection"])
    write_csv(output_directory / "part3_cost_comparison.csv", payload["cost_comparison"])
    (output_directory / "part3_cost_comparison.json").write_text(
        json.dumps(payload["cost_comparison"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return payload


def main() -> None:
    """Run all windows and preserve partial per-turn evidence if needed."""

    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    probe_scores: list[dict[str, Any]] = []
    with RUNS_JSONL.open("w", encoding="utf-8") as raw_file:
        for window in WINDOWS:
            summary, scores = run_window(window, api_base_url(), timeout_seconds(), raw_file)
            summaries.append(summary)
            probe_scores.extend(scores)
    decision = choose_best_worst(summaries)
    payload = {
        "homework": "DATA260 HW6",
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "model": MODEL_NAME,
        "embedding_model": EMBEDDING_MODEL,
        "hardware": HARDWARE,
        "same_conversation_for_all_windows": True,
        "conversation_turns": 30,
        "probe_count": 5,
        "rubric": "5 exact and correct; 4 correct with minor incompleteness; 3 partial/vague; 2 related without expected fact; 1 incorrect, empty, or unavailable.",
        "automated_score_note": "Keyword scoring is an automated heuristic, not human evaluation.",
        "windows": summaries,
        "best_worst": decision,
        "cost_projection": build_cost_rows(summaries),
        "cost_comparison": build_cost_comparison_rows(summaries),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    WINDOW_SUMMARY_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_csv(WINDOW_SUMMARY_CSV, summaries)
    write_csv(PROBE_SCORES_CSV, probe_scores)
    write_csv(COST_PROJECTION_CSV, payload["cost_projection"])
    write_csv(OUTPUT_DIRECTORY / "part3_cost_comparison.csv", payload["cost_comparison"])
    (OUTPUT_DIRECTORY / "part3_cost_comparison.json").write_text(
        json.dumps(payload["cost_comparison"], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Completed {len(summaries)} bounded windows with no automatic retries.")
    print(f"Evidence written under {OUTPUT_DIRECTORY}.")


if __name__ == "__main__":
    main()
