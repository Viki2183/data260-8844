"""Single-message HW8 agent-pipeline sender and observer.

The live journey is intentionally explicit and performs no automatic retries.
Importing this module does not contact Kafka.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any

from hw08_kafka_runtime import build_manual_commit_consumer, build_producer
from hw08_messages import build_message, deserialize_message, serialize_message

AGENT_TOPICS = {
    "input": "s8844_inbox",
    "planner": "s8844_tasks",
    "writer": "s8844_drafts",
    "reviewer": "s8844_final",
}


async def observe_one(consumer: Any, process: str, topic: str) -> dict[str, Any]:
    """Capture one observed record, including its Kafka location."""
    record = await consumer.__anext__()
    return {
        "process": process,
        "topic": record.topic if hasattr(record, "topic") else topic,
        "partition": record.partition,
        "offset": record.offset,
        "timestamp_ms": record.timestamp,
        "key": record.key.decode("utf-8") if record.key else None,
        "message": deserialize_message(record.value),
    }


async def run_journey(
    *,
    bootstrap_servers: str,
    correlation_id: str,
    data: Mapping[str, Any],
    group_suffix: str,
    message_key: bytes | None = None,
) -> dict[str, Any]:
    """Publish one input and observe one record at each pipeline stage."""
    producer = await build_producer(bootstrap_servers=bootstrap_servers)
    consumers = {
        name: await build_manual_commit_consumer(
            topic,
            group_id=f"s8844-hw8-observer-{name}-{group_suffix}",
            bootstrap_servers=bootstrap_servers,
        )
        for name, topic in AGENT_TOPICS.items()
    }
    producer_started = False
    started_consumers: list[Any] = []
    try:
        await producer.start()
        producer_started = True
        for consumer in consumers.values():
            await consumer.start()
            started_consumers.append(consumer)

        input_message = build_message(
            message_type="agent_request",
            correlation_id=correlation_id,
            data=data,
            timestamp="2026-10-30T08:40:00Z",
        )
        metadata = await producer.send_and_wait(
            AGENT_TOPICS["input"],
            serialize_message(input_message),
            key=message_key,
        )
        observed = {
            name: await asyncio.wait_for(
                observe_one(consumers[name], process, AGENT_TOPICS[name]),
                timeout=30,
            )
            for name, process in (
                ("input", "sender-observer"),
                ("planner", "Planner"),
                ("writer", "Writer"),
                ("reviewer", "Reviewer"),
            )
        }
        return {
            "bootstrap_servers": bootstrap_servers,
            "correlation_id": correlation_id,
            "input": {
                "process": "host-sender",
                "topic": metadata.topic,
                "partition": metadata.partition,
                "offset": metadata.offset,
                "timestamp_ms": getattr(metadata, "timestamp", None),
                "key": message_key.decode("utf-8") if message_key else None,
                "message": input_message,
            },
            "observed": observed,
            "final_output": observed["reviewer"]["message"],
            "automatic_retries": 0,
        }
    finally:
        for consumer in reversed(started_consumers):
            await consumer.stop()
        if producer_started:
            await producer.stop()


def main() -> int:  # pragma: no cover - live execution only
    import asyncio as _asyncio

    result = _asyncio.run(
        run_journey(
            bootstrap_servers="localhost:29092",
            correlation_id="hw8-8844-agent-journey-001",
            data={
                "question": "Which deterministic HW8 pipeline stage produced this answer?"
            },
            group_suffix="20261030-01",
            message_key=None,
        )
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - live execution only
    raise SystemExit(main())
