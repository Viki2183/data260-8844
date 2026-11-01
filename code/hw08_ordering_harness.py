"""Live HW8 ordering experiment for unkeyed and entity-keyed workloads."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import time
from pathlib import Path
from typing import Any

from hw08_consumer_death_harness import wait_for_writer_group
from hw08_kafka_config import (
    DRAFTS_TOPIC,
    KAFKA_BOOTSTRAP_SERVERS,
    ORDERING_MESSAGE_COUNT,
    TASKS_TOPIC,
    VERIFY_SEED,
)
from hw08_kafka_runtime import build_producer
from hw08_messages import deserialize_message, serialize_message, utc_timestamp
from hw08_ordering import generate_ordering_messages

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "reports" / "hw08" / "raw"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HW8 Kafka ordering harness")
    parser.add_argument("--mode", choices=("unkeyed", "keyed"), required=True)
    parser.add_argument("--bootstrap-servers", default=KAFKA_BOOTSTRAP_SERVERS)
    parser.add_argument("--group-id", default="s8844-writer")
    parser.add_argument("--topic", default=TASKS_TOPIC)
    parser.add_argument("--seed", type=int, default=VERIFY_SEED)
    parser.add_argument("--count", type=int, default=ORDERING_MESSAGE_COUNT)
    parser.add_argument("--timeout-seconds", type=float, default=45.0)
    parser.add_argument("--validate-args", action="store_true")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)
    if args.topic != TASKS_TOPIC:
        parser.error(f"topic must be {TASKS_TOPIC!r}")
    if args.group_id != "s8844-writer":
        parser.error("group-id must be 's8844-writer'")
    if args.seed != VERIFY_SEED:
        parser.error(f"seed must be {VERIFY_SEED}")
    if args.count != ORDERING_MESSAGE_COUNT:
        parser.error("count must be exactly 20")
    if args.timeout_seconds <= 0:
        parser.error("timeout-seconds must be positive")
    if args.live and args.validate_args:
        parser.error("--live and --validate-args are mutually exclusive")
    return args


def require_exact_two_partitions(partitions: object) -> list[int]:
    """Normalize aiokafka's synchronous partition set and enforce exactly two."""
    if not isinstance(partitions, set) or partitions != {0, 1}:
        raise RuntimeError(
            f"{TASKS_TOPIC} must have exactly partitions {{0, 1}}; found {partitions!r}"
        )
    return sorted(partitions)


async def read_topic_partitions(consumer: Any, topic: str) -> list[int]:
    """Read partitions and clean up without masking the original outcome."""
    startup_attempted = False
    original_error: BaseException | None = None
    try:
        startup_attempted = True
        await consumer.start()
        partitions = consumer.partitions_for_topic(topic)
        return require_exact_two_partitions(partitions)
    except BaseException as exc:
        original_error = exc
        raise
    finally:
        if startup_attempted:
            try:
                await consumer.stop()
            except asyncio.CancelledError:
                # Cleanup cancellation must never replace a result or the
                # original startup/partition exception.
                if original_error is None:
                    pass


async def verify_runtime(args: argparse.Namespace) -> dict[str, Any]:
    from aiokafka import AIOKafkaConsumer

    consumer = AIOKafkaConsumer(
        bootstrap_servers=args.bootstrap_servers,
        request_timeout_ms=5000,
    )
    normalized_partitions = await read_topic_partitions(consumer, args.topic)
    readiness = await wait_for_writer_group(
        bootstrap_servers=args.bootstrap_servers,
        group_id=args.group_id,
        topic=args.topic,
        timeout_seconds=args.timeout_seconds,
    )
    if readiness.get("active_member_count") != 2:
        raise RuntimeError(
            f"expected exactly two active Writers; found {readiness.get('active_member_count')}"
        )
    assigned = readiness.get("assigned_partitions_by_client", {})
    if len(assigned) != 2 or not all(args.topic in topics for topics in assigned.values()):
        raise RuntimeError(f"Writer assignments are incomplete: {assigned}")
    return {
        "topic_partitions": normalized_partitions,
        "readiness_method": readiness.get("readiness_method"),
        "active_member_count": readiness.get("active_member_count"),
        "assigned_partitions_by_client": assigned,
    }


async def publish_messages(args: argparse.Namespace) -> list[dict[str, Any]]:
    messages = generate_ordering_messages(
        seed=args.seed,
        count=args.count,
        keyed=args.mode == "keyed",
    )
    producer = await build_producer(bootstrap_servers=args.bootstrap_servers)
    await producer.start()
    produced: list[dict[str, Any]] = []
    try:
        for message in messages:
            message["metadata"] = {
                **dict(message.get("metadata", {})),
                "produced_timestamp": utc_timestamp(),
                "ordering_mode": args.mode,
            }
            key = message.get("key")
            metadata = await producer.send_and_wait(
                args.topic,
                serialize_message(message),
                key=key.encode("utf-8") if key is not None else None,
            )
            produced.append(
                {
                    "sequence": message["data"]["sequence"],
                    "correlation_id": message["correlation_id"],
                    "key": key,
                    "topic": metadata.topic,
                    "partition": metadata.partition,
                    "offset": metadata.offset,
                    "produced_timestamp": message["metadata"]["produced_timestamp"],
                }
            )
    finally:
        await producer.stop()
    if len(produced) != ORDERING_MESSAGE_COUNT:
        raise RuntimeError(f"expected 20 produced messages; found {len(produced)}")
    return produced


async def consume_outputs(
    args: argparse.Namespace,
    produced: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    from aiokafka import AIOKafkaConsumer

    by_correlation = {item["correlation_id"]: item for item in produced}
    consumer = AIOKafkaConsumer(
        DRAFTS_TOPIC,
        bootstrap_servers=args.bootstrap_servers,
        group_id=f"s8844-ordering-observer-{args.mode}",
        enable_auto_commit=False,
        auto_offset_reset="latest",
        request_timeout_ms=5000,
    )
    await consumer.start()
    rows: list[dict[str, Any]] = []
    try:
        deadline = time.monotonic() + args.timeout_seconds
        while len(rows) < ORDERING_MESSAGE_COUNT and time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            try:
                record = await asyncio.wait_for(consumer.getone(), min(1.0, remaining))
            except asyncio.TimeoutError:
                continue
            message = deserialize_message(record.value)
            correlation_id = message.get("correlation_id")
            source = by_correlation.get(correlation_id)
            if source is None:
                continue
            metadata = message.get("metadata", {})
            rows.append(
                {
                    **source,
                    "writer_consumer": metadata.get("writer_consumer", "unavailable"),
                    "consumed_timestamp": metadata.get("processed_timestamp", "unavailable"),
                    "processing_order": len(rows) + 1,
                }
            )
    finally:
        await consumer.stop()
    if len(rows) != ORDERING_MESSAGE_COUNT:
        raise RuntimeError(f"expected 20 processed messages; found {len(rows)}")
    if len({row["correlation_id"] for row in rows}) != ORDERING_MESSAGE_COUNT:
        raise RuntimeError("processed correlation IDs were not unique")
    if args.mode == "keyed" and len({row["partition"] for row in rows}) != 1:
        raise RuntimeError("entity-keyed messages were assigned to multiple partitions")
    return rows


def write_evidence(args: argparse.Namespace, rows: list[dict[str, Any]]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    jsonl_path = RAW / f"part3_ordering_{args.mode}.jsonl"
    csv_path = RAW / f"part3_ordering_{args.mode}.csv"
    jsonl_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    columns = [
        "sequence",
        "correlation_id",
        "key",
        "topic",
        "partition",
        "offset",
        "writer_consumer",
        "produced_timestamp",
        "consumed_timestamp",
        "processing_order",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


async def run_live(args: argparse.Namespace) -> None:  # pragma: no cover - live only
    runtime = await verify_runtime(args)
    observer_task = asyncio.create_task(asyncio.sleep(0))
    del observer_task
    # The output observer must be subscribed before the single publish loop.
    messages = generate_ordering_messages(
        seed=args.seed,
        count=args.count,
        keyed=args.mode == "keyed",
    )
    from aiokafka import AIOKafkaConsumer

    consumer = AIOKafkaConsumer(
        DRAFTS_TOPIC,
        bootstrap_servers=args.bootstrap_servers,
        group_id=f"s8844-ordering-observer-{args.mode}",
        enable_auto_commit=False,
        auto_offset_reset="latest",
        request_timeout_ms=5000,
    )
    await consumer.start()
    try:
        producer = await build_producer(bootstrap_servers=args.bootstrap_servers)
        await producer.start()
        produced: list[dict[str, Any]] = []
        try:
            for message in messages:
                message["metadata"] = {
                    **dict(message.get("metadata", {})),
                    "produced_timestamp": utc_timestamp(),
                    "ordering_mode": args.mode,
                }
                key = message.get("key")
                metadata = await producer.send_and_wait(
                    args.topic,
                    serialize_message(message),
                    key=key.encode("utf-8") if key is not None else None,
                )
                produced.append(
                    {
                        "sequence": message["data"]["sequence"],
                        "correlation_id": message["correlation_id"],
                        "key": key,
                        "topic": metadata.topic,
                        "partition": metadata.partition,
                        "offset": metadata.offset,
                        "produced_timestamp": message["metadata"]["produced_timestamp"],
                    }
                )
        finally:
            await producer.stop()
        by_correlation = {item["correlation_id"]: item for item in produced}
        rows: list[dict[str, Any]] = []
        deadline = time.monotonic() + args.timeout_seconds
        while len(rows) < ORDERING_MESSAGE_COUNT and time.monotonic() < deadline:
            remaining = max(0.1, deadline - time.monotonic())
            try:
                record = await asyncio.wait_for(consumer.getone(), min(1.0, remaining))
            except asyncio.TimeoutError:
                continue
            message = deserialize_message(record.value)
            source = by_correlation.get(message.get("correlation_id"))
            if source is None:
                continue
            metadata = message.get("metadata", {})
            rows.append(
                {
                    **source,
                    "writer_consumer": metadata.get("writer_consumer", "unavailable"),
                    "consumed_timestamp": metadata.get("processed_timestamp", "unavailable"),
                    "processing_order": len(rows) + 1,
                }
            )
        if len(rows) != ORDERING_MESSAGE_COUNT:
            raise RuntimeError(f"expected 20 processed messages; found {len(rows)}")
        if len({row["correlation_id"] for row in rows}) != ORDERING_MESSAGE_COUNT:
            raise RuntimeError("processed correlation IDs were not unique")
        if args.mode == "keyed" and len({row["partition"] for row in rows}) != 1:
            raise RuntimeError("entity-keyed messages were assigned to multiple partitions")
        write_evidence(args, rows)
        print(
            json.dumps(
                {
                    "event_type": "ordering_run_complete",
                    "mode": args.mode,
                    "seed": args.seed,
                    "count": len(rows),
                    "runtime": runtime,
                    "partitions_observed": sorted({row["partition"] for row in rows}),
                    "writer_consumers_observed": sorted({row["writer_consumer"] for row in rows}),
                    "evidence_jsonl": str(RAW / f"part3_ordering_{args.mode}.jsonl"),
                    "evidence_csv": str(RAW / f"part3_ordering_{args.mode}.csv"),
                }
            ),
            flush=True,
        )
    finally:
        await consumer.stop()


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - CLI wrapper
    args = parse_args(argv)
    if args.validate_args:
        print(
            json.dumps(
                {
                    "mode": args.mode,
                    "bootstrap_servers": args.bootstrap_servers,
                    "group_id": args.group_id,
                    "topic": args.topic,
                    "seed": args.seed,
                    "count": args.count,
                    "live": False,
                }
            )
        )
        return
    if not args.live:
        raise SystemExit("pass --validate-args or --live")
    asyncio.run(run_live(args))


if __name__ == "__main__":  # pragma: no cover
    main()
