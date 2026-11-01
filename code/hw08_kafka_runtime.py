"""Lazy Kafka runtime adapters for HW8.

Importing this module is offline-safe.  The aiokafka dependency is imported
only when a live runtime is explicitly started in a later phase.
"""

from __future__ import annotations

from typing import Any

from hw08_kafka_config import KAFKA_BOOTSTRAP_SERVERS


def require_aiokafka() -> tuple[Any, Any]:
    try:
        from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
    except ImportError as exc:  # pragma: no cover - live environment only
        raise RuntimeError("aiokafka is required only for live HW8 execution") from exc
    return AIOKafkaConsumer, AIOKafkaProducer


async def build_producer(
    *, bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS, **kwargs: Any
) -> Any:
    """Construct a producer while an asyncio runtime is active."""
    _, producer_type = require_aiokafka()
    return producer_type(bootstrap_servers=bootstrap_servers, **kwargs)


async def build_manual_commit_consumer(
    topic: str,
    *,
    group_id: str,
    bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS,
    **kwargs: Any,
) -> Any:
    """Construct a consumer while an asyncio runtime is active."""
    consumer_type, _ = require_aiokafka()
    return consumer_type(
        topic,
        bootstrap_servers=bootstrap_servers,
        group_id=group_id,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        **kwargs,
    )

