"""Small Redis adapter for HW9 with centralized namespace validation."""

from __future__ import annotations

import os
from typing import Any

PREFIX = "s8844:"
_client: Any | None = None


class RedisUnavailableError(RuntimeError):
    """Raised when the optional Redis service cannot be used."""


def validate_key(key: str) -> str:
    if not key.startswith(PREFIX):
        raise ValueError(f"Redis key must begin with {PREFIX!r}: {key!r}")
    return key


def make_key(namespace: str, *parts: object) -> str:
    """Build and validate every HW9 Redis key in one place."""
    clean_namespace = namespace.strip(":")
    suffix = ":".join(str(part) for part in parts)
    key = f"{PREFIX}{clean_namespace}"
    if suffix:
        key = f"{key}:{suffix}"
    return validate_key(key)


def get_redis_client() -> Any:
    """Return a lazy Redis client without contacting Redis during import."""
    global _client
    if _client is not None:
        return _client
    try:
        import redis
    except ImportError as exc:  # pragma: no cover - depends on deployment image
        raise RedisUnavailableError("Python redis package is not installed") from exc

    host = os.getenv("HW9_REDIS_HOST", os.getenv("REDIS_HOST", "127.0.0.1"))
    port = int(os.getenv("HW9_REDIS_PORT", os.getenv("REDIS_PORT", "6379")))
    # Binary responses are required for RediSearch FLOAT32 vector fields.
    _client = redis.Redis(host=host, port=port, decode_responses=False)
    try:
        _client.ping()
    except Exception as exc:  # pragma: no cover - depends on live Redis
        _client = None
        raise RedisUnavailableError(f"Redis is unavailable at {host}:{port}") from exc
    return _client


def reset_client_for_tests() -> None:
    """Clear the process-local connection handle; never flushes Redis."""
    global _client
    _client = None
