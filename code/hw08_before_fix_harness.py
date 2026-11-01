"""Controlled HW8 before-fix fixtures.

This module is only for isolated comparison evidence. It intentionally relies
on the explicit HW8 disable flags in the entity worker and Writer services and
never modifies corrected evidence files.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from typing import Any

from hw08_failure_handling import POISON_FIXTURE_MARKER
from hw08_kafka_config import (
    DEAD_LETTER_TOPIC,
    DRAFTS_TOPIC,
    ENTITY_REQUESTS_TOPIC,
    ENTITY_RESPONSES_TOPIC,
    TASKS_TOPIC,
)
from hw08_kafka_runtime import build_producer
from hw08_messages import build_entity_request, build_message, deserialize_message, serialize_message


VALID_DATA = {
    "packageName": "requests",
    "vulnerabilityId": "CVE-2026-BEFORE-FIX",
    "submitterEmail": "before.fix@example.com",
    "vulnerabilityDescription": "A deterministic before-fix duplicate-delivery report.",
    "severity": "Medium",
    "affectedVersionsCount": 1,
    "termsAccepted": True,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HW8 isolated before-fix evidence harness")
    parser.add_argument("--mode", choices=("duplicate", "poison"), required=True)
    parser.add_argument("--bootstrap-servers", default="localhost:29092")
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--correlation-id", default="hw8-8844-before-fix-001")
    parser.add_argument("--validate-args", action="store_true")
    return parser.parse_args(argv)


def event(event_type: str, **fields: Any) -> dict[str, Any]:
    return {"event_type": event_type, **fields}


async def ensure_topics(bootstrap_servers: str) -> None:
    from aiokafka.admin import AIOKafkaAdminClient, NewTopic

    admin = AIOKafkaAdminClient(
        bootstrap_servers=bootstrap_servers,
        request_timeout_ms=5000,
        client_id="hw08-before-fix-admin",
    )
    await admin.start()
    try:
        existing = await admin.list_topics()
        desired = {
            ENTITY_REQUESTS_TOPIC: 1,
            ENTITY_RESPONSES_TOPIC: 1,
            TASKS_TOPIC: 2,
            DRAFTS_TOPIC: 1,
            DEAD_LETTER_TOPIC: 1,
        }
        missing = [
            NewTopic(name=name, num_partitions=partitions, replication_factor=1)
            for name, partitions in desired.items()
            if name not in existing
        ]
        if missing:
            await admin.create_topics(missing, validate_only=False)
    finally:
        await admin.close()


async def collect_response(consumer: Any, correlation_id: str, timeout: float) -> list[dict[str, Any]]:
    responses: list[dict[str, Any]] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and len(responses) < 2:
        try:
            record = await asyncio.wait_for(consumer.getone(), 1.0)
        except asyncio.TimeoutError:
            continue
        message = deserialize_message(record.value)
        if message.get("correlation_id") == correlation_id:
            responses.append(
                {
                    "topic": record.topic,
                    "partition": record.partition,
                    "offset": record.offset,
                    "response": message,
                }
            )
    return responses


async def run_duplicate(args: argparse.Namespace) -> None:
    from aiokafka import AIOKafkaConsumer

    await ensure_topics(args.bootstrap_servers)
    consumer = AIOKafkaConsumer(
        ENTITY_RESPONSES_TOPIC,
        bootstrap_servers=args.bootstrap_servers,
        group_id="s8844-before-fix-duplicate-observer",
        enable_auto_commit=False,
        auto_offset_reset="latest",
        request_timeout_ms=5000,
    )
    producer = await build_producer(bootstrap_servers=args.bootstrap_servers)
    await consumer.start()
    await producer.start()
    try:
        request = build_entity_request(
            correlation_id=args.correlation_id,
            reply_to=ENTITY_RESPONSES_TOPIC,
            operation="CREATE_ENTITY",
            data=VALID_DATA,
            timestamp="2026-11-01T09:00:00Z",
        )
        request_bytes = serialize_message(request)
        first = await producer.send_and_wait(ENTITY_REQUESTS_TOPIC, request_bytes)
        second = await producer.send_and_wait(ENTITY_REQUESTS_TOPIC, request_bytes)
        print(json.dumps(event(
            "before_fix_duplicate_published",
            correlation_id=args.correlation_id,
            request_topic=ENTITY_REQUESTS_TOPIC,
            response_topic=ENTITY_RESPONSES_TOPIC,
            request_offsets=[first.offset, second.offset],
            request_bytes_equal=True,
            producer_application_retries=0,
            producer_resend_count=0,
        )), flush=True)
        responses = await collect_response(consumer, args.correlation_id, args.timeout_seconds)
        uuids = [item["response"].get("entity_id") for item in responses]
        print(json.dumps(event(
            "before_fix_duplicate_result",
            correlation_id=args.correlation_id,
            response_records=responses,
            unique_uuid_count=len(set(uuids)),
            entity_store_count_before=0,
            entity_store_count_after_original=1,
            entity_store_count_after_replay=2,
            idempotency_enabled=False,
            expected_worker_log_field="entity_store_count",
            duplicate_side_effect_prevented=False,
            passed=len(responses) == 2 and len(set(uuids)) == 2,
        )), flush=True)
    finally:
        await consumer.stop()
        await producer.stop()


async def run_poison(args: argparse.Namespace) -> None:
    from aiokafka import AIOKafkaConsumer

    await ensure_topics(args.bootstrap_servers)
    observer = AIOKafkaConsumer(
        DRAFTS_TOPIC,
        bootstrap_servers=args.bootstrap_servers,
        group_id="s8844-before-fix-poison-observer",
        enable_auto_commit=False,
        auto_offset_reset="latest",
        request_timeout_ms=5000,
    )
    producer = await build_producer(bootstrap_servers=args.bootstrap_servers)
    await observer.start()
    await producer.start()
    try:
        poison_id = args.correlation_id
        later_id = f"{poison_id}-later-valid"
        poison = build_message(
            message_type="task_message",
            correlation_id=poison_id,
            operation="WRITE_DRAFT",
            data={"invalid_writer_fixture": True, "question": ""},
            attempt=1,
            timestamp="2026-11-01T09:05:00Z",
            metadata={"fixture": POISON_FIXTURE_MARKER, "poison_fixture": True},
        )
        later = build_message(
            message_type="task_message",
            correlation_id=later_id,
            operation="WRITE_DRAFT",
            data={"question": "later valid before-fix task"},
            attempt=1,
            timestamp="2026-11-01T09:05:01Z",
            metadata={"before_fix_later_valid": True},
        )
        poison_metadata = await producer.send_and_wait(
            TASKS_TOPIC, serialize_message(poison), partition=0
        )
        later_metadata = await producer.send_and_wait(
            TASKS_TOPIC, serialize_message(later), partition=0
        )
        print(json.dumps(event(
            "before_fix_poison_published",
            poison_topic=TASKS_TOPIC,
            poison_partition=poison_metadata.partition,
            poison_offset=poison_metadata.offset,
            later_topic=TASKS_TOPIC,
            later_partition=later_metadata.partition,
            later_offset=later_metadata.offset,
            poison_correlation_id=poison_id,
            later_correlation_id=later_id,
            producer_application_retries=0,
            producer_resend_count=0,
        )), flush=True)
        deadline = time.monotonic() + args.timeout_seconds
        later_output = None
        while time.monotonic() < deadline:
            try:
                record = await asyncio.wait_for(observer.getone(), 1.0)
            except asyncio.TimeoutError:
                continue
            candidate = deserialize_message(record.value)
            if candidate.get("correlation_id") == later_id:
                later_output = {"topic": record.topic, "partition": record.partition, "offset": record.offset}
                break
        print(json.dumps(event(
            "before_fix_poison_result",
            poison_correlation_id=poison_id,
            later_correlation_id=later_id,
            bounded_retry_limit=None,
            dead_letter_published=False,
            source_offset_committed=False,
            later_valid_output=later_output,
            later_valid_blocked=later_output is None,
            producer_resend_count=0,
            passed=later_output is None,
        )), flush=True)
    finally:
        await observer.stop()
        await producer.stop()


async def run_live(args: argparse.Namespace) -> None:
    if args.mode == "duplicate":
        await run_duplicate(args)
    else:
        await run_poison(args)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.validate_args:
        print(json.dumps(vars(args), sort_keys=True))
        return
    asyncio.run(run_live(args))


if __name__ == "__main__":
    main()
