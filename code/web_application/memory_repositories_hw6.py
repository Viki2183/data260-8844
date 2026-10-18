"""MongoDB repository functions for the DATA 260 Homework 6 memory system."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from bson import ObjectId
from pymongo import DESCENDING
from pymongo.collection import Collection

try:
    from .mongo_database_hw6 import get_hw6_database
except ImportError:  # pragma: no cover - supports direct module imports
    from mongo_database_hw6 import get_hw6_database


MESSAGES_COLLECTION_NAME = "messages"
SUMMARIES_COLLECTION_NAME = "summaries"
EPISODES_COLLECTION_NAME = "episodes"
MAX_MEMORY_LIMIT = 100
MemoryRole = Literal["user", "assistant"]
SummaryScope = Literal["session", "user"]


def get_messages_collection() -> Collection[dict[str, Any]]:
    """Return the messages collection handle when explicitly requested."""

    return get_hw6_database()[MESSAGES_COLLECTION_NAME]


def get_summaries_collection() -> Collection[dict[str, Any]]:
    """Return the summaries collection handle when explicitly requested."""

    return get_hw6_database()[SUMMARIES_COLLECTION_NAME]


def get_episodes_collection() -> Collection[dict[str, Any]]:
    """Return the episodes collection handle when explicitly requested."""

    return get_hw6_database()[EPISODES_COLLECTION_NAME]


def _require_text(value: str, field_name: str) -> str:
    """Reject missing or whitespace-only text before it reaches MongoDB."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must contain meaningful text")
    return value


def _validate_role(role: str) -> MemoryRole:
    """Validate the two roles supported by the memory message model."""

    if role not in {"user", "assistant"}:
        raise ValueError("role must be 'user' or 'assistant'")
    return role  # type: ignore[return-value]


def _validate_scope(scope: str) -> SummaryScope:
    """Validate whether a summary belongs to a session or a user lifetime."""

    if scope not in {"session", "user"}:
        raise ValueError("scope must be 'session' or 'user'")
    return scope  # type: ignore[return-value]


def _validate_limit(limit: int) -> None:
    """Keep memory queries bounded before they reach MongoDB."""

    if limit < 1 or limit > MAX_MEMORY_LIMIT:
        raise ValueError(f"limit must be between 1 and {MAX_MEMORY_LIMIT}")


def _serialize_value(value: Any) -> Any:
    """Convert nested ObjectIds while preserving datetime values for Pydantic."""

    if isinstance(value, ObjectId):
        return str(value)

    if isinstance(value, list):
        return [_serialize_value(item) for item in value]

    if isinstance(value, dict):
        return {
            str(key): _serialize_value(item)
            for key, item in value.items()
        }

    return value


def _serialize_record(record: dict[str, Any]) -> dict[str, Any]:
    """Return a record with public ``id`` and no raw MongoDB ``_id``."""

    serialized = {
        "id": str(record["_id"]),
        **{
            key: value
            for key, value in record.items()
            if key != "_id"
        },
    }
    return _serialize_value(serialized)


def serialize_message(message: dict[str, Any]) -> dict[str, Any]:
    """Serialize a stored message for response schemas."""

    return _serialize_record(message)


def serialize_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Serialize a stored summary for response schemas."""

    return _serialize_record(summary)


def serialize_episode(episode: dict[str, Any]) -> dict[str, Any]:
    """Serialize a stored episode without exposing its raw ObjectId."""

    return _serialize_record(episode)


def save_message(
    user_id: str,
    session_id: str,
    role: str,
    content: str,
    token_count: int | None = None,
    latency_ms: float | None = None,
    memory_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Store one chat message and return its serialized representation."""

    document: dict[str, Any] = {
        "user_id": _require_text(user_id, "user_id"),
        "session_id": _require_text(session_id, "session_id"),
        "role": _validate_role(role),
        "content": _require_text(content, "content"),
        "created_at": datetime.now(timezone.utc),
    }

    if token_count is not None:
        if token_count < 0:
            raise ValueError("token_count must be zero or greater")
        document["token_count"] = token_count

    if latency_ms is not None:
        if latency_ms < 0:
            raise ValueError("latency_ms must be zero or greater")
        document["latency_ms"] = latency_ms

    if memory_refs is not None:
        document["memory_refs"] = list(memory_refs)

    result = get_messages_collection().insert_one(document)
    document["_id"] = result.inserted_id
    return serialize_message(document)


def load_short_term_messages(
    user_id: str,
    session_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    """Load a bounded newest window and return it in conversation order."""

    _validate_limit(limit)
    cursor = (
        get_messages_collection()
        .find({"user_id": _require_text(user_id, "user_id"), "session_id": _require_text(session_id, "session_id")})
        .sort("created_at", DESCENDING)
        .limit(limit)
    )
    messages = [serialize_message(message) for message in cursor]
    return list(reversed(messages))


def count_user_messages(user_id: str, session_id: str) -> int:
    """Count only user-authored messages in one user/session pair."""

    return get_messages_collection().count_documents(
        {
            "user_id": _require_text(user_id, "user_id"),
            "session_id": _require_text(session_id, "session_id"),
            "role": "user",
        }
    )


def save_summary(
    user_id: str,
    session_id: str | None,
    scope: str,
    text: str,
    source_message_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Store a session or lifetime summary with creation and update times."""

    validated_scope = _validate_scope(scope)
    if validated_scope == "session" and session_id is None:
        raise ValueError("session summaries require a session_id")

    document: dict[str, Any] = {
        "user_id": _require_text(user_id, "user_id"),
        "session_id": (
            _require_text(session_id, "session_id")
            if session_id is not None
            else None
        ),
        "scope": validated_scope,
        "text": _require_text(text, "text"),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    if source_message_ids is not None:
        document["source_message_ids"] = list(source_message_ids)

    result = get_summaries_collection().insert_one(document)
    document["_id"] = result.inserted_id
    return serialize_summary(document)


def get_latest_session_summary(
    user_id: str,
    session_id: str,
) -> dict[str, Any] | None:
    """Return the newest session summary for the requested user/session."""

    summary = get_summaries_collection().find_one(
        {
            "user_id": _require_text(user_id, "user_id"),
            "session_id": _require_text(session_id, "session_id"),
            "scope": "session",
        },
        sort=[("updated_at", DESCENDING), ("created_at", DESCENDING)],
    )
    return serialize_summary(summary) if summary is not None else None


def get_latest_lifetime_summary(user_id: str) -> dict[str, Any] | None:
    """Return the newest user-lifetime summary with a null session ID."""

    summary = get_summaries_collection().find_one(
        {
            "user_id": _require_text(user_id, "user_id"),
            "session_id": None,
            "scope": "user",
        },
        sort=[("updated_at", DESCENDING), ("created_at", DESCENDING)],
    )
    return serialize_summary(summary) if summary is not None else None


def list_recent_summaries(
    user_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return a bounded newest-first list of summaries for one user."""

    _validate_limit(limit)
    cursor = (
        get_summaries_collection()
        .find({"user_id": _require_text(user_id, "user_id")})
        .sort("updated_at", DESCENDING)
        .limit(limit)
    )
    return [serialize_summary(summary) for summary in cursor]


def save_episode(
    user_id: str,
    session_id: str | None,
    fact: str,
    importance: float,
    embedding: list[float],
    source_message_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Store one extracted fact and its caller-provided embedding."""

    if importance < 0.0 or importance > 1.0:
        raise ValueError("importance must be between 0.0 and 1.0")

    document: dict[str, Any] = {
        "user_id": _require_text(user_id, "user_id"),
        "session_id": (
            _require_text(session_id, "session_id")
            if session_id is not None
            else None
        ),
        "fact": _require_text(fact, "fact"),
        "importance": importance,
        "embedding": [float(value) for value in embedding],
        "created_at": datetime.now(timezone.utc),
    }
    if source_message_ids is not None:
        document["source_message_ids"] = list(source_message_ids)

    result = get_episodes_collection().insert_one(document)
    document["_id"] = result.inserted_id
    return serialize_episode(document)


def list_recent_episodes(
    user_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return recent episodic facts for one user, newest first."""

    _validate_limit(limit)
    cursor = (
        get_episodes_collection()
        .find({"user_id": _require_text(user_id, "user_id")})
        .sort("created_at", DESCENDING)
        .limit(limit)
    )
    return [serialize_episode(episode) for episode in cursor]


def list_all_episodes_for_user(
    user_id: str,
    limit: int = MAX_MEMORY_LIMIT,
) -> list[dict[str, Any]]:
    """Return bounded episodes with embeddings for later similarity search."""

    _validate_limit(limit)
    cursor = (
        get_episodes_collection()
        .find({"user_id": _require_text(user_id, "user_id"), "embedding": {"$exists": True}})
        .sort("created_at", DESCENDING)
        .limit(limit)
    )
    return [serialize_episode(episode) for episode in cursor]


def get_daily_message_counts(user_id: str) -> list[dict[str, Any]]:
    """Group one user's messages by their UTC calendar date."""

    pipeline = [
        {"$match": {"user_id": _require_text(user_id, "user_id")}},
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": "$created_at",
                        "timezone": "UTC",
                    }
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": DESCENDING}},
    ]
    return [
        {"date": item["_id"], "count": item["count"]}
        for item in get_messages_collection().aggregate(pipeline)
    ]


def get_recent_summaries_for_user(
    user_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Return recent summaries for aggregate responses, newest first."""

    return list_recent_summaries(user_id=user_id, limit=limit)


__all__ = [
    "EPISODES_COLLECTION_NAME",
    "MAX_MEMORY_LIMIT",
    "MESSAGES_COLLECTION_NAME",
    "SUMMARIES_COLLECTION_NAME",
    "count_user_messages",
    "get_daily_message_counts",
    "get_latest_lifetime_summary",
    "get_latest_session_summary",
    "get_messages_collection",
    "get_episodes_collection",
    "get_recent_summaries_for_user",
    "get_summaries_collection",
    "list_all_episodes_for_user",
    "list_recent_episodes",
    "list_recent_summaries",
    "load_short_term_messages",
    "save_episode",
    "save_message",
    "save_summary",
    "serialize_episode",
    "serialize_message",
    "serialize_summary",
]
