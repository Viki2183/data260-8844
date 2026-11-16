"""Capture Phase 5 live HW9/HW8 evidence without changing workers or envelopes.

The script consumes each Kafka topic with an independent read-only consumer
group, calls the existing authenticated HW9 endpoint, and writes only HW10 raw
evidence.  It never publishes, commits, seeks, deletes, flushes, or changes
Redis/Kafka configuration.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Mapping

import httpx
import redis
from aiokafka import AIOKafkaConsumer


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "reports/hw10/raw"
TRACE_DIR = RAW_DIR / "traces"
API_URL = os.getenv("HW10_API_URL", "http://127.0.0.1:8745/api/agent/ask")
BOOTSTRAP = os.getenv("HW10_KAFKA_BOOTSTRAP", "127.0.0.1:29092")
REDIS_HOST = os.getenv("HW9_REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("HW9_REDIS_PORT", "16379"))
THRESHOLD = float(os.getenv("HW9_SEMANTIC_THRESHOLD", "0.85"))
REPORT_ID = int(os.getenv("HW10_REPORT_ID", "5005"))
TIMEOUT_SECONDS = 75.0
TOPICS = {
    "inbox": "s8844_inbox",
    "tasks": "s8844_tasks",
    "drafts": "s8844_drafts",
    "final": "s8844_final",
}
TRACE_STAGES = ("cache_lookup", "inbox", "planner", "tasks", "writer", "drafts", "reviewer", "final", "evaluation")
QUESTION_TEMPLATES = [
    "Which release boundary is affected by the package vulnerability advisory?",
    "How severe is the open-source package security issue described by this CVE?",
    "What exploit precondition is required for this package flaw?",
    "Name the first patched release for the vulnerable package component.",
    "What mitigation should operators apply for this package vulnerability?",
    "Which software ecosystem publishes the package named in this advisory?",
    "Which maintainer action addressed the disclosed package vulnerability?",
    "Does the advisory describe a path traversal condition in the package?",
    "Does the package vulnerability permit injection through untrusted input?",
    "Is local access required to exploit the package security defect?",
    "Can the package flaw be reached over a network without authentication?",
    "Does exploitation require an authenticated package-registry account?",
    "What sensitive data could the affected package expose?",
    "Does the advisory permit arbitrary code execution in the package process?",
    "Is the package issue a dependency-confusion vulnerability?",
    "Does the affected release contain a prototype-pollution weakness?",
    "What symlink handling behavior causes the package security problem?",
    "Does archive extraction create the vulnerable filesystem behavior?",
    "Is the package advisory caused by an integer-overflow condition?",
    "Can the disclosed package flaw cause denial of service?",
    "Which input validation rule is missing from the vulnerable package?",
    "What boundary check should the package patch add?",
    "Does the vulnerability affect only development-time package tooling?",
    "Which package release introduced the insecure default configuration?",
    "What configuration change reduces exposure to the package advisory?",
    "Does the vulnerability depend on a crafted package name?",
    "Which package API receives the untrusted value in this advisory?",
    "Is the flaw triggered during package installation or runtime execution?",
    "What privilege level is needed to exploit this open-source package issue?",
    "Does the advisory identify a vulnerable transitive dependency?",
    "Which release removes the unsafe deserialization path?",
    "Can a malformed archive trigger the package vulnerability?",
    "Does the package bug permit command execution through a shell argument?",
    "What remediation version should downstream package users install?",
    "Which release train contains the security fix for the package?",
    "Does the package vulnerability require a specially crafted URL?",
    "Is the exposed package behavior limited to a test or debug mode?",
    "What attack surface is named in the open-source vulnerability report?",
    "Does the advisory affect package metadata parsing?",
    "Which package operation first processes the attacker-controlled data?",
    "Is the vulnerable behavior reachable before authentication?",
    "What severity category is assigned to the package security report?",
    "Does the patch change a default permission on extracted files?",
    "Which release corrects unsafe temporary-file handling?",
    "Can a remote attacker alter package resolution through this flaw?",
    "Does the vulnerability involve an incorrect cryptographic check?",
    "What user-visible impact follows from the affected package behavior?",
    "Which package version should be excluded from dependency locks?",
    "Does the advisory require a malicious repository or mirror?",
    "What defensive upgrade guidance accompanies the open-source package CVE?",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime | None) -> str | None:
    return value.isoformat().replace("+00:00", "Z") if value else None


def iso_after(start: datetime, duration_ms: float | None) -> str | None:
    if duration_ms is None:
        return None
    return iso(start + timedelta(milliseconds=max(0.0, float(duration_ms))))


def decode(value: bytes) -> dict[str, Any] | None:
    try:
        item = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return item if isinstance(item, dict) else None


class KafkaObserver:
    """Read-only Kafka observer using fresh groups and no offset commits."""

    def __init__(self) -> None:
        self.consumers: list[AIOKafkaConsumer] = []
        self.tasks: list[asyncio.Task[Any]] = []
        self.records: dict[str, list[dict[str, Any]]] = defaultdict(list)

    async def start(self) -> None:
        for stage, topic in TOPICS.items():
            consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=BOOTSTRAP,
                group_id=f"hw10-phase5-observer-{stage}-{uuid.uuid4().hex[:12]}",
                auto_offset_reset="latest",
                enable_auto_commit=False,
            )
            await consumer.start()
            self.consumers.append(consumer)
            self.tasks.append(asyncio.create_task(self._collect(stage, consumer)))
        await asyncio.sleep(1.0)

    async def _collect(self, stage: str, consumer: AIOKafkaConsumer) -> None:
        try:
            async for record in consumer:
                payload = decode(record.value)
                if not payload:
                    continue
                correlation_id = payload.get("correlation_id")
                if not correlation_id:
                    continue
                self.records[str(correlation_id)].append(
                    {
                        "observed_stage": stage,
                        "topic": record.topic,
                        "partition": record.partition,
                        "offset": record.offset,
                        "kafka_timestamp_ms": record.timestamp,
                        "message_type": payload.get("message_type"),
                        "payload": payload,
                    }
                )
        except asyncio.CancelledError:
            return

    async def wait_for(self, trace_id: str, timeout: float = 10.0) -> list[dict[str, Any]]:
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            records = self.records.get(trace_id, [])
            stages = {record["observed_stage"] for record in records}
            if {"inbox", "tasks", "drafts", "final"}.issubset(stages):
                return list(records)
            await asyncio.sleep(0.1)
        return list(self.records.get(trace_id, []))

    async def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        for consumer in self.consumers:
            await consumer.stop()


def stage_record(records: list[dict[str, Any]], stage: str) -> dict[str, Any] | None:
    matches = [record for record in records if record.get("observed_stage") == stage]
    return sorted(matches, key=lambda item: (item.get("kafka_timestamp_ms") or 0, item.get("offset") or 0))[0] if matches else None


def record_time(record: Mapping[str, Any] | None) -> datetime | None:
    if not record:
        return None
    timestamp_ms = record.get("kafka_timestamp_ms")
    if timestamp_ms is None:
        return None
    return datetime.fromtimestamp(float(timestamp_ms) / 1000, tz=timezone.utc)


def payload_data(record: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = record.get("payload") if record else None
    data = payload.get("data") if isinstance(payload, Mapping) else None
    return dict(data) if isinstance(data, Mapping) else {}


def redis_client() -> redis.Redis:
    # Embeddings are binary FLOAT32 values; decode textual fields selectively.
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)


def find_entry(client: redis.Redis, question: str) -> dict[str, Any] | None:
    prefix = "s8844:semantic_cache:entry:"
    for key in client.scan_iter(match=prefix + "*"):
        raw_entry = client.hgetall(key)
        entry: dict[str, Any] = {}
        for raw_key, raw_value in raw_entry.items():
            field = raw_key.decode("utf-8", errors="replace") if isinstance(raw_key, bytes) else str(raw_key)
            if field == "embedding":
                continue
            entry[field] = raw_value.decode("utf-8", errors="replace") if isinstance(raw_value, bytes) else raw_value
        if entry.get("question") == question:
            entry["entry_id"] = entry.get("entry_id") or (key.decode("utf-8", errors="replace") if isinstance(key, bytes) else str(key))[len(prefix) :]
            entry["redis_key"] = key.decode("utf-8", errors="replace") if isinstance(key, bytes) else str(key)
            return entry
    return None


async def call_api(client: httpx.AsyncClient, token: str, question: str, trace_id: str, report_id: int | None = None) -> dict[str, Any]:
    start_wall = utc_now()
    start_perf = time.perf_counter_ns()
    body: dict[str, Any] = {"question": question, "correlation_id": trace_id}
    if report_id is not None:
        body["report_id"] = report_id
    try:
        response = await client.post(
            API_URL,
            headers={"Authorization": f"Bearer {token}", "X-Correlation-ID": trace_id},
            json=body,
            timeout=TIMEOUT_SECONDS,
        )
        parsed: Any
        try:
            parsed = response.json()
        except ValueError:
            parsed = None
        return {
            "trace_id": trace_id,
            "question": question,
            "report_id": report_id,
            "http_status": response.status_code,
            "response": parsed if isinstance(parsed, dict) else None,
            "response_text": response.text if not isinstance(parsed, dict) else None,
            "start_time": iso(start_wall),
            "end_time": iso(utc_now()),
            "wall_clock_latency_ms": round((time.perf_counter_ns() - start_perf) / 1_000_000, 3),
            "time_source": "time.perf_counter_ns for duration; datetime.now(timezone.utc) for timestamps",
        }
    except Exception as exc:  # bounded failure is retained in raw evidence
        return {
            "trace_id": trace_id,
            "question": question,
            "report_id": report_id,
            "http_status": None,
            "response": None,
            "response_text": None,
            "start_time": iso(start_wall),
            "end_time": iso(utc_now()),
            "wall_clock_latency_ms": round((time.perf_counter_ns() - start_perf) / 1_000_000, 3),
            "time_source": "time.perf_counter_ns for duration; datetime.now(timezone.utc) for timestamps",
            "error": f"{type(exc).__name__}: {exc}",
        }


def kafka_message_fields(record: Mapping[str, Any] | None) -> dict[str, Any]:
    if not record:
        return {"topic": None, "partition": None, "offset": None, "message_type": None, "timestamp": None}
    return {
        "topic": record.get("topic"),
        "partition": record.get("partition"),
        "offset": record.get("offset"),
        "message_type": record.get("message_type"),
        "timestamp": iso(record_time(record)),
    }


def stage_row(
    stage: str,
    *,
    status: str,
    start: datetime | None = None,
    end: datetime | None = None,
    duration_ms: float | None = None,
    record: Mapping[str, Any] | None = None,
    error: str | None = None,
    cache_status: str | None = None,
    similarity: float | None = None,
    threshold: float | None = THRESHOLD,
    entry_id: str | None = None,
    report_id: int | None = None,
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    fields = kafka_message_fields(record)
    return {
        "stage": stage,
        "start_time": iso(start),
        "end_time": iso(end),
        "duration_ms": round(duration_ms, 3) if duration_ms is not None else None,
        "status": status,
        "error": error,
        "topic": fields["topic"],
        "partition": fields["partition"],
        "offset": fields["offset"],
        "message_type": fields["message_type"],
        "cache_status": cache_status,
        "similarity": similarity,
        "threshold": threshold,
        "entry_id": entry_id,
        "report_id": report_id,
        "details": dict(details or {}),
    }


def build_trace(
    call: Mapping[str, Any],
    records: list[dict[str, Any]],
    *,
    entry: Mapping[str, Any] | None,
    failure_stage: str | None = None,
    failure_class: str | None = None,
) -> dict[str, Any]:
    response = call.get("response") if isinstance(call.get("response"), Mapping) else {}
    cache_status = response.get("cache_status")
    is_cached = response.get("is_cached")
    similarity = float(response["similarity"]) if response.get("similarity") is not None else None
    report_id = call.get("report_id")
    entry_id = entry.get("entry_id") if entry else None
    request_start = datetime.fromisoformat(str(call["start_time"]).replace("Z", "+00:00"))
    total_ms = float(response["latency_ms"]) if response.get("latency_ms") is not None else float(call.get("wall_clock_latency_ms", 0))
    request_end = request_start + timedelta(milliseconds=total_ms)
    timings = response.get("timings_ms") if isinstance(response.get("timings_ms"), Mapping) else {}
    cache_ms = sum(float(timings.get(key, 0.0)) for key in ("embedding", "redis_search")) if timings else None
    cache_end = request_start + timedelta(milliseconds=cache_ms) if cache_ms is not None else request_end
    inbox = stage_record(records, "inbox")
    tasks = stage_record(records, "tasks")
    drafts = stage_record(records, "drafts")
    final = stage_record(records, "final")
    inbox_time = record_time(inbox)
    tasks_time = record_time(tasks)
    drafts_time = record_time(drafts)
    final_time = record_time(final)
    planner_ms = (tasks_time - inbox_time).total_seconds() * 1000 if inbox_time and tasks_time else None
    writer_ms = (drafts_time - tasks_time).total_seconds() * 1000 if tasks_time and drafts_time else None
    reviewer_ms = (final_time - drafts_time).total_seconds() * 1000 if drafts_time and final_time else None
    pipeline_ms = sum(value for value in (planner_ms, writer_ms, reviewer_ms) if value is not None)
    queue_wait_ms = max(0.0, float(timings.get("agent", total_ms)) - pipeline_ms) if pipeline_ms is not None else None
    if failure_stage:
        error = str(response.get("detail") or call.get("error") or call.get("response_text") or "controlled failure")
        rows = [
            stage_row("cache_lookup", status="failed_before_cache_decision", start=request_start, end=request_end, duration_ms=total_ms, error=error, cache_status="unknown", similarity=None, entry_id=entry_id, report_id=report_id),
        ]
        rows.extend(stage_row(stage, status="not_reached", error=error, cache_status="unknown", similarity=None, entry_id=entry_id, report_id=report_id) for stage in TRACE_STAGES[1:])
    else:
        rows = [stage_row("cache_lookup", status="cache_hit" if is_cached else "cache_miss", start=request_start, end=cache_end, duration_ms=cache_ms, cache_status=cache_status, similarity=similarity, entry_id=entry_id, report_id=report_id, details={"timings_ms": dict(timings)} if timings else {})]
        if inbox and inbox_time:
            rows.append(stage_row("inbox", status="observed", start=request_start, end=inbox_time, duration_ms=(inbox_time - request_start).total_seconds() * 1000, record=inbox, cache_status=cache_status, similarity=similarity, entry_id=entry_id, report_id=report_id, details=payload_data(inbox)))
        else:
            rows.append(stage_row("inbox", status="unavailable", error="No matching Kafka inbox record observed", cache_status=cache_status, similarity=similarity, entry_id=entry_id, report_id=report_id))
        for stage, record, start, end, duration in (("planner", tasks, inbox_time, tasks_time, planner_ms), ("tasks", tasks, tasks_time, tasks_time, 0.0), ("writer", drafts, tasks_time, drafts_time, writer_ms), ("drafts", drafts, drafts_time, drafts_time, 0.0), ("reviewer", final, drafts_time, final_time, reviewer_ms), ("final", final, final_time, final_time, 0.0)):
            if record:
                rows.append(stage_row(stage, status="observed" if stage in {"planner", "writer", "reviewer"} else "observed_same_topic_record", start=start, end=end, duration_ms=duration, record=record, cache_status=cache_status, similarity=similarity, entry_id=entry_id, report_id=report_id, details=payload_data(record)))
            else:
                rows.append(stage_row(stage, status="unavailable", error=f"No matching Kafka {stage} record observed", cache_status=cache_status, similarity=similarity, entry_id=entry_id, report_id=report_id))
        rows.append(stage_row("evaluation", status="not_executed", error="Phase 3 judge was not executed per-request during this live experiment", cache_status=cache_status, similarity=similarity, entry_id=entry_id, report_id=report_id))
    return {
        "trace_id": call["trace_id"],
        "correlation_id": call["trace_id"],
        "question": call["question"],
        "start_time": call["start_time"],
        "end_time": call["end_time"],
        "duration_ms": round(total_ms, 3),
        "status": "failed" if failure_stage else "success",
        "error": (str(response.get("detail") or call.get("error") or call.get("response_text")) if failure_stage else None),
        "failure_stage": failure_stage,
        "failure_class": failure_class,
        "cache_status": cache_status or ("unknown" if failure_stage else None),
        "is_cached": is_cached,
        "similarity": similarity,
        "threshold": THRESHOLD,
        "threshold_source": "HW9_SEMANTIC_THRESHOLD environment variable or existing code default 0.85",
        "entry_id": entry_id,
        "report_id": report_id,
        "http_status": call.get("http_status"),
        "response": response,
        "timings_ms": dict(timings),
        "stages": rows,
        "source": {"api": API_URL, "kafka_bootstrap": BOOTSTRAP, "redis": f"{REDIS_HOST}:{REDIS_PORT}"},
        "time_convention": "UTC ISO-8601 Z timestamps; monotonic time.perf_counter_ns for wall-clock durations",
    }


def percentile(values: list[float], percentage: float) -> float | None:
    """Linear interpolation over the inclusive sorted range (n-1)*p index."""
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    index = (len(ordered) - 1) * (percentage / 100.0)
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 3)


def latency_summary(rows: list[dict[str, Any]], attempts: list[dict[str, Any]]) -> dict[str, Any]:
    included = [row for row in rows if row.get("included")]
    stage_values: dict[str, list[float]] = {stage: [] for stage in ("cache_lookup", "planner", "writer", "reviewer", "queue_wait_total", "evaluation")}
    for row in included:
        for key in stage_values:
            value = row.get("latency_metrics_ms", {}).get(key)
            if isinstance(value, (int, float)):
                stage_values[key].append(float(value))
    total_values = [float(row["total_latency_ms"]) for row in included if isinstance(row.get("total_latency_ms"), (int, float))]
    p50_total = percentile(total_values, 50)
    table = []
    for stage, label in (("cache_lookup", "Cache lookup"), ("planner", "Planner"), ("writer", "Writer"), ("reviewer", "Reviewer"), ("queue_wait_total", "Queue wait (total)"), ("evaluation", "Evaluation")):
        p50 = percentile(stage_values[stage], 50)
        p95 = percentile(stage_values[stage], 95)
        table.append({"stage": label, "p50_ms": p50, "p95_ms": p95, "percent_of_cache_miss_end_to_end": round(p50 / p50_total * 100, 3) if p50 is not None and p50_total else None, "status": "unavailable" if not stage_values[stage] else "observed"})
    accidental_hits = [row for row in attempts if row.get("classification") == "accidental_hit"]
    failed = [row for row in attempts if row.get("classification") == "failed"]
    return {
        "phase": "phase-5",
        "status": "completed" if len(included) == 50 else "blocked_incomplete",
        "total_requests": len(attempts),
        "target_confirmed_misses": 50,
        "confirmed_misses": len(included),
        "accidental_hits": len(accidental_hits),
        "failed_requests": len(failed),
        "included_requests": len(included),
        "excluded_requests": len(attempts) - len(included),
        "timestamp_convention": "UTC ISO-8601 Z",
        "duration_time_source": "time.perf_counter_ns",
        "stage_boundaries": {
            "cache_lookup": "HW9 response timings_ms.embedding + timings_ms.redis_search",
            "planner": "Kafka tasks publication timestamp minus matching inbox publication timestamp; includes observable queue/processing interval",
            "writer": "Kafka drafts publication timestamp minus matching tasks publication timestamp; includes observable queue/processing interval",
            "reviewer": "Kafka final publication timestamp minus matching drafts publication timestamp; includes observable queue/processing interval",
            "queue_wait_total": "max(0, HW9 timings_ms.agent - planner_ms - writer_ms - reviewer_ms); residual after observed stage intervals",
            "evaluation": "not executed per request; no latency fabricated",
            "total": "HW9 response latency_ms, with monotonic wall-clock fallback only for failures",
        },
        "percentile_method": "linear interpolation on sorted values at index (n-1)*p/100",
        "cache_miss_end_to_end_percentage": "p50 stage latency divided by p50 total latency, multiplied by 100",
        "latency_table": table,
        "p50_total_latency_ms": p50_total,
        "p95_total_latency_ms": percentile(total_values, 95),
        "evaluation_status": "unavailable_not_executed_per_request",
        "attempt_classifications": {"confirmed_miss": len(included), "accidental_hit": len(accidental_hits), "failed": len(failed)},
    }


async def main_async() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    token_module = __import__("web_application.auth_hw7", fromlist=["create_access_token"])
    token = token_module.create_access_token("vikki1", "reader")
    redis_conn = redis_client()
    health = {"captured_at": iso(utc_now()), "api_url": API_URL, "redis": f"{REDIS_HOST}:{REDIS_PORT}", "kafka_bootstrap": BOOTSTRAP}
    try:
        health["redis_ping"] = bool(redis_conn.ping())
    except Exception as exc:
        health["redis_ping"] = False
        health["redis_error"] = f"{type(exc).__name__}: {exc}"
    observer = KafkaObserver()
    try:
        await observer.start()
        health["kafka_observer"] = "started_read_only"
    except Exception as exc:
        health["kafka_observer"] = "blocked"
        health["kafka_error"] = f"{type(exc).__name__}: {exc}"
        (RAW_DIR / "phase5_health.json").write_text(json.dumps(health, indent=2) + "\n", encoding="utf-8")
        raise
    async with httpx.AsyncClient() as client:
        miss_id = f"hw10-live-miss-{uuid.uuid4().hex[:12]}"
        trace_selection_attempts: list[dict[str, Any]] = []
        miss_trace: dict[str, Any] | None = None
        miss_question = ""
        for selection_number in range(1, 31):
            candidate_nonce = uuid.uuid4().hex
            candidate_question = (
                f"Open-source vulnerability trace selection nonce {candidate_nonce} "
                f"artifact marker {uuid.uuid4().hex}: document the package security evidence."
            )
            candidate_call = await call_api(client, token, candidate_question, miss_id, report_id=REPORT_ID)
            candidate_response = candidate_call.get("response") or {}
            candidate_is_miss = candidate_response.get("is_cached") is False and candidate_response.get("cache_status") == "miss"
            candidate_records = await observer.wait_for(miss_id, timeout=10.0 if candidate_is_miss else 0.25)
            candidate_entry = find_entry(redis_conn, candidate_question)
            trace_selection_attempts.append(
                {
                    "attempt": selection_number,
                    "trace_id": miss_id,
                    "question": candidate_question,
                    "http_status": candidate_call.get("http_status"),
                    "cache_status": candidate_response.get("cache_status"),
                    "is_cached": candidate_response.get("is_cached"),
                    "similarity": candidate_response.get("similarity"),
                    "selected": candidate_is_miss,
                }
            )
            if candidate_is_miss:
                miss_question = candidate_question
                miss_trace = build_trace(candidate_call, candidate_records, entry=candidate_entry)
                break
        if miss_trace is None:
            raise RuntimeError("blocked: unable to capture a genuine live cache miss trace after 30 selection attempts")
        hit_id = f"hw10-live-hit-{uuid.uuid4().hex[:12]}"
        hit_call = await call_api(client, token, miss_question, hit_id, report_id=REPORT_ID)
        hit_records = await observer.wait_for(hit_id, timeout=0.25)
        hit_entry = find_entry(redis_conn, miss_question)
        hit_trace = build_trace(hit_call, hit_records, entry=hit_entry)
        failed_id = f"hw10-live-failed-{uuid.uuid4().hex[:12]}"
        failed_question = f"Phase5 controlled validation failure {uuid.uuid4().hex}: report lookup"
        failed_call = await call_api(client, token, failed_question, failed_id, report_id=999999999)
        failed_records = await observer.wait_for(failed_id, timeout=2.0)
        failed_trace = build_trace(failed_call, failed_records, entry=None, failure_stage="validation/report_lookup", failure_class="validation")

        attempts: list[dict[str, Any]] = []
        confirmed = 0
        sequence = 0
        while confirmed < 50 and len(attempts) < 80:
            sequence += 1
            trace_id = f"hw10-latency-{sequence:03d}-{uuid.uuid4().hex[:8]}"
            nonce = uuid.uuid4().hex
            template = QUESTION_TEMPLATES[(sequence - 1) % len(QUESTION_TEMPLATES)]
            question = f"{template} Package nonce {nonce}; CVE evidence token {uuid.uuid4().hex}."
            call = await call_api(client, token, question, trace_id, report_id=REPORT_ID)
            response = call.get("response") or {}
            is_miss = response.get("is_cached") is False and response.get("cache_status") == "miss"
            records = await observer.wait_for(trace_id, timeout=10.0 if is_miss else 0.25)
            entry = find_entry(redis_conn, question)
            classification = "confirmed_miss" if is_miss and call.get("http_status") == 200 else "accidental_hit" if response.get("is_cached") is True or response.get("cache_status") == "hit" else "failed"
            trace = build_trace(call, records, entry=entry, failure_stage=None)
            stage_map = {item["stage"]: item for item in trace["stages"]}
            timings = response.get("timings_ms") if isinstance(response.get("timings_ms"), Mapping) else {}
            metrics = {
                "cache_lookup": sum(float(timings.get(key, 0.0)) for key in ("embedding", "redis_search")) if timings else None,
                "planner": next((stage_map["planner"]["duration_ms"] for _ in [0] if stage_map.get("planner", {}).get("duration_ms") is not None), None),
                "writer": next((stage_map["writer"]["duration_ms"] for _ in [0] if stage_map.get("writer", {}).get("duration_ms") is not None), None),
                "reviewer": next((stage_map["reviewer"]["duration_ms"] for _ in [0] if stage_map.get("reviewer", {}).get("duration_ms") is not None), None),
                "queue_wait_total": None,
                "evaluation": None,
            }
            if metrics["planner"] is not None and metrics["writer"] is not None and metrics["reviewer"] is not None:
                metrics["queue_wait_total"] = max(0.0, float(timings.get("agent", response.get("latency_ms", call.get("wall_clock_latency_ms", 0)))) - sum(float(metrics[key]) for key in ("planner", "writer", "reviewer")))
            attempts.append({
                "attempt_number": sequence,
                "trace_id": trace_id,
                "question": question,
                "classification": classification,
                "included": classification == "confirmed_miss",
                "http_status": call.get("http_status"),
                "is_cached": response.get("is_cached"),
                "cache_status": response.get("cache_status"),
                "similarity": response.get("similarity"),
                "threshold": THRESHOLD,
                "entry_id": trace.get("entry_id"),
                "report_id": REPORT_ID,
                "start_time": call.get("start_time"),
                "end_time": call.get("end_time"),
                "total_latency_ms": response.get("latency_ms", call.get("wall_clock_latency_ms")),
                "timings_ms": response.get("timings_ms", {}),
                "latency_metrics_ms": metrics,
                "stage_evidence": trace["stages"],
                "error": trace.get("error"),
                "time_source": call.get("time_source"),
            })
            if classification == "confirmed_miss":
                confirmed += 1

    await observer.stop()
    trace_files = {}
    for label, trace in (("cache_hit", hit_trace), ("cache_miss", miss_trace), ("failed", failed_trace)):
        path = TRACE_DIR / f"{label}_{trace['trace_id']}.json"
        path.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
        trace_files[label] = str(path.relative_to(ROOT))
    index = {
        "phase": "phase-5",
        "status": "completed" if miss_trace["status"] == "success" and miss_trace.get("cache_status") == "miss" and hit_trace["status"] == "success" and hit_trace.get("cache_status") == "hit" and failed_trace["status"] == "failed" else "blocked",
        "trace_ids": {"cache_hit": hit_trace["trace_id"], "cache_miss": miss_trace["trace_id"], "failed": failed_trace["trace_id"]},
        "trace_files": trace_files,
        "correlation_id_is_trace_id": True,
        "failure_stage": failed_trace.get("failure_stage"),
        "failure_class": failed_trace.get("failure_class"),
        "trace_selection_attempts": trace_selection_attempts,
    }
    (TRACE_DIR / "trace_index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    jsonl_path = RAW_DIR / "latency_50_cache_misses.jsonl"
    jsonl_path.write_text("".join(json.dumps(item, sort_keys=True) + "\n" for item in attempts), encoding="utf-8")
    summary = latency_summary(attempts, attempts)
    summary["trace_index"] = str((TRACE_DIR / "trace_index.json").relative_to(ROOT))
    summary["raw_jsonl"] = str(jsonl_path.relative_to(ROOT))
    (RAW_DIR / "latency_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    health["trace_index"] = str((TRACE_DIR / "trace_index.json").relative_to(ROOT))
    health["confirmed_miss_count"] = summary["confirmed_misses"]
    (RAW_DIR / "phase5_health.json").write_text(json.dumps(health, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"trace_index": index, "latency_summary": summary, "health": health}, indent=2))


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "code"))
    sys.path.insert(0, str(ROOT / "code" / "web_application"))
    asyncio.run(main_async())
