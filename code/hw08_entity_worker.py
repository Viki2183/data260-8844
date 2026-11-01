"""Pure HW8 entity-worker processing functions.

Kafka consumption and offset commits are deferred to a later phase.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping
from typing import Any

from hw08_kafka_config import ENTITY_RESPONSES_TOPIC, ENTITY_REQUESTS_TOPIC, ENTITY_CONSUMER_GROUP
from hw08_kafka_runtime import build_manual_commit_consumer, build_producer
from hw08_entity_store import EntityStore
from hw08_entity_validation import validate_vulnerability_report
from hw08_messages import build_response, deserialize_message, serialize_message

CREATE_ENTITY = "CREATE_ENTITY"
GET_ENTITY = "GET_ENTITY"
DOMAIN_CREATE_OPERATION = "CREATE_VULNERABILITY_REPORT"
DOMAIN_GET_OPERATION = "GET_VULNERABILITY_REPORT"
CREATE_OPERATION = CREATE_ENTITY
GET_OPERATION = GET_ENTITY


def process_entity_message(
    message: Mapping[str, Any],
    store: EntityStore,
    *,
    uuid_factory: Callable[[], uuid.UUID] = uuid.uuid4,
) -> dict[str, Any]:
    cached = store.get_cached_response(message)
    if cached is not None:
        cached["metadata"] = {**cached.get("metadata", {}), "duplicate": True}
        return cached

    operation = message.get("operation")
    data = message.get("data")
    if not isinstance(data, Mapping):
        response = build_response(message, success=False, error="data must be an object")
        store.cache_response(message, response)
        return response

    if operation in {CREATE_ENTITY, DOMAIN_CREATE_OPERATION}:
        errors = validate_vulnerability_report(data)
        if errors:
            response = build_response(message, success=False, error="; ".join(errors))
        else:
            entity_id = str(uuid_factory())
            entity = store.create(entity_id, data)
            response = build_response(
                message, success=True, data={"entity": entity}, entity_id=entity_id
            )
    elif operation in {GET_ENTITY, DOMAIN_GET_OPERATION}:
        entity_id = data.get("entity_id") or message.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id:
            response = build_response(message, success=False, error="entity_id is required")
        else:
            entity = store.get(entity_id)
            if entity is None:
                response = build_response(
                    message, success=False, error="Entity not found", entity_id=entity_id
                )
            else:
                response = build_response(
                    message, success=True, data={"entity": entity}, entity_id=entity_id
                )
    else:
        response = build_response(message, success=False, error="Unknown operation")

    store.cache_response(message, response)
    return response


class EntityKafkaWorker:
    """Live Kafka adapter with manual commit after response publication."""

    def __init__(self, producer: Any, consumer: Any, store: EntityStore | None = None) -> None:
        self.producer = producer
        self.consumer = consumer
        self.store = store or EntityStore()

    async def process_record(
        self,
        record: Any,
        *,
        uuid_factory: Callable[[], uuid.UUID] = uuid.uuid4,
    ) -> dict[str, Any]:
        message = deserialize_message(record.value if hasattr(record, "value") else record)
        print(
            json.dumps(
                {
                    "event": "entity_request_received",
                    "topic": getattr(record, "topic", ENTITY_REQUESTS_TOPIC),
                    "partition": getattr(record, "partition", None),
                    "offset": getattr(record, "offset", None),
                    "correlation_id": message.get("correlation_id"),
                    "operation": message.get("operation"),
                    "request": message,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        response = process_entity_message(message, self.store, uuid_factory=uuid_factory)
        metadata = await self.producer.send_and_wait(
            ENTITY_RESPONSES_TOPIC, serialize_message(response)
        )
        print(
            json.dumps(
                {
                    "event": "entity_response_published",
                    "topic": metadata.topic,
                    "partition": metadata.partition,
                    "offset": metadata.offset,
                    "correlation_id": response.get("correlation_id"),
                    "operation": response.get("operation"),
                    "response": response,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        await self.consumer.commit()
        print(
            json.dumps(
                {
                    "event": "entity_source_offset_committed",
                    "topic": getattr(record, "topic", ENTITY_REQUESTS_TOPIC),
                    "partition": getattr(record, "partition", None),
                    "offset": getattr(record, "offset", None),
                    "correlation_id": response.get("correlation_id"),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return response

    async def run(self) -> None:  # pragma: no cover - live execution only
        producer_started = False
        consumer_started = False
        try:
            await self.producer.start()
            producer_started = True
            await self.consumer.start()
            consumer_started = True
            print(
                "Consumer is ready and listening on s8844_entity_requests",
                flush=True,
            )
            async for record in self.consumer:
                await self.process_record(record)
        finally:
            if consumer_started:
                await self.consumer.stop()
            if producer_started:
                await self.producer.stop()


async def build_live_worker() -> EntityKafkaWorker:
    return EntityKafkaWorker(
        await build_producer(),
        await build_manual_commit_consumer(
            ENTITY_REQUESTS_TOPIC,
            group_id=ENTITY_CONSUMER_GROUP,
        ),
    )


if __name__ == "__main__":  # pragma: no cover - live execution only
    import asyncio

    async def main() -> None:
        worker = await build_live_worker()
        await worker.run()

    asyncio.run(main())

