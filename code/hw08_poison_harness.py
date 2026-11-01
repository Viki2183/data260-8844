"""HW8 poison-message and dead-letter observer.

The live mode publishes one poison fixture and observes the Writer's bounded
attempt metadata, dead-letter publication, and source-offset commit.  It does
not join the Writer group or resend the source message.
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
    DEFAULT_MAX_ATTEMPTS,
    DRAFTS_TOPIC,
    KAFKA_BOOTSTRAP_SERVERS,
    TASKS_TOPIC,
    WRITER_CONSUMER_GROUP,
)
from hw08_kafka_runtime import build_producer
from hw08_messages import build_message, deserialize_message, serialize_message, utc_timestamp


def parse_harness_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HW8 poison-message harness")
    parser.add_argument("--group-id", default=WRITER_CONSUMER_GROUP)
    parser.add_argument("--topic", default=TASKS_TOPIC)
    parser.add_argument("--dead-letter-topic", default=DEAD_LETTER_TOPIC)
    parser.add_argument(
        "--correlation-id",
        default="hw8-8844-poison-001",
    )
    parser.add_argument("--bootstrap-servers", default=KAFKA_BOOTSTRAP_SERVERS)
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument(
        "--later-valid-check",
        action="store_true",
        help="publish and observe one later valid task after DLT commit",
    )
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--validate-args", action="store_true")
    args = parser.parse_args(argv)
    if args.group_id != WRITER_CONSUMER_GROUP:
        parser.error(f"group id must be {WRITER_CONSUMER_GROUP!r}")
    if args.topic != TASKS_TOPIC:
        parser.error(f"topic must be {TASKS_TOPIC!r}")
    if args.dead_letter_topic != DEAD_LETTER_TOPIC:
        parser.error(f"dead-letter topic must be {DEAD_LETTER_TOPIC!r}")
    if args.max_attempts < 1:
        parser.error("max-attempts must be positive")
    if args.timeout_seconds <= 0:
        parser.error("timeout-seconds must be positive")
    if args.live and args.validate_args:
        parser.error("--live and --validate-args are mutually exclusive")
    return args


def _event(event_type: str, **fields: Any) -> dict[str, Any]:
    return {"event_type": event_type, **fields}


async def create_or_verify_topics(
    *, bootstrap_servers: str, include_later_check: bool = False
) -> None:
    from aiokafka.admin import AIOKafkaAdminClient, NewTopic
    from aiokafka.errors import TopicAlreadyExistsError

    admin = AIOKafkaAdminClient(
        bootstrap_servers=bootstrap_servers,
        request_timeout_ms=5000,
        client_id="hw08-poison-harness-admin",
    )
    await admin.start()
    try:
        existing = set(await admin.list_topics())
        required_topics = [TASKS_TOPIC, DEAD_LETTER_TOPIC]
        if include_later_check:
            required_topics.append(DRAFTS_TOPIC)
        missing = [
            topic
            for topic in required_topics
            if topic not in existing
        ]
        if missing:
            try:
                await admin.create_topics(
                    [
                        NewTopic(
                            topic,
                            num_partitions=2 if topic == TASKS_TOPIC else 1,
                            replication_factor=1,
                        )
                        for topic in missing
                    ]
                )
            except TopicAlreadyExistsError:
                pass
        verified = set(await admin.list_topics())
        missing_after = [
            topic
            for topic in required_topics
            if topic not in verified
        ]
        if missing_after:
            raise RuntimeError(f"required topics missing: {missing_after}")
    finally:
        await admin.close()


async def publish_poison(args: argparse.Namespace) -> dict[str, Any]:
    producer = await build_producer(bootstrap_servers=args.bootstrap_servers)
    await producer.start()
    try:
        correlation_id = args.correlation_id
        message = build_message(
            message_type="task_message",
            correlation_id=correlation_id,
            data={"invalid_writer_fixture": True, "question": ""},
            attempt=1,
            timestamp="2026-10-31T09:20:00Z",
            metadata={
                "fixture": POISON_FIXTURE_MARKER,
                "poison_fixture": True,
                "operation": "WRITE_DRAFT",
                "producer_application_retries": 0,
                "producer_resend_count": 0,
            },
        )
        metadata = await producer.send_and_wait(
            args.topic,
            serialize_message(message),
        )
        event = _event(
            "task_published",
            group_id=args.group_id,
            topic=args.topic,
            partition=metadata.partition,
            offset=metadata.offset,
            correlation_id=correlation_id,
            producer_application_retries=0,
            producer_retries=0,
            task_resend_count=0,
            message=message,
        )
        print(json.dumps(event), flush=True)
        return event
    finally:
        await producer.stop()


async def observe_dead_letter(
    args: argparse.Namespace,
    published: dict[str, Any],
) -> dict[str, Any]:
    from aiokafka import AIOKafkaConsumer

    observer = AIOKafkaConsumer(
        args.dead_letter_topic,
        bootstrap_servers=args.bootstrap_servers,
        group_id="s8844-poison-observer",
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        request_timeout_ms=5000,
    )
    await observer.start()
    try:
        deadline = time.monotonic() + args.timeout_seconds
        dead_letter: dict[str, Any] | None = None
        dlt_record: Any = None
        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            try:
                record = await asyncio.wait_for(observer.getone(), min(1.0, remaining))
            except asyncio.TimeoutError:
                continue
            candidate = deserialize_message(record.value)
            if candidate.get("correlation_id") == published["correlation_id"]:
                dead_letter = candidate
                dlt_record = record
                break
        if dead_letter is None or dlt_record is None:
            raise TimeoutError("dead-letter publication was not observed")

        metadata = dead_letter.get("metadata", {})
        failures = metadata.get("failed_attempts", [])
        if len(failures) != args.max_attempts:
            raise RuntimeError(
                f"expected {args.max_attempts} bounded attempts, found {len(failures)}"
            )
        for failure in failures:
            print(
                json.dumps(
                    _event(
                        "poison_attempt",
                        topic=metadata.get("source_topic"),
                        partition=metadata.get("source_partition"),
                        offset=metadata.get("source_offset"),
                        correlation_id=dead_letter.get("correlation_id"),
                        attempt=failure.get("attempt"),
                        error_type=failure.get("error_type"),
                        retry_scheduled=failure.get("retry_scheduled"),
                        max_attempts=args.max_attempts,
                    )
                ),
                flush=True,
            )
        published_event = _event(
            "dead_letter_published",
            topic=metadata.get("source_topic"),
            partition=metadata.get("source_partition"),
            offset=metadata.get("source_offset"),
            correlation_id=dead_letter.get("correlation_id"),
            attempt=dead_letter.get("attempt"),
            error_type=metadata.get("error_type"),
            dlt_topic=dlt_record.topic,
            dlt_partition=dlt_record.partition,
            dlt_offset=dlt_record.offset,
            failed_attempts=failures,
        )
        print(json.dumps(published_event), flush=True)
        return {
            "dead_letter": dead_letter,
            "record": dlt_record,
            "published_event": published_event,
        }
    finally:
        await observer.stop()


async def observe_source_commit(
    args: argparse.Namespace,
    *,
    source_topic: str,
    source_partition: int,
    source_offset: int,
    correlation_id: str,
) -> dict[str, Any]:
    from aiokafka import TopicPartition
    from aiokafka.admin import AIOKafkaAdminClient

    admin = AIOKafkaAdminClient(
        bootstrap_servers=args.bootstrap_servers,
        request_timeout_ms=5000,
        client_id="hw08-poison-harness-offsets",
    )
    await admin.start()
    try:
        deadline = time.monotonic() + args.timeout_seconds
        committed_offset: int | None = None
        while time.monotonic() < deadline:
            offsets = await admin.list_consumer_group_offsets(args.group_id)
            for topic_partition, offset_metadata in offsets.items():
                if (
                    topic_partition.topic == source_topic
                    and topic_partition.partition == source_partition
                ):
                    committed_offset = int(offset_metadata.offset)
                    break
            if committed_offset is not None and committed_offset >= source_offset + 1:
                break
            await asyncio.sleep(0.5)
        if committed_offset is None or committed_offset < source_offset + 1:
            raise TimeoutError("source offset commit was not observed after DLT publication")
        event = _event(
            "poison_offset_committed",
            topic=source_topic,
            partition=source_partition,
            offset=source_offset,
            correlation_id=correlation_id,
            committed=True,
            committed_offset=committed_offset,
            dead_letter_publication_required=True,
        )
        print(json.dumps(event), flush=True)
        return event
    finally:
        await admin.close()


async def observe_later_valid_message(args: argparse.Namespace) -> dict[str, Any]:
    """Verify that a later valid task is processed after poison DLT handling."""
    from aiokafka import AIOKafkaConsumer

    correlation_id = f"{args.correlation_id}-later-valid"
    observer = AIOKafkaConsumer(
        DRAFTS_TOPIC,
        bootstrap_servers=args.bootstrap_servers,
        group_id="s8844-poison-later-observer",
        enable_auto_commit=False,
        auto_offset_reset="latest",
        request_timeout_ms=5000,
    )
    producer = await build_producer(bootstrap_servers=args.bootstrap_servers)
    await observer.start()
    await producer.start()
    try:
        message = build_message(
            message_type="task_message",
            correlation_id=correlation_id,
            operation="WRITE_DRAFT",
            data={"question": "later valid HW8 task"},
            attempt=1,
            timestamp=utc_timestamp(),
            metadata={
                "post_dead_letter_check": True,
                "producer_application_retries": 0,
                "producer_resend_count": 0,
            },
        )
        produced = await producer.send_and_wait(
            TASKS_TOPIC,
            serialize_message(message),
        )
        published_event = _event(
            "later_valid_published",
            correlation_id=correlation_id,
            topic=produced.topic,
            partition=produced.partition,
            offset=produced.offset,
            producer_application_retries=0,
            producer_resend_count=0,
        )
        print(json.dumps(published_event), flush=True)
        deadline = time.monotonic() + args.timeout_seconds
        while time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            try:
                record = await asyncio.wait_for(
                    observer.getone(), min(1.0, remaining)
                )
            except asyncio.TimeoutError:
                continue
            candidate = deserialize_message(record.value)
            if candidate.get("correlation_id") != correlation_id:
                continue
            event = _event(
                "later_valid_processed",
                correlation_id=correlation_id,
                source_topic=TASKS_TOPIC,
                output_topic=record.topic,
                output_partition=record.partition,
                output_offset=record.offset,
                status=candidate.get("data", {}).get("status"),
                blocked_by_poison=False,
            )
            print(json.dumps(event), flush=True)
            return {"published": published_event, "processed": event}
        raise TimeoutError("later valid task was not processed after DLT handling")
    finally:
        await observer.stop()
        await producer.stop()


async def run_live(args: argparse.Namespace) -> None:  # pragma: no cover - live only
    await create_or_verify_topics(
        bootstrap_servers=args.bootstrap_servers,
        include_later_check=args.later_valid_check,
    )
    print(
        json.dumps(
            _event(
                "topics_verified",
                topics=[TASKS_TOPIC, DEAD_LETTER_TOPIC],
                bootstrap_servers=args.bootstrap_servers,
            )
        ),
        flush=True,
    )
    published = await publish_poison(args)
    observed = await observe_dead_letter(args, published)
    metadata = observed["dead_letter"]["metadata"]
    await observe_source_commit(
        args,
        source_topic=metadata["source_topic"],
        source_partition=int(metadata["source_partition"]),
        source_offset=int(metadata["source_offset"]),
        correlation_id=published["correlation_id"],
    )
    if args.later_valid_check:
        await observe_later_valid_message(args)


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - CLI wrapper
    args = parse_harness_args(argv)
    if args.validate_args:
        print(
            json.dumps(
                {
                    "group_id": args.group_id,
                    "topic": args.topic,
                    "dead_letter_topic": args.dead_letter_topic,
                    "bootstrap_servers": args.bootstrap_servers,
                    "correlation_id": args.correlation_id,
                    "max_attempts": args.max_attempts,
                    "live": False,
                }
            )
        )
        return
    if not args.live:
        raise SystemExit("pass --validate-args for offline validation or --live for approved Kafka execution")
    asyncio.run(run_live(args))


if __name__ == "__main__":  # pragma: no cover - CLI wrapper
    main()
