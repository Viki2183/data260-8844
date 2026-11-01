"""Isolated HW8 FastAPI facade for the Kafka entity request/response flow."""

from __future__ import annotations

from contextlib import asynccontextmanager
import json
import os
from typing import Any

from fastapi import FastAPI, Header

from hw08_entity_client import EntityKafkaClient
from hw08_kafka_config import (
    ENTITY_REQUESTS_TOPIC,
    ENTITY_RESPONSES_TOPIC,
    KAFKA_BOOTSTRAP_SERVERS,
)
from hw08_kafka_runtime import build_manual_commit_consumer, build_producer
from hw08_messages import build_entity_request, build_message

_client: EntityKafkaClient | None = None
_producer: Any = None
_consumer: Any = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _client, _producer, _consumer
    _producer = await build_producer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    _consumer = await build_manual_commit_consumer(
        ENTITY_RESPONSES_TOPIC,
        group_id="s8844-api-client",
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    )
    await _producer.start()
    await _consumer.start()
    _client = EntityKafkaClient(_producer, _consumer)
    print(
        "FastAPI server started at http://127.0.0.1:8744",
        flush=True,
    )
    try:
        yield
    finally:
        if _consumer is not None:
            await _consumer.stop()
        if _producer is not None:
            await _producer.stop()
        _client = None
        _producer = None
        _consumer = None


app = FastAPI(
    title="DATA260 HW8 Vulnerability Entity API",
    version="8.0.0",
    lifespan=lifespan,
)


def _correlation(header: str | None, fallback: str) -> str:
    return header.strip() if header and header.strip() else fallback


async def _request(request: dict[str, Any]) -> dict[str, Any]:
    if _client is None:
        raise RuntimeError("Kafka API client is not ready")
    await _client.publish(request)
    print(
        json.dumps(
            {
                "event": "api_request_published",
                "topic": ENTITY_REQUESTS_TOPIC,
                "correlation_id": request.get("correlation_id"),
                "operation": request.get("operation"),
                "request": request,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    response = await _client.wait_for_response(
        str(request["correlation_id"]), timeout_seconds=30.0
    )
    print(
        json.dumps(
            {
                "event": "api_response_received",
                "topic": ENTITY_RESPONSES_TOPIC,
                "correlation_id": response.get("correlation_id"),
                "operation": response.get("operation"),
                "response": response,
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "hw08-api"}


@app.post("/hw8/entity")
async def create_entity(
    payload: dict[str, Any],
    x_correlation_id: str | None = Header(default=None),
) -> dict[str, Any]:
    correlation_id = _correlation(x_correlation_id, "hw8-8844-api-create-001")
    request = build_entity_request(
        correlation_id=correlation_id,
        reply_to=ENTITY_RESPONSES_TOPIC,
        operation="CREATE_ENTITY",
        data=payload,
    )
    response = await _request(request)
    return {"request": request, "response": response}


@app.get("/hw8/entity/{entity_id}")
async def get_entity(
    entity_id: str,
    x_correlation_id: str | None = Header(default=None),
) -> dict[str, Any]:
    correlation_id = _correlation(x_correlation_id, "hw8-8844-api-get-001")
    request = build_entity_request(
        correlation_id=correlation_id,
        reply_to=ENTITY_RESPONSES_TOPIC,
        operation="GET_ENTITY",
        data={"entity_id": entity_id},
        entity_id=entity_id,
    )
    response = await _request(request)
    return {"request": request, "response": response}


@app.post("/hw8/entity/raw")
async def raw_entity_request(
    payload: dict[str, Any],
    x_correlation_id: str | None = Header(default=None),
) -> dict[str, Any]:
    correlation_id = _correlation(x_correlation_id, "hw8-8844-api-raw-001")
    request = build_message(
        message_type=str(payload.get("message_type", "entity_request")),
        correlation_id=correlation_id,
        operation=payload.get("operation"),
        data=payload.get("data", {}),
        reply_to=ENTITY_RESPONSES_TOPIC,
        entity_id=payload.get("entity_id"),
        attempt=int(payload.get("attempt", 1)),
        timestamp=payload.get("timestamp"),
        metadata=payload.get("metadata", {}),
    )
    response = await _request(request)
    return {"request": request, "response": response}


if __name__ == "__main__":  # pragma: no cover - live entry point
    import uvicorn

    uvicorn.run(
        "hw08_api:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT_BASE", "8744")),
        reload=False,
    )
