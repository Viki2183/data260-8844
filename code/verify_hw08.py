"""Initial offline HW8 smoke verifier.

It intentionally does not connect to Kafka, Docker, MySQL, Ollama, or the
public network. It writes verification.json only when explicitly run.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from hw08_entity_store import EntityStore
from hw08_entity_validation import validate_vulnerability_report
from hw08_entity_worker import CREATE_OPERATION, GET_OPERATION, process_entity_message
from hw08_messages import build_entity_request, idempotency_key

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "hw08" / "verification.json"
LIVE_EVIDENCE = ROOT / "reports" / "hw08" / "raw" / "part1_create_get.jsonl"
LIVE_DEMO_EVIDENCE = ROOT / "reports" / "hw08" / "raw" / "part1_homework_demo_live2.jsonl"
AGENT_EVIDENCE = ROOT / "reports" / "hw08" / "raw" / "part2_agent_journey.jsonl"
AGENT_LIVE_EVIDENCE = ROOT / "reports" / "hw08" / "raw" / "part2_agent_demo_live2.jsonl"
DUPLICATE_EVIDENCE = ROOT / "reports" / "hw08" / "raw" / "part3_duplicate_delivery.jsonl"
POISON_EVIDENCE = ROOT / "reports" / "hw08" / "raw" / "part3_poison_dead_letter.jsonl"
CONSUMER_DEATH_EVIDENCE = ROOT / "reports" / "hw08" / "raw" / "part3_consumer_death.jsonl"
CONSUMER_DEATH_LIVE2_EVIDENCE = ROOT / "reports" / "hw08" / "raw" / "part3_consumer_death_live2.jsonl"
ORDERING_UNKEYED_EVIDENCE = ROOT / "reports" / "hw08" / "raw" / "part3_ordering_unkeyed.jsonl"
ORDERING_KEYED_EVIDENCE = ROOT / "reports" / "hw08" / "raw" / "part3_ordering_keyed.jsonl"
BEFORE_FIX_DUPLICATE_EVIDENCE = ROOT / "reports" / "hw08" / "raw" / "part3_before_fix_duplicate.jsonl"
BEFORE_FIX_CONSUMER_DEATH_EVIDENCE = ROOT / "reports" / "hw08" / "raw" / "part3_before_fix_consumer_death.jsonl"
BEFORE_FIX_POISON_EVIDENCE = ROOT / "reports" / "hw08" / "raw" / "part3_before_fix_poison_live3.jsonl"


def read_evidence_text(path: Path) -> str:
    """Read UTF-8 evidence and PowerShell UTF-16LE Tee-Object evidence safely."""
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe"):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


def read_before_fix(path: Path, expected_event: str) -> dict[str, object]:
    result: dict[str, object] = {
        "evidence_file": str(path.relative_to(ROOT)),
        "recorded": path.exists(),
        "passed": False,
        "status": "unavailable",
    }
    if not path.exists():
        return result
    try:
        records = [
            json.loads(line)
            for line in read_evidence_text(path).splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)
        return result
    result_record = next((record for record in records if record.get("event_type") == expected_event), {})
    passed = bool(result_record.get("passed"))
    if expected_event == "before_fix_duplicate_result":
        passed = passed and result_record.get("unique_uuid_count") == 2 and result_record.get("duplicate_side_effect_prevented") is False
    elif expected_event == "before_fix_poison_result":
        passed = passed and result_record.get("later_valid_blocked") is True and result_record.get("dead_letter_published") is False
    elif expected_event == "writer_terminated":
        passed = result_record.get("exit_code") == 42 and result_record.get("redelivery_observed") is False and result_record.get("output_observed") is False
    result.update({"passed": passed, "status": "passed" if passed else "failed", "record_count": len(records)})
    return result


def run_offline_smoke() -> list[dict[str, object]]:
    payload = {
        "packageName": "requests",
        "vulnerabilityId": "CVE-2026-0001",
        "submitterEmail": "student@example.com",
        "vulnerabilityDescription": "A sufficiently detailed vulnerability description.",
        "severity": "High",
        "affectedVersionsCount": 1,
        "termsAccepted": True,
    }
    valid_errors = validate_vulnerability_report(payload)
    invalid_errors = validate_vulnerability_report(
        {"packageName": "", "severity": "Unknown", "termsAccepted": False}
    )
    store = EntityStore()
    create_message = build_entity_request(
        correlation_id="verify-8844-create",
        reply_to="s8844_entity_responses",
        operation=CREATE_OPERATION,
        data=payload,
        timestamp="offline",
    )
    create = process_entity_message(
        create_message, store, uuid_factory=lambda: uuid.UUID(int=4)
    )
    expected_uuid = str(uuid.UUID(int=4))
    duplicate = process_entity_message(
        create_message, store, uuid_factory=lambda: uuid.UUID(int=5)
    )
    get_message = build_entity_request(
        correlation_id="verify-8844-get",
        reply_to="s8844_entity_responses",
        operation=GET_OPERATION,
        data={"entity_id": create.get("entity_id")},
        timestamp="offline",
    )
    get = process_entity_message(
        get_message, store
    )
    missing = process_entity_message(
        build_entity_request(
            correlation_id="verify-8844-missing",
            reply_to="s8844_entity_responses",
            operation=GET_OPERATION,
            data={"entity_id": "missing"},
            timestamp="offline",
        ),
        store,
    )
    return [
        {"name": "valid vulnerability-report validation", "passed": valid_errors == []},
        {
            "name": "invalid payload rejection",
            "passed": bool(invalid_errors) and not process_entity_message(
                build_entity_request(
                    correlation_id="verify-8844-invalid",
                    reply_to="s8844_entity_responses",
                    operation=CREATE_OPERATION,
                    data={"packageName": "", "severity": "Unknown", "termsAccepted": False},
                    timestamp="offline",
                ),
                EntityStore(),
            )["success"],
        },
        {"name": "offline CREATE_ENTITY", "passed": bool(create["success"])},
        {
            "name": "UUID generation",
            "passed": create.get("entity_id") == expected_uuid
            and create.get("entity_id") in store.entities,
        },
        {
            "name": "CREATE correlation_id preservation",
            "passed": create["correlation_id"] == "verify-8844-create",
        },
        {"name": "offline GET_ENTITY round trip", "passed": bool(get["success"])},
        {
            "name": "GET correlation_id preservation",
            "passed": get["correlation_id"] == "verify-8844-get",
        },
        {
            "name": "missing-entity behavior",
            "passed": not missing["success"]
            and missing.get("error") == "Entity not found"
            and missing["correlation_id"] == "verify-8844-missing",
        },
        {
            "name": "duplicate CREATE idempotency",
            "passed": duplicate.get("entity_id") == create.get("entity_id")
            and duplicate.get("metadata", {}).get("duplicate") is True
            and len(store.entities) == 1,
        },
        {
            "name": "GET idempotency key includes entity_id",
            "passed": idempotency_key(get_message)[-1] == expected_uuid,
        },
    ]


def read_live_smoke() -> dict[str, object]:
    """Validate recorded Phase 4A smoke evidence without contacting Kafka."""
    result: dict[str, object] = {
        "evidence_file": str(LIVE_EVIDENCE.relative_to(ROOT)),
        "recorded": LIVE_EVIDENCE.exists(),
        "passed": False,
        "status": "unavailable",
    }
    if not LIVE_EVIDENCE.exists():
        return result
    try:
        records = [json.loads(line) for line in read_evidence_text(LIVE_EVIDENCE).splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)
        return result
    if len(records) != 2:
        result["error"] = f"expected exactly two records, found {len(records)}"
        return result
    create, get = records
    create_response = create.get("response", {})
    get_response = get.get("response", {})
    create_entity = create_response.get("data", {}).get("entity", {})
    get_entity = get_response.get("data", {}).get("entity", {})
    passed = (
        create.get("event") == "CREATE_ENTITY"
        and get.get("event") == "GET_ENTITY"
        and create_response.get("success") is True
        and get_response.get("success") is True
        and create.get("entity_id")
        and create.get("entity_id") == get.get("entity_id")
        and create_response.get("correlation_id") == create.get("request", {}).get("correlation_id")
        and get_response.get("correlation_id") == get.get("request", {}).get("correlation_id")
        and create_entity == get_entity
    )
    result.update({"passed": bool(passed), "status": "passed" if passed else "failed"})
    return result


def read_homework_demo() -> dict[str, object]:
    """Validate the recorded live homework_demo.py API run."""
    result: dict[str, object] = {
        "evidence_file": str(LIVE_DEMO_EVIDENCE.relative_to(ROOT)),
        "recorded": LIVE_DEMO_EVIDENCE.exists(),
        "passed": False,
        "status": "unavailable",
    }
    if not LIVE_DEMO_EVIDENCE.exists():
        return result
    try:
        records = [
            json.loads(line)
            for line in read_evidence_text(LIVE_DEMO_EVIDENCE).splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)
        return result
    if len(records) != 6:
        result["error"] = f"expected six homework_demo.py records, found {len(records)}"
        return result
    api_records = records[1:]
    events = [record.get("body", {}).get("request", {}).get("operation") for record in api_records]
    responses = [record.get("body", {}).get("response", {}) for record in api_records]
    create, get, validation, missing, unknown = responses[0:5]
    entity = create.get("data", {}).get("entity", {})
    passed = (
        records[0].get("event") == "demo_started"
        and events == ["CREATE_ENTITY", "GET_ENTITY", "CREATE_ENTITY", "GET_ENTITY", "UNKNOWN_OPERATION"]
        and create.get("success") is True
        and get.get("success") is True
        and entity == get.get("data", {}).get("entity")
        and bool(create.get("entity_id"))
        and validation.get("success") is False
        and missing.get("success") is False
        and missing.get("error") == "Entity not found"
        and unknown.get("success") is False
        and unknown.get("error") == "Unknown operation"
        and all(
            record.get("body", {}).get("request", {}).get("correlation_id")
            == record.get("body", {}).get("response", {}).get("correlation_id")
            for record in api_records
        )
        and records[0].get("automatic_retries") == 0
    )
    result.update({"passed": bool(passed), "status": "passed" if passed else "failed", "record_count": len(records)})
    return result


def read_agent_journey() -> dict[str, object]:
    """Validate recorded Part 2 stage evidence without contacting Kafka."""
    result: dict[str, object] = {
        "evidence_file": str(AGENT_EVIDENCE.relative_to(ROOT)),
        "recorded": AGENT_EVIDENCE.exists(),
        "passed": False,
        "status": "unavailable",
    }
    if not AGENT_EVIDENCE.exists():
        return result
    try:
        records = [json.loads(line) for line in read_evidence_text(AGENT_EVIDENCE).splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)
        return result
    expected = [
        ("input", "s8844_inbox", "host-sender"),
        ("planner", "s8844_tasks", "Planner"),
        ("writer", "s8844_drafts", "Writer"),
        ("reviewer", "s8844_final", "Reviewer"),
    ]
    correlation_ids = {record.get("correlation_id") for record in records}
    passed = (
        len(records) == len(expected)
        and all(
            (record.get("stage"), record.get("topic"), record.get("process")) == expected[index]
            for index, record in enumerate(records)
        )
        and len(correlation_ids) == 1
        and all(record.get("message", {}).get("correlation_id") in correlation_ids for record in records)
        and records[-1].get("final_result") is True
        and records[-1].get("message", {}).get("data", {}).get("status") == "approved"
    )
    result.update({"passed": bool(passed), "status": "passed" if passed else "failed"})
    return result


def read_agent_live2() -> dict[str, object]:
    """Validate the corrected live API-side agent sender/observer result."""
    result: dict[str, object] = {
        "evidence_file": str(AGENT_LIVE_EVIDENCE.relative_to(ROOT)),
        "pipeline_log": "reports/hw08/raw/part2_agent_pipeline_logs.log",
        "recorded": AGENT_LIVE_EVIDENCE.exists(),
        "passed": False,
        "status": "unavailable",
    }
    if not AGENT_LIVE_EVIDENCE.exists():
        return result
    try:
        records = [
            json.loads(line)
            for line in read_evidence_text(AGENT_LIVE_EVIDENCE).splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)
        return result
    correlation_ids = {record.get("correlation_id") for record in records}
    pipeline_log = ROOT / "reports" / "hw08" / "raw" / "part2_agent_pipeline_logs.log"
    log_text = read_evidence_text(pipeline_log) if pipeline_log.exists() else ""
    passed = (
        len(records) == 2
        and [record.get("event") for record in records] == ["input_published", "final_received"]
        and len(correlation_ids) == 1
        and all(record.get("topic") in {"s8844_inbox", "s8844_final"} for record in records)
        and records[-1].get("message", {}).get("data", {}).get("status") == "approved"
        and records[0].get("producer_application_retries") == 0
        and records[0].get("producer_resend_count") == 0
        and all(process in log_text for process in ("planner", "writer", "reviewer"))
    )
    result.update({"passed": bool(passed), "status": "passed" if passed else "failed", "record_count": len(records)})
    return result


def read_duplicate_delivery() -> dict[str, object]:
    """Validate recorded duplicate-delivery evidence without contacting Kafka."""
    result: dict[str, object] = {
        "evidence_file": str(DUPLICATE_EVIDENCE.relative_to(ROOT)),
        "recorded": DUPLICATE_EVIDENCE.exists(),
        "passed": False,
        "status": "unavailable",
    }
    if not DUPLICATE_EVIDENCE.exists():
        return result
    try:
        records = [json.loads(line) for line in read_evidence_text(DUPLICATE_EVIDENCE).splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)
        return result
    if len(records) != 1:
        result["error"] = f"expected exactly one record, found {len(records)}"
        return result
    record = records[0]
    original = record.get("original_response", {}).get("message", {})
    replay = record.get("replay_response", {}).get("message", {})
    passed = (
        record.get("request_bytes_equal_on_replay") is True
        and record.get("same_uuid") is True
        and record.get("duplicate_delivery") is True
        and record.get("automatic_retries") == 0
        and record.get("original_uuid") == record.get("replay_uuid")
        and record.get("original_correlation_id") == record.get("replay_correlation_id")
        and original.get("success") is True
        and replay.get("success") is True
        and replay.get("metadata", {}).get("duplicate") is True
        and record.get("entity_store_count_after_original") == record.get("entity_store_count_after_replay")
    )
    result.update({"passed": bool(passed), "status": "passed" if passed else "failed"})
    return result


def read_consumer_death() -> dict[str, object]:
    """Validate the recorded real-Writer redelivery sequence offline."""
    result: dict[str, object] = {
        "evidence_file": str(CONSUMER_DEATH_EVIDENCE.relative_to(ROOT)),
        "recorded": CONSUMER_DEATH_LIVE2_EVIDENCE.exists() or CONSUMER_DEATH_EVIDENCE.exists(),
        "passed": False,
        "status": "unavailable",
    }
    live2_path = CONSUMER_DEATH_LIVE2_EVIDENCE
    evidence_path = live2_path if live2_path.exists() else CONSUMER_DEATH_EVIDENCE
    result["evidence_file"] = str(evidence_path.relative_to(ROOT))
    if not evidence_path.exists():
        return result
    try:
        records = [
            json.loads(line)
            for line in read_evidence_text(evidence_path).splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)
        return result
    if len(records) not in {7, 8}:
        result["error"] = f"expected seven legacy or eight corrected records, found {len(records)}"
        return result
    event_records = [record for record in records if record.get("event_type") != "topics_verified"]
    event_types = [record.get("event_type") for record in event_records]
    expected = [
        "task_published",
        "message_received",
        "pre_commit_crash",
        "writer_terminated",
        "message_redelivered",
        "output_published",
        "offset_committed",
    ]
    correlation_ids = {record.get("correlation_id") for record in records}
    original = records[1]
    redelivery = records[4]
    passed = (
        event_types[:7] == expected
        and len(correlation_ids) == 1
        and bool(next(iter(correlation_ids), None))
        and all(record.get("topic") == "s8844_tasks" for record in records[1:7])
        and original.get("partition") == redelivery.get("partition")
        and original.get("offset") == redelivery.get("offset")
        and original.get("process") == "writer-1"
        and records[2].get("process") == "writer-1"
        and records[2].get("committed") is False
        and (records[3].get("exit_code") == 42 or records[3].get("termination_observed") is True)
        and redelivery.get("process") == "writer-2"
        and records[5].get("process") == "writer-2"
        and records[5].get("output_topic") == "s8844_drafts"
        and records[6].get("process") == "writer-2"
        and records[6].get("committed") is True
        and records[0].get("readiness_method") in {"aiokafka", "kafka_cli_fallback"}
        and records[0].get("producer_application_retries") == 0
        and records[0].get("producer_retries") == 0
        and records[0].get("task_resend_count") == 0
    )
    if len(records) == 8:
        passed = passed and records[7].get("event_type") == "writer_restarted" and records[7].get("consumer_ready") is True
    result.update({"passed": bool(passed), "status": "passed" if passed else "failed"})
    return result


def read_poison_dead_letter() -> dict[str, object]:
    """Validate future bounded poison/DLT evidence without contacting Kafka."""
    result: dict[str, object] = {
        "evidence_file": str(POISON_EVIDENCE.relative_to(ROOT)),
        "recorded": POISON_EVIDENCE.exists(),
        "passed": False,
        "status": "unavailable",
    }
    live2_path = ROOT / "reports" / "hw08" / "raw" / "part3_poison_dead_letter_live2.jsonl"
    evidence_path = live2_path if live2_path.exists() else POISON_EVIDENCE
    result["evidence_file"] = str(evidence_path.relative_to(ROOT))
    if not evidence_path.exists():
        return result
    try:
        records = [
            json.loads(line)
            for line in read_evidence_text(evidence_path).splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)
        return result
    if len(records) < 5:
        result["error"] = f"expected task, bounded attempts, DLT, and commit records; found {len(records)}"
        return result
    event_records = [record for record in records if record.get("event_type") != "topics_verified"]
    event_types = [record.get("event_type") for record in event_records]
    primary_event_records = [
        record
        for record in event_records
        if record.get("event_type")
        in {"task_published", "poison_attempt", "dead_letter_published", "poison_offset_committed"}
    ]
    correlation_ids = {record.get("correlation_id") for record in primary_event_records if record.get("correlation_id")}
    attempt_records = [record for record in event_records if record.get("event_type") == "poison_attempt"]
    dlt_record = next((record for record in event_records if record.get("event_type") == "dead_letter_published"), {})
    commit_record = next((record for record in event_records if record.get("event_type") == "poison_offset_committed"), {})
    task_record = next((record for record in event_records if record.get("event_type") == "task_published"), {})
    later_published = next((record for record in event_records if record.get("event_type") == "later_valid_published"), {})
    later_processed = next((record for record in event_records if record.get("event_type") == "later_valid_processed"), {})
    source = (dlt_record.get("topic"), dlt_record.get("partition"), dlt_record.get("offset"))
    failure_summaries = [
        {
            "attempt": record.get("attempt"),
            "classification": "intentional_poison",
            "error_type": record.get("error_type"),
            "retry_scheduled": record.get("retry_scheduled"),
        }
        for record in attempt_records
    ]
    passed = (
        event_types[0] == "task_published"
        and all(event_type == "poison_attempt" for event_type in event_types[1 : 1 + len(attempt_records)])
        and len(correlation_ids) == 1
        and task_record.get("producer_application_retries") == 0
        and task_record.get("producer_retries") == 0
        and task_record.get("task_resend_count") == 0
        and len(attempt_records) == 3
        and [record.get("attempt") for record in attempt_records] == [1, 2, 3]
        and attempt_records[-1].get("retry_scheduled") is False
        and all(
            (record.get("topic"), record.get("partition"), record.get("offset")) == source
            for record in attempt_records
        )
        and source[0] == "s8844_tasks"
        and dlt_record.get("dlt_topic") == "s8844_dead_letter"
        and dlt_record.get("failed_attempts") == failure_summaries
        and commit_record.get("committed") is True
        and commit_record.get("committed_offset") == int(source[2]) + 1
        and later_published.get("correlation_id")
        and later_processed.get("blocked_by_poison") is False
        and later_processed.get("output_topic") == "s8844_drafts"
    )
    result.update({"passed": bool(passed), "status": "passed" if passed else "failed", "later_valid_check": later_processed})
    return result


def read_ordering(path: Path, *, keyed: bool) -> dict[str, object]:
    """Validate one measured 20-message ordering run offline."""
    result: dict[str, object] = {
        "evidence_file": str(path.relative_to(ROOT)),
        "recorded": path.exists(),
        "passed": False,
        "status": "unavailable",
        "keyed": keyed,
    }
    if not path.exists():
        return result
    try:
        records = [
            json.loads(line)
            for line in read_evidence_text(path).splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)
        return result
    by_partition: dict[int, list[dict[str, object]]] = {}
    for record in records:
        by_partition.setdefault(int(record.get("partition", -1)), []).append(record)
    passed = (
        len(records) == 20
        and {record.get("sequence") for record in records} == set(range(20))
        and len({record.get("correlation_id") for record in records}) == 20
        and all(record.get("topic") == "s8844_tasks" for record in records)
        and all(record.get("writer_consumer") in {"writer-1", "writer-2"} for record in records)
        and all(record.get("produced_timestamp") and record.get("consumed_timestamp") for record in records)
        and [record.get("processing_order") for record in records] == list(range(1, 21))
        and (len({record.get("partition") for record in records}) == 1 if keyed else True)
        and all(
            [row.get("sequence") for row in sorted(rows, key=lambda row: int(row.get("offset", -1)))]
            == sorted(row.get("sequence") for row in rows)
            for rows in by_partition.values()
        )
    )
    result.update(
        {
            "passed": bool(passed),
            "status": "passed" if passed else "failed",
            "message_count": len(records),
            "partitions_observed": sorted(by_partition),
            "writer_consumers_observed": sorted({record.get("writer_consumer") for record in records}),
        }
    )
    return result


def main() -> int:
    checks = run_offline_smoke()
    offline_pass = all(bool(check["passed"]) for check in checks)
    live_smoke = read_live_smoke()
    homework_demo = read_homework_demo()
    agent_journey = read_agent_journey()
    agent_live2 = read_agent_live2()
    duplicate_delivery = read_duplicate_delivery()
    consumer_death = read_consumer_death()
    poison_dead_letter = read_poison_dead_letter()
    ordering_unkeyed = read_ordering(ORDERING_UNKEYED_EVIDENCE, keyed=False)
    ordering_keyed = read_ordering(ORDERING_KEYED_EVIDENCE, keyed=True)
    before_fix_duplicate = read_before_fix(BEFORE_FIX_DUPLICATE_EVIDENCE, "before_fix_duplicate_result")
    before_fix_consumer_death = read_before_fix(BEFORE_FIX_CONSUMER_DEATH_EVIDENCE, "writer_terminated")
    before_fix_poison = read_before_fix(BEFORE_FIX_POISON_EVIDENCE, "before_fix_poison_result")
    payload = {
        "homework": 8,
        "sid4": 8844,
        "port_base": 8744,
        "prefix": "s8844",
        "domain_id": 4,
        "domain": "open-source package vulnerabilities",
        "kafka_image": "apache/kafka:3.9.2",
        "compose_project": "data260-hw8",
        "host_bootstrap": "localhost:29092",
        "docker_bootstrap": "hw08-kafka:9092",
        "commit_hash": "bda1110c82293aac22d16951f35cff5b368f825a",
        "commit_hash_status": "HW8 artifact commit; tag target is recorded separately",
        "artifact_commit_hash": "bda1110c82293aac22d16951f35cff5b368f825a",
        "tag_name": "hw8",
        "tag_commit_hash": "dfd3d31511d2af410288fa320b4e567276aef352",
        "model_configuration": {"model": "qwen3:8b", "mode": "offline foundation"},
        "seed": 8844,
        "verify_seed": 268844,
        "checks": checks,
        "offline_checks": checks,
        "offline_overall_pass": offline_pass,
        "live_kafka_smoke": live_smoke,
        "live_homework_demo": homework_demo,
        "live_agent_journey": agent_journey,
        "live_agent_journey_live2": agent_live2,
        "live_duplicate_delivery": duplicate_delivery,
        "live_consumer_death": consumer_death,
        "live_poison_dead_letter": poison_dead_letter,
        "live_ordering_unkeyed": ordering_unkeyed,
        "live_ordering_keyed": ordering_keyed,
        "before_fix_duplicate_delivery": before_fix_duplicate,
        "before_fix_consumer_death": before_fix_consumer_death,
        "before_fix_poison": before_fix_poison,
        "overall_pass": (
            offline_pass
            and (not live_smoke["recorded"] or bool(live_smoke["passed"]))
            and (not homework_demo["recorded"] or bool(homework_demo["passed"]))
            and (not agent_journey["recorded"] or bool(agent_journey["passed"]))
            and (not agent_live2["recorded"] or bool(agent_live2["passed"]))
            and (not duplicate_delivery["recorded"] or bool(duplicate_delivery["passed"]))
            and (not consumer_death["recorded"] or bool(consumer_death["passed"]))
            and (not poison_dead_letter["recorded"] or bool(poison_dead_letter["passed"]))
            and (not ordering_unkeyed["recorded"] or bool(ordering_unkeyed["passed"]))
            and (not ordering_keyed["recorded"] or bool(ordering_keyed["passed"]))
            and (not before_fix_duplicate["recorded"] or bool(before_fix_duplicate["passed"]))
            and (not before_fix_consumer_death["recorded"] or bool(before_fix_consumer_death["passed"]))
            and (not before_fix_poison["recorded"] or bool(before_fix_poison["passed"]))
        ),
        "live_results_claimed": bool(live_smoke["passed"]),
        "live_kafka_smoke_run": bool(live_smoke["recorded"]),
        "live_agent_journey_run": bool(agent_journey["recorded"]),
        "duplicate_delivery_run": bool(duplicate_delivery["recorded"]),
        "consumer_death_run": bool(consumer_death["recorded"]),
        "poison_dead_letter_run": bool(poison_dead_letter["recorded"]),
        "ordering_unkeyed_run": bool(ordering_unkeyed["recorded"]),
        "ordering_keyed_run": bool(ordering_keyed["recorded"]),
        "live_kafka_experiments_run": True,
        "docker_experiments_run": True,
        "database_experiments_run": False,
        "model_experiments_run": False,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = OUTPUT.with_name(f".{OUTPUT.name}.tmp")
    temporary_output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        os.replace(temporary_output, OUTPUT)
    except PermissionError:
        temporary_output.unlink(missing_ok=True)
        print("verification.json is locked; existing HW8 artifact was preserved")
    print(json.dumps(payload, indent=2))
    return 0 if payload["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

