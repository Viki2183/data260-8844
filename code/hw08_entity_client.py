"""Kafka entity client; request construction is testable without Kafka."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterable, Mapping
from typing import Any

from hw08_kafka_config import ENTITY_REQUESTS_TOPIC, ENTITY_RESPONSES_TOPIC
from hw08_kafka_runtime import build_manual_commit_consumer, build_producer
from hw08_messages import (
    build_entity_request,
    deserialize_message,
    serialize_message,
)

CREATE_ENTITY = "CREATE_ENTITY"
GET_ENTITY = "GET_ENTITY"


class EntityKafkaClient:
    """Publish one request and wait only for its matching correlation ID."""

    def __init__(
        self,
        producer: Any,
        response_consumer: AsyncIterable[Any],
        *,
        request_topic: str = ENTITY_REQUESTS_TOPIC,
        response_topic: str = ENTITY_RESPONSES_TOPIC,
    ) -> None:
        self.producer = producer
        self.response_consumer = response_consumer
        self.request_topic = request_topic
        self.response_topic = response_topic

    def create_request(self, correlation_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
        return build_entity_request(
            correlation_id=correlation_id,
            reply_to=self.response_topic,
            operation=CREATE_ENTITY,
            data=data,
        )

    def get_request(self, correlation_id: str, entity_id: str) -> dict[str, Any]:
        return build_entity_request(
            correlation_id=correlation_id,
            reply_to=self.response_topic,
            operation=GET_ENTITY,
            data={"entity_id": entity_id},
            entity_id=entity_id,
        )

    async def publish(self, request: Mapping[str, Any]) -> None:
        """Publish exactly once; this method performs no automatic retry."""
        await self.producer.send_and_wait(self.request_topic, serialize_message(request))

    async def wait_for_response(
        self, correlation_id: str, *, timeout_seconds: float | None = None
    ) -> dict[str, Any]:
        async def receive() -> dict[str, Any]:
            async for record in self.response_consumer:
                value = record.value if hasattr(record, "value") else record
                message = deserialize_message(value)
                if message.get("correlation_id") == correlation_id:
                    return message
            raise RuntimeError("response consumer ended before the matching response arrived")

        if timeout_seconds is None:
            return await receive()
        return await asyncio.wait_for(receive(), timeout=timeout_seconds)

    @classmethod
    async def live_defaults(cls) -> "EntityKafkaClient":
        """Construct live dependencies; intentionally unused until later approval."""
        producer = await build_producer()
        consumer = await build_manual_commit_consumer(
            ENTITY_RESPONSES_TOPIC,
            group_id="s8844-entity-client",
        )
        return cls(producer, consumer)

