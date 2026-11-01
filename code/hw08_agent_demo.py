"""One deterministic host/container-side Planner/Writer/Reviewer journey."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from hw08_kafka_config import FINAL_TOPIC, INBOX_TOPIC, KAFKA_BOOTSTRAP_SERVERS
from hw08_kafka_runtime import build_producer
from hw08_messages import build_message, deserialize_message, serialize_message, utc_timestamp


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="HW8 agent journey demo")
    parser.add_argument("--bootstrap-servers", default=KAFKA_BOOTSTRAP_SERVERS)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> list[dict[str, object]]:
    from aiokafka import AIOKafkaConsumer

    correlation_id = "hw8-8844-agent-live2-001"
    observer = AIOKafkaConsumer(
        FINAL_TOPIC,
        bootstrap_servers=args.bootstrap_servers,
        group_id="s8844-agent-observer-live2",
        enable_auto_commit=False,
        auto_offset_reset="latest",
        request_timeout_ms=5000,
    )
    producer = await build_producer(bootstrap_servers=args.bootstrap_servers)
    await observer.start()
    await producer.start()
    events: list[dict[str, object]] = []
    try:
        message = build_message(
            message_type="agent_input",
            correlation_id=correlation_id,
            data={"question": "Explain how Kafka coordinates vulnerability-report workers."},
            attempt=1,
            timestamp=utc_timestamp(),
            metadata={"producer_application_retries": 0, "producer_resend_count": 0},
        )
        metadata = await producer.send_and_wait(INBOX_TOPIC, serialize_message(message))
        events.append(
            {
                "event": "input_published",
                "topic": metadata.topic,
                "partition": metadata.partition,
                "offset": metadata.offset,
                "correlation_id": correlation_id,
                "message": message,
                "producer_application_retries": 0,
                "producer_resend_count": 0,
            }
        )
        print(json.dumps(events[-1], sort_keys=True), flush=True)
        deadline = time.monotonic() + args.timeout_seconds
        while time.monotonic() < deadline:
            try:
                record = await asyncio.wait_for(observer.getone(), 1.0)
            except asyncio.TimeoutError:
                continue
            candidate = deserialize_message(record.value)
            if candidate.get("correlation_id") != correlation_id:
                continue
            events.append(
                {
                    "event": "final_received",
                    "process": "reviewer",
                    "topic": record.topic,
                    "partition": record.partition,
                    "offset": record.offset,
                    "correlation_id": correlation_id,
                    "message": candidate,
                }
            )
            print(json.dumps(events[-1], sort_keys=True), flush=True)
            break
        else:
            raise TimeoutError("final agent message was not observed")
    finally:
        await observer.stop()
        await producer.stop()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
            encoding="utf-8",
        )
    return events


def main(argv: list[str] | None = None) -> None:
    asyncio.run(run(parse_args(argv)))


if __name__ == "__main__":
    main()
