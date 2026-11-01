"""Deterministic HW8 ordering-workload and record helpers."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

from hw08_kafka_config import ORDERING_MESSAGE_COUNT, VERIFY_SEED
from hw08_messages import build_message


@dataclass(frozen=True)
class OrderingRecord:
    partition: int
    offset: int
    consumer: str
    sequence: int
    key: str | None
    processing_order: int


def generate_ordering_messages(
    *,
    seed: int = VERIFY_SEED,
    count: int = ORDERING_MESSAGE_COUNT,
    keyed: bool,
) -> list[dict[str, Any]]:
    if count != ORDERING_MESSAGE_COUNT:
        raise ValueError("HW8 ordering experiment requires exactly 20 messages")
    rng = random.Random(seed)
    key = f"entity-{seed}" if keyed else None
    messages = []
    for sequence in range(count):
        message = build_message(
            message_type="ordering_test",
            correlation_id=f"ordering-{seed}-{sequence:02d}",
            operation="ORDERING_TEST",
            data={"entity_id": key or f"entity-{rng.randrange(2)}", "sequence": sequence},
            attempt=1,
            timestamp="deterministic",
            metadata={"seed": seed, "sequence": sequence, "key": key},
        )
        message["key"] = key
        messages.append(message)
    return messages


def record_processing(
    *,
    partition: int,
    offset: int,
    consumer: str,
    sequence: int,
    key: str | None,
    processing_order: int,
) -> OrderingRecord:
    return OrderingRecord(partition, offset, consumer, sequence, key, processing_order)


def records_to_rows(records: list[OrderingRecord]) -> list[dict[str, Any]]:
    return [record.__dict__.copy() for record in records]

