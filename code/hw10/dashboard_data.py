"""Read-only HW10 dashboard data adapters.

The dashboard deliberately reads exported evidence only.  It does not connect
to Kafka, Redis, Ollama, or the HW8/HW9 services, and it never mutates evidence.
The existing ``correlation_id`` is exposed as the dashboard ``trace_id``.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping


STAGE_ORDER = (
    "cache_lookup",
    "inbox",
    "planner",
    "tasks",
    "writer",
    "drafts",
    "reviewer",
    "final",
    "evaluation",
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    raw = path.read_bytes()
    text: str
    for encoding in ("utf-8-sig", "utf-16", "utf-8"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - malformed evidence is reported to the caller
        raise UnicodeDecodeError("utf-8", raw, 0, 1, f"unsupported evidence encoding: {path}")
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} is not a JSON object")
        records.append(value)
    return records


def _message(record: Mapping[str, Any]) -> Mapping[str, Any]:
    value = record.get("message")
    return value if isinstance(value, Mapping) else {}


def _correlation_id(record: Mapping[str, Any]) -> str | None:
    direct = record.get("correlation_id")
    if direct:
        return str(direct)
    nested = _message(record).get("correlation_id")
    return str(nested) if nested else None


def _timestamp_ms(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).timestamp() * 1000
    except ValueError:
        return None


def _timestamp(record: Mapping[str, Any]) -> tuple[str | None, float | None]:
    raw = record.get("timestamp")
    if raw is None:
        raw = _message(record).get("timestamp")
    numeric = record.get("timestamp_ms")
    if numeric is None:
        numeric = _timestamp_ms(raw)
    return (str(raw) if raw is not None else None, _timestamp_ms(numeric))


def _new_trace(traces: dict[str, dict[str, Any]], trace_id: str) -> dict[str, Any]:
    return traces.setdefault(
        trace_id,
        {
            "trace_id": trace_id,
            "correlation_id": trace_id,
            "observations": [],
            "source_kinds": set(),
        },
    )


def _add_observation(
    traces: dict[str, dict[str, Any]],
    trace_id: str,
    *,
    stage: str,
    status: str,
    source: Path | str,
    source_kind: str,
    timestamp: str | None = None,
    end_timestamp: str | None = None,
    timestamp_ms: float | None = None,
    duration_ms: float | None = None,
    topic: Any = None,
    partition: Any = None,
    offset: Any = None,
    error: str | None = None,
    cache_status: str | None = None,
    cache_metadata: Mapping[str, Any] | None = None,
    details: Mapping[str, Any] | None = None,
    timing_provenance: str | None = None,
) -> None:
    trace = _new_trace(traces, trace_id)
    trace["source_kinds"].add(source_kind)
    trace["observations"].append(
        {
            "stage": stage,
            "status": status,
            "source_kind": source_kind,
            "source_file": str(source),
            "timestamp": timestamp,
            "start_time": timestamp,
            "end_time": end_timestamp,
            "timestamp_ms": timestamp_ms,
            "duration_ms": duration_ms,
            "error": error,
            "topic": topic,
            "partition": partition,
            "offset": offset,
            "cache_status": cache_status,
            "cache_metadata": dict(cache_metadata or {}),
            "details": dict(details or {}),
            "timing_provenance": timing_provenance,
        }
    )


def _stage_from_hw8_record(record: Mapping[str, Any]) -> str | None:
    raw = str(record.get("stage") or record.get("process") or "").lower()
    return {"input": "inbox", "planner": "planner", "writer": "writer", "reviewer": "reviewer"}.get(raw)


def _add_hw8_records(traces: dict[str, dict[str, Any]], path: Path, *, source_kind: str) -> None:
    for record in _read_jsonl(path):
        trace_id = _correlation_id(record)
        if not trace_id:
            continue
        stage = _stage_from_hw8_record(record)
        event = str(record.get("event") or "")
        if stage is None and event == "input_published":
            stage = "inbox"
        if stage is None and event == "final_received":
            stage = "final"
        if stage is None:
            continue
        message = _message(record)
        data = message.get("data") if isinstance(message.get("data"), Mapping) else {}
        timestamp, timestamp_ms = _timestamp(record)
        details = {"message_type": message.get("message_type"), **dict(data)}
        status = "observed"
        _add_observation(
            traces,
            trace_id,
            stage=stage,
            status=status,
            source=path,
            source_kind=source_kind,
            timestamp=timestamp,
            timestamp_ms=timestamp_ms,
            topic=record.get("topic"),
            partition=record.get("partition"),
            offset=record.get("offset"),
            error=record.get("error"),
            details=details,
        )
        # A Planner/Writer record is the only evidence for the corresponding
        # Kafka task/draft topic.  Show that fact without inventing a second
        # message or identifier.
        alias = {"planner": "tasks", "writer": "drafts"}.get(stage)
        if alias:
            _add_observation(
                traces,
                trace_id,
                stage=alias,
                status="observed_same_topic_record",
                source=path,
                source_kind=source_kind,
                timestamp=timestamp,
                timestamp_ms=timestamp_ms,
                topic=record.get("topic"),
                partition=record.get("partition"),
                offset=record.get("offset"),
                details={"note": f"No separate {alias} record; this is the observed {stage} message."},
            )
        if stage == "reviewer" and record.get("final_result") is True:
            _add_observation(
                traces,
                trace_id,
                stage="final",
                status="observed_same_reviewer_record",
                source=path,
                source_kind=source_kind,
                timestamp=timestamp,
                timestamp_ms=timestamp_ms,
                topic=record.get("topic"),
                partition=record.get("partition"),
                offset=record.get("offset"),
                details={"note": "final_result=true on the observed Reviewer record."},
            )


def _add_cache_record(
    traces: dict[str, dict[str, Any]],
    trace_id: str,
    record: Mapping[str, Any],
    source: Path,
) -> None:
    cache_status = str(record.get("cache_status") or "unknown").lower()
    status = "cache_hit" if cache_status == "hit" else "cache_miss" if cache_status == "miss" else "observed"
    _add_observation(
        traces,
        trace_id,
        stage="cache_lookup",
        status=status,
        source=source,
        source_kind="historical_live",
        duration_ms=float(record["latency_ms"]) if record.get("latency_ms") is not None else None,
        cache_status=cache_status,
        cache_metadata={
            "similarity": record.get("similarity"),
            "timings_ms": record.get("timings_ms"),
            "question": record.get("question"),
        },
        details={"answer": record.get("answer")},
    )


def _add_hw9_cache_evidence(traces: dict[str, dict[str, Any]], root: Path) -> None:
    warm_path = root / "reports/hw09/raw/warm_cache_10_query_final.json"
    if warm_path.exists():
        warm = _read_json(warm_path)
        for response in warm.get("responses", []):
            trace_id = response.get("correlation_id")
            if trace_id:
                _add_cache_record(traces, str(trace_id), response, warm_path)

    endpoint_path = root / "reports/hw09/raw/endpoint_live.json"
    if endpoint_path.exists():
        endpoint = _read_json(endpoint_path)
        for key in ("first_request", "exact_duplicate", "paraphrase", "different_query", "correlation_matching"):
            record = endpoint.get(key)
            if isinstance(record, Mapping) and record.get("correlation_id"):
                _add_cache_record(traces, str(record["correlation_id"]), record, endpoint_path)


def _add_offline_evaluation_evidence(traces: dict[str, dict[str, Any]], root: Path) -> None:
    cases_path = root / "reports/hw10/eval_cases.json"
    labels_path = root / "reports/hw10/human_labels.csv"
    run_paths = [root / f"reports/hw10/raw/judge_run_{i}.json" for i in (1, 2, 3)]
    if not cases_path.exists() or not all(path.exists() for path in run_paths):
        return
    cases = _read_json(cases_path)
    runs = [_read_json(path) for path in run_paths]
    run_by_case = [{item["case_id"]: item for item in run.get("cases", [])} for run in runs]
    for case in cases:
        trace_id = str(case.get("correlation_id", ""))
        if not trace_id:
            continue
        case_path = cases_path
        _add_observation(
            traces,
            trace_id,
            stage="writer",
            status="offline_reconstructed",
            source=case_path,
            source_kind="offline",
            details={"draft": case.get("candidate_draft"), "provenance": case.get("draft_provenance")},
        )
        _add_observation(
            traces,
            trace_id,
            stage="drafts",
            status="offline_reconstructed",
            source=case_path,
            source_kind="offline",
            details={"note": "Same offline Writer draft represented at the drafts stage."},
        )
        scores = [run_case.get(case["case_id"], {}).get("judge_score") for run_case in run_by_case]
        first = run_by_case[0].get(case["case_id"], {})
        _add_observation(
            traces,
            trace_id,
            stage="evaluation",
            status="offline_evaluation",
            source=run_paths[0],
            source_kind="offline",
            timestamp=first.get("timestamp"),
            duration_ms=first.get("latency_seconds", 0) * 1000 if first.get("latency_seconds") is not None else None,
            details={
                "judge_scores_by_trial": scores,
                "human_score": first.get("human_score"),
                "judge_reason": first.get("judge_reason"),
                "model": first.get("judge_model"),
            },
        )


def _add_phase5_live_traces(traces: dict[str, dict[str, Any]], root: Path) -> None:
    """Load the three Phase 5 trace artifacts into the same trace lookup model."""
    index_path = root / "reports/hw10/raw/traces/trace_index.json"
    if not index_path.exists():
        return
    index = _read_json(index_path)
    for relative in (index.get("trace_files") or {}).values():
        path = root / str(relative)
        if not path.exists():
            continue
        trace = _read_json(path)
        trace_id = str(trace.get("trace_id", ""))
        if not trace_id:
            continue
        normalized = _new_trace(traces, trace_id)
        normalized["source_kinds"].add("live")
        for row in trace.get("stages", []):
            _add_observation(
                traces,
                trace_id,
                stage=str(row.get("stage")),
                status=str(row.get("status")),
                source=path,
                source_kind="live",
                timestamp=row.get("start_time"),
                end_timestamp=row.get("end_time"),
                timestamp_ms=_timestamp_ms(row.get("start_time")),
                duration_ms=row.get("duration_ms"),
                topic=row.get("topic"),
                partition=row.get("partition"),
                offset=row.get("offset"),
                error=row.get("error"),
                cache_status=row.get("cache_status"),
                cache_metadata={
                    "similarity": row.get("similarity"),
                    "threshold": row.get("threshold"),
                    "entry_id": row.get("entry_id"),
                    "report_id": row.get("report_id"),
                },
                details=row.get("details"),
                timing_provenance=row.get("timing_provenance"),
            )


def load_traces(root: Path = REPO_ROOT) -> list[dict[str, Any]]:
    """Load all available traces and retain missing stages as unavailable UI rows."""
    traces: dict[str, dict[str, Any]] = {}
    journey = root / "reports/hw08/raw/part2_agent_journey.jsonl"
    demo = root / "reports/hw08/raw/part2_agent_demo_live2.jsonl"
    if journey.exists():
        _add_hw8_records(traces, journey, source_kind="historical_live")
    if demo.exists():
        _add_hw8_records(traces, demo, source_kind="historical_live")
    _add_hw9_cache_evidence(traces, root)
    _add_offline_evaluation_evidence(traces, root)
    _add_phase5_live_traces(traces, root)
    result: list[dict[str, Any]] = []
    for trace in traces.values():
        trace["source_kinds"] = sorted(trace["source_kinds"])
        result.append(trace)
    return sorted(result, key=lambda item: item["trace_id"])


def trace_rows(trace: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return exactly the required ordered stages, including unavailable rows."""
    observations = list(trace.get("observations", []))
    by_stage: dict[str, dict[str, Any]] = {}
    for observation in observations:
        # A Phase 5 trace may retain its original unavailable marker and then
        # append a real evaluator span.  The last observation is authoritative.
        by_stage[str(observation.get("stage"))] = dict(observation)
    timed = sorted(
        (item for item in observations if item.get("timestamp_ms") is not None),
        key=lambda item: float(item["timestamp_ms"]),
    )
    next_time: dict[int, float] = {}
    for current, following in zip(timed, timed[1:]):
        next_time[id(current)] = max(0.0, float(following["timestamp_ms"]) - float(current["timestamp_ms"]))

    rows: list[dict[str, Any]] = []
    for stage in STAGE_ORDER:
        observation = by_stage.get(stage)
        if observation is None:
            rows.append(
                {
                    "stage": stage,
                    "status": "unavailable",
                    "source_kind": "unavailable",
                    "timestamp": None,
                    "start_time": None,
                    "end_time": None,
                    "duration_ms": None,
                    "error": "No evidence record for this stage in the selected trace.",
                    "topic": None,
                    "partition": None,
                    "offset": None,
                    "cache_status": None,
                    "cache_metadata": {},
                    "source_file": None,
                    "details": {},
                }
            )
            continue
        row = dict(observation)
        row.setdefault("start_time", row.get("timestamp"))
        row.setdefault("end_time", None)
        if row.get("duration_ms") is None and id(observation) in next_time:
            row["duration_ms"] = round(next_time[id(observation)], 3)
        rows.append(row)
    return rows


def _metric(name: str, value: Any, unit: str, source: str, time_window: str, status: str) -> dict[str, Any]:
    return {
        "metric": name,
        "value": value,
        "unit": unit,
        "status": status,
        "source": source,
        "time_window": time_window,
    }


def load_summary(root: Path = REPO_ROOT) -> dict[str, Any]:
    """Aggregate only fields explicitly present in the recorded HW9 evidence."""
    source = "reports/hw09/raw/warm_cache_10_query_final.json"
    path = root / source
    if not path.exists():
        unavailable = [
            _metric(name, None, unit, source, "Unavailable: evidence file is missing", "unavailable")
            for name, unit in (
                ("Recent request count", "count"),
                ("Cache-hit count", "count"),
                ("Cache-miss count", "count"),
                ("Cache hit rate", "%"),
                ("Error count", "count"),
                ("Error rate", "%"),
                ("Total end-to-end latency", "ms"),
                ("Average cache-hit latency", "ms"),
                ("Average cache-miss latency", "ms"),
            )
        ]
        return {"metrics": unavailable, "live_available": False, "mode": "unavailable"}

    evidence = _read_json(path)
    responses = [item for item in evidence.get("responses", []) if isinstance(item, Mapping)]
    hits = [item for item in responses if item.get("cache_status") == "hit"]
    misses = [item for item in responses if item.get("cache_status") == "miss"]
    window = "Historical live warm-cache run: query numbers 1–10; warm-up excluded"
    metrics = [
        _metric("Recent request count", len(responses), "count", source, window, "historical_live"),
        _metric("Cache-hit count", len(hits), "count", source, window, "historical_live"),
        _metric("Cache-miss count", len(misses), "count", source, window, "historical_live"),
        _metric("Cache hit rate", round(len(hits) / len(responses) * 100, 2) if responses else None, "%", source, window, "historical_live"),
        _metric("Error count", None, "count", source, "Unavailable: no response-level error field in this evidence", "unavailable"),
        _metric("Error rate", None, "%", source, "Unavailable: no response-level error field in this evidence", "unavailable"),
        _metric("Total end-to-end latency", round(sum(float(item.get("latency_ms", 0)) for item in responses), 3), "ms", source, window, "historical_live"),
        _metric("Average cache-hit latency", round(mean(float(item["latency_ms"]) for item in hits), 3) if hits else None, "ms", source, window, "historical_live"),
        _metric("Average cache-miss latency", round(mean(float(item["latency_ms"]) for item in misses), 3) if misses else None, "ms", source, window, "historical_live"),
    ]
    live_metrics: list[dict[str, Any]] = []
    latency_path = root / "reports/hw10/raw/latency_summary.json"
    if latency_path.exists():
        latency = _read_json(latency_path)
        live_source = "reports/hw10/raw/latency_summary.json"
        live_window = "Live Phase 5 run; UTC evidence captured on the current run"
        total_requests = latency.get("total_requests")
        confirmed = latency.get("confirmed_misses")
        accidental = latency.get("accidental_hits")
        failed = latency.get("failed_requests")
        error_window = (
            f"Live Phase 5 latency experiment: {total_requests} requests; "
            f"{failed} failed; UTC evidence window"
        )
        metrics[4] = _metric("Error count", failed, "count", live_source, error_window, "live")
        metrics[5] = _metric(
            "Error rate",
            round((failed / total_requests) * 100, 3) if total_requests else None,
            "%",
            live_source,
            error_window,
            "live",
        )
        live_metrics = [
            _metric("Phase 5 request attempts", total_requests, "count", live_source, live_window, "live"),
            _metric("Phase 5 confirmed cache misses", confirmed, "count", live_source, live_window, "live"),
            _metric("Phase 5 accidental cache hits", accidental, "count", live_source, live_window, "live"),
            _metric("Phase 5 failed requests", failed, "count", live_source, live_window, "live"),
            _metric("Phase 5 p50 miss total latency", latency.get("p50_total_latency_ms"), "ms", live_source, live_window, "live"),
            _metric("Phase 5 p95 miss total latency", latency.get("p95_total_latency_ms"), "ms", live_source, live_window, "live"),
        ]
    return {
        "metrics": metrics,
        "live_metrics": live_metrics,
        "live_available": bool(live_metrics),
        "mode": "historical_and_live_evidence",
        "source": source,
        "notes": [
            "No live polling connection is configured for this read-only dashboard.",
            "Error count/rate use the Phase 5 latency evidence window and are calculated as failed_requests / total_requests.",
        ],
    }


def _labels(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["case_id"]: row for row in csv.DictReader(handle)}


def _observed_hw8_comparison(root: Path) -> dict[str, Any] | None:
    path = root / "reports/hw08/raw/part2_agent_journey.jsonl"
    if not path.exists():
        return None
    writer: Mapping[str, Any] | None = None
    reviewer: Mapping[str, Any] | None = None
    trace_id: str | None = None
    for record in _read_jsonl(path):
        trace_id = trace_id or _correlation_id(record)
        stage = str(record.get("stage") or "").lower()
        data = _message(record).get("data")
        if not isinstance(data, Mapping):
            continue
        if stage == "writer":
            writer = data
        elif stage == "reviewer":
            reviewer = data
    if not writer and not reviewer:
        return None
    return {
        "trace_id": trace_id,
        "writer_draft": writer.get("draft") if writer else None,
        "reviewer_final": reviewer.get("answer") if reviewer else None,
        "source": "reports/hw08/raw/part2_agent_journey.jsonl",
        "status": "historical_live_exemplar",
    }


def load_evaluation(root: Path = REPO_ROOT) -> dict[str, Any]:
    cases = _read_json(root / "reports/hw10/eval_cases.json")
    labels = _labels(root / "reports/hw10/human_labels.csv")
    runs = [_read_json(root / f"reports/hw10/raw/judge_run_{i}.json") for i in (1, 2, 3)]
    validation = _read_json(root / "reports/hw10/raw/judge_validation.json")
    live_path = root / "reports/hw10/raw/end_to_end/live_evaluation_trace.json"
    live_evaluation = _read_json(live_path) if live_path.exists() else None
    by_trial = [{case["case_id"]: case for case in run.get("cases", [])} for run in runs]
    rows: list[dict[str, Any]] = []
    for case in cases:
        case_id = case["case_id"]
        first = by_trial[0].get(case_id, {})
        rows.append(
            {
                "case_id": case_id,
                "question": case.get("question"),
                "human_score": int(labels[case_id]["human_label"]) if case_id in labels else None,
                "planner_score": None,
                "writer_score_trial_1": first.get("judge_score"),
                "writer_score_trial_2": by_trial[1].get(case_id, {}).get("judge_score"),
                "writer_score_trial_3": by_trial[2].get(case_id, {}).get("judge_score"),
                "reviewer_final_score": None,
                "draft_vs_final": "Unavailable: no per-case Reviewer/final output was saved for the frozen cases.",
                "writer_draft": case.get("candidate_draft"),
                "expected_answer": first.get("expected_answer"),
                "judge_reason": first.get("judge_reason"),
                "provenance": case.get("draft_provenance"),
            }
        )
    statistics = validation.get("statistics", {})
    live_view = None
    if live_evaluation:
        live_view = {
            "trace_id": live_evaluation.get("trace_id"),
            "question": live_evaluation.get("question"),
            "plan": next((item.get("details", {}).get("plan") for item in live_evaluation.get("stages", []) if item.get("stage") == "planner"), None),
            "writer_draft": next((item.get("details", {}).get("draft") for item in live_evaluation.get("stages", []) if item.get("stage") == "writer"), None),
            "reviewer_final": next((item.get("details", {}).get("answer") for item in live_evaluation.get("stages", []) if item.get("stage") == "reviewer"), None),
            "criteria": live_evaluation.get("evaluation", {}).get("criteria", []),
            "draft_score": live_evaluation.get("evaluation", {}).get("draft_score"),
            "final_score": live_evaluation.get("evaluation", {}).get("final_score"),
            "score_difference": live_evaluation.get("evaluation", {}).get("score_difference"),
            "status": live_evaluation.get("evaluation", {}).get("status"),
            "interpretation": live_evaluation.get("evaluation", {}).get("interpretation"),
            "evidence_path": "reports/hw10/raw/end_to_end/live_evaluation_trace.json",
        }
    return {
        "rows": rows,
        "statistics": statistics,
        "settings": {
            "model": validation.get("model"),
            "prompt_version": validation.get("prompt_version"),
            "temperature": validation.get("temperature"),
            "seed": validation.get("seed"),
            "timeout_seconds": validation.get("timeout_seconds"),
            "generation_settings": validation.get("generation_settings"),
        },
        "interpretation": (
            "All 20 confirmed human labels and all 60 normalized judge scores are 1. "
            "This is a repeatable finding that the candidate Writer drafts were not helpful "
            "because they repeated the questions; it is not evidence of correct vulnerability answers."
        ),
        "spearman_explanation": statistics.get("explanation"),
        "observed_comparison": _observed_hw8_comparison(root),
        "live_evaluation": live_view,
    }


def evidence_signature(root: Path = REPO_ROOT) -> tuple[tuple[str, int, int], ...]:
    """Return a cheap cache key so evidence refreshes invalidate st.cache_data."""
    paths = [
        root / "reports/hw09/raw/warm_cache_10_query_final.json",
        root / "reports/hw09/raw/endpoint_live.json",
        root / "reports/hw08/raw/part2_agent_journey.jsonl",
        root / "reports/hw08/raw/part2_agent_demo_live2.jsonl",
        root / "reports/hw10/eval_cases.json",
        root / "reports/hw10/human_labels.csv",
        root / "reports/hw10/raw/judge_run_1.json",
        root / "reports/hw10/raw/judge_run_2.json",
        root / "reports/hw10/raw/judge_run_3.json",
        root / "reports/hw10/raw/judge_validation.json",
        root / "reports/hw10/raw/end_to_end/live_evaluation_trace.json",
        root / "reports/hw10/raw/latency_summary.json",
        root / "reports/hw10/raw/traces/trace_index.json",
    ]
    trace_dir = root / "reports/hw10/raw/traces"
    if trace_dir.exists():
        paths.extend(sorted(trace_dir.glob("*.json")))
    return tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in paths if path.exists())
