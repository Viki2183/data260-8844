"""Deterministic Planner/Writer/Reviewer transformations and live adapter."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from hw08_failure_handling import (
    classify_poison_message,
    dead_letter_message,
    poison_attempt_records,
    should_commit_after_dead_letter,
)
from hw08_kafka_config import DEAD_LETTER_TOPIC, DEFAULT_MAX_ATTEMPTS
from hw08_kafka_runtime import build_manual_commit_consumer, build_producer
from hw08_messages import deserialize_message, serialize_message, utc_timestamp


CRASH_HOOK_ENV = "HW8_CRASH_BEFORE_COMMIT_ONCE"
CRASH_MARKER_ENV = "HW8_CRASH_MARKER"
COMMIT_BEFORE_PROCESS_ENV = "HW8_COMMIT_BEFORE_PROCESS"
UNBOUNDED_POISON_ENV = "HW8_UNBOUNDED_POISON"


def stage_event(
    event_type: str,
    *,
    stage: str,
    record: Any,
    message: Mapping[str, Any],
    committed: bool,
    output_topic: str | None = None,
    output_partition: int | None = None,
    output_offset: int | None = None,
) -> dict[str, Any]:
    """Build a safe Writer lifecycle event for later consumer-death evidence."""
    event = {
        "event_type": event_type,
        "process": stage,
        "correlation_id": str(message.get("correlation_id", "")),
        "topic": record.topic,
        "partition": record.partition,
        "offset": record.offset,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "committed": committed,
    }
    if output_topic is not None:
        event.update(
            {
                "output_topic": output_topic,
                "output_partition": output_partition,
                "output_offset": output_offset,
            }
        )
    return event


def poison_event(
    event_type: str,
    *,
    stage: str,
    record: Any,
    message: Mapping[str, Any],
    attempt: int | None = None,
    error_type: str | None = None,
    committed: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    """Build bounded, safe poison lifecycle events for Writer logs."""
    event = stage_event(
        event_type,
        stage=stage,
        record=record,
        message=message,
        committed=committed,
    )
    if attempt is not None:
        event["attempt"] = attempt
    if error_type is not None:
        event["error_type"] = error_type
    event.update(extra)
    return event


def crash_once_before_commit(*, stage: str, marker_path: str | None) -> bool:
    """Consume a one-shot Writer crash hook using a persistent marker."""
    if stage != "writer" or os.getenv(CRASH_HOOK_ENV) != "1" or not marker_path:
        return False
    marker = Path(marker_path)
    marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        marker.touch(exist_ok=False)
    except FileExistsError:
        return False
    return True


def transform_stage(stage: str, message: Mapping[str, Any]) -> dict[str, Any]:
    """Transform one stage without a model call or network access."""
    data = dict(message.get("data", {}))
    correlation_id = str(message.get("correlation_id", ""))
    question = str(data.get("question", data.get("content", "")))
    if stage == "planner":
        output = {"question": question, "plan": f"Plan: answer {question}"}
    elif stage == "writer":
        plan = str(data.get("plan", ""))
        output = {"question": question, "draft": f"Draft based on {plan}"}
    elif stage == "reviewer":
        draft = str(data.get("draft", ""))
        output = {"answer": draft, "status": "approved"}
    else:
        raise ValueError(f"unknown agent stage: {stage}")
    return {
        "message_type": f"{stage}_message",
        "correlation_id": correlation_id,
        "data": output,
        "attempt": int(message.get("attempt", 1)),
        "timestamp": message.get("timestamp", "offline"),
        "metadata": {**dict(message.get("metadata", {})), "stage": stage},
    }


async def run_stage(
    *,
    input_topic: str,
    output_topic: str,
    group_id: str,
    stage: str,
    transform: Callable[[str, Mapping[str, Any]], dict[str, Any]] = transform_stage,
) -> None:  # pragma: no cover - live execution only
    consumer = await build_manual_commit_consumer(
        input_topic,
        group_id=group_id,
        client_id=os.getenv("HW8_WRITER_NAME", stage),
    )
    producer = await build_producer()
    consumer_started = False
    producer_started = False
    try:
        await consumer.start()
        consumer_started = True
        await producer.start()
        producer_started = True
        print(
            json.dumps(
                {
                    "event_type": "consumer_ready",
                    "process": stage,
                    "input_topic": input_topic,
                    "group_id": group_id,
                }
            ),
            flush=True,
        )
        async for record in consumer:
            message = deserialize_message(record.value)
            print(
                json.dumps(
                    stage_event(
                        "message_received",
                        stage=stage,
                        record=record,
                        message=message,
                        committed=False,
                    )
                ),
                flush=True,
            )
            if stage == "writer" and os.getenv(COMMIT_BEFORE_PROCESS_ENV) == "1":
                await consumer.commit()
                print(
                    json.dumps(
                        stage_event(
                            "before_fix_offset_committed_before_process",
                            stage=stage,
                            record=record,
                            message=message,
                            committed=True,
                        )
                    ),
                    flush=True,
                )
            poison_error_type = classify_poison_message(message)
            if poison_error_type is not None:
                if os.getenv(UNBOUNDED_POISON_ENV) == "1":
                    attempt = int(message.get("attempt", 1))
                    while True:
                        print(
                            json.dumps(
                                poison_event(
                                    "before_fix_poison_retry_loop",
                                    stage=stage,
                                    record=record,
                                    message=message,
                                    attempt=attempt,
                                    error_type=poison_error_type,
                                    retry_scheduled=True,
                                    bounded=False,
                                )
                            ),
                            flush=True,
                        )
                        attempt += 1
                        await asyncio.sleep(0.5)
                failures = poison_attempt_records(
                    message,
                    error_type=poison_error_type,
                    max_attempts=DEFAULT_MAX_ATTEMPTS,
                )
                for failure in failures:
                    print(
                        json.dumps(
                            poison_event(
                                "poison_attempt",
                                stage=stage,
                                record=record,
                                message=message,
                                attempt=failure["attempt"],
                                error_type=failure["error_type"],
                                retry_scheduled=failure["retry_scheduled"],
                                max_attempts=DEFAULT_MAX_ATTEMPTS,
                            )
                        ),
                        flush=True,
                    )
                final_attempt = failures[-1]["attempt"]
                dead_letter = dead_letter_message(
                    message,
                    error_type=poison_error_type,
                    source_topic=record.topic,
                    source_partition=record.partition,
                    source_offset=record.offset,
                    attempt=final_attempt,
                    failure_metadata=failures,
                )
                try:
                    dead_letter_metadata = await producer.send_and_wait(
                        DEAD_LETTER_TOPIC,
                        serialize_message(dead_letter),
                    )
                except Exception as exc:
                    print(
                        json.dumps(
                            poison_event(
                                "dead_letter_publish_failed",
                                stage=stage,
                                record=record,
                                message=message,
                                attempt=final_attempt,
                                error_type=type(exc).__name__,
                                failure_classification="dead_letter_publish_failure",
                            )
                        ),
                        flush=True,
                    )
                    raise
                print(
                    json.dumps(
                        poison_event(
                            "dead_letter_published",
                            stage=stage,
                            record=record,
                            message=message,
                            attempt=final_attempt,
                            error_type=poison_error_type,
                            dlt_topic=dead_letter_metadata.topic,
                            dlt_partition=dead_letter_metadata.partition,
                            dlt_offset=dead_letter_metadata.offset,
                            failed_attempts=failures,
                        )
                    ),
                    flush=True,
                )
                if not should_commit_after_dead_letter(published=True):
                    raise RuntimeError("dead-letter publication was not confirmed")
                await consumer.commit()
                print(
                    json.dumps(
                        poison_event(
                            "poison_offset_committed",
                            stage=stage,
                            record=record,
                            message=message,
                            attempt=final_attempt,
                            error_type=poison_error_type,
                            committed=True,
                            committed_offset=record.offset + 1,
                        )
                    ),
                    flush=True,
                )
                continue
            if crash_once_before_commit(
                stage=stage,
                marker_path=os.getenv(CRASH_MARKER_ENV),
            ):
                print(
                    json.dumps(
                        stage_event(
                            "pre_commit_crash",
                            stage=stage,
                            record=record,
                            message=message,
                            committed=False,
                        )
                    ),
                    flush=True,
                )
                os._exit(42)
            output = transform(stage, message)
            output_metadata = dict(output.get("metadata", {}))
            output_metadata.update(
                {
                    "source_topic": record.topic,
                    "source_partition": record.partition,
                    "source_offset": record.offset,
                    "writer_consumer": os.getenv("HW8_WRITER_NAME", stage),
                    "processed_timestamp": utc_timestamp(),
                }
            )
            output["metadata"] = output_metadata
            metadata = await producer.send_and_wait(output_topic, serialize_message(output))
            print(
                json.dumps(
                    stage_event(
                        "output_published",
                        stage=stage,
                        record=record,
                        message=message,
                        committed=False,
                        output_topic=metadata.topic,
                        output_partition=metadata.partition,
                        output_offset=metadata.offset,
                    )
                ),
                flush=True,
            )
            await consumer.commit()
            print(
                json.dumps(
                    stage_event(
                        "offset_committed",
                        stage=stage,
                        record=record,
                        message=message,
                        committed=True,
                    )
                ),
                flush=True,
            )
    finally:
        if consumer_started:
            await consumer.stop()
        if producer_started:
            await producer.stop()

