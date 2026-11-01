"""Canonical, dependency-free DATA260 HW8 message helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Mapping


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_message(
    *,
    message_type: str,
    correlation_id: str,
    operation: str | None = None,
    data: Mapping[str, Any] | None = None,
    reply_to: str | None = None,
    entity_id: str | None = None,
    attempt: int = 1,
    timestamp: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the official HW8 envelope without contacting Kafka."""
    if not correlation_id:
        raise ValueError("correlation_id must be non-empty")
    if attempt < 1:
        raise ValueError("attempt must be at least 1")
    message: dict[str, Any] = {
        "message_type": message_type,
        "correlation_id": correlation_id,
        "data": dict(data or {}),
        "attempt": attempt,
        "timestamp": timestamp if timestamp is not None else utc_timestamp(),
        "metadata": dict(metadata or {}),
    }
    if operation is not None:
        message["operation"] = operation
    if reply_to is not None:
        message["reply_to"] = reply_to
    if entity_id is not None:
        message["entity_id"] = entity_id
    return message


def build_entity_request(
    *,
    correlation_id: str,
    reply_to: str,
    operation: str,
    data: Mapping[str, Any],
    entity_id: str | None = None,
    attempt: int = 1,
    timestamp: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return build_message(
        message_type="entity_request",
        correlation_id=correlation_id,
        operation=operation,
        data=data,
        reply_to=reply_to,
        entity_id=entity_id,
        attempt=attempt,
        timestamp=timestamp,
        metadata=metadata,
    )


def build_response(
    request: Mapping[str, Any],
    *,
    success: bool,
    data: Mapping[str, Any] | None = None,
    entity_id: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Build a response while preserving the request correlation ID."""
    response = build_message(
        message_type="entity_response",
        correlation_id=str(request.get("correlation_id", "")),
        operation=request.get("operation"),
        data=data,
        entity_id=entity_id,
        attempt=int(request.get("attempt", 1)),
        timestamp=request.get("timestamp"),
        metadata={"response_to": request.get("message_type", "")},
    )
    response["success"] = success
    if error is not None:
        response["error"] = error
    return response


def idempotency_key(message: Mapping[str, Any]) -> tuple[str, str, str, str]:
    data = message.get("data")
    data_entity_id = data.get("entity_id") if isinstance(data, Mapping) else None
    return (
        str(message.get("message_type", "")),
        str(message.get("correlation_id", "")),
        str(message.get("operation", "")),
        str(message.get("entity_id") or data_entity_id or ""),
    )


def serialize_message(message: Mapping[str, Any]) -> bytes:
    """Serialize one envelope deterministically for Kafka transport."""
    return json.dumps(dict(message), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def deserialize_message(value: bytes | str) -> dict[str, Any]:
    """Decode and minimally validate a Kafka envelope without side effects."""
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    message = json.loads(value)
    if not isinstance(message, dict):
        raise ValueError("Kafka message must decode to an object")
    for field in ("message_type", "correlation_id", "data", "attempt"):
        if field not in message:
            raise ValueError(f"Kafka message missing {field}")
    return message

