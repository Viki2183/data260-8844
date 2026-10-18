"""MongoDB validators and indexes for the DATA 260 HW6 memory system."""

from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, DESCENDING

try:
    from .mongo_database_hw6 import get_hw6_database
except ImportError:  # pragma: no cover - supports direct module imports
    from mongo_database_hw6 import get_hw6_database


MESSAGES_COLLECTION_NAME = "messages"
SUMMARIES_COLLECTION_NAME = "summaries"
EPISODES_COLLECTION_NAME = "episodes"

# Pydantic protects normal API requests.  These MongoDB validators provide a
# second boundary for scripts or other writers that bypass the FastAPI layer.
MESSAGES_VALIDATOR: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "user_id",
            "session_id",
            "role",
            "content",
            "created_at",
        ],
        "properties": {
            "user_id": {"bsonType": "string", "maxLength": 200},
            "session_id": {"bsonType": "string", "maxLength": 200},
            "role": {
                "bsonType": "string",
                "enum": ["user", "assistant"],
            },
            "content": {"bsonType": "string", "maxLength": 10000},
            "created_at": {"bsonType": "date"},
            "token_count": {"bsonType": "number", "minimum": 0},
            "latency_ms": {"bsonType": "number", "minimum": 0},
        },
    }
}

SUMMARIES_VALIDATOR: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["user_id", "scope", "text", "created_at"],
        "properties": {
            "user_id": {"bsonType": "string", "maxLength": 200},
            "session_id": {
                "bsonType": ["string", "null"],
                "maxLength": 200,
            },
            "scope": {
                "bsonType": "string",
                "enum": ["session", "user"],
            },
            "text": {"bsonType": "string", "maxLength": 10000},
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
        },
    }
}

EPISODES_VALIDATOR: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "user_id",
            "fact",
            "importance",
            "embedding",
            "created_at",
        ],
        "properties": {
            "user_id": {"bsonType": "string", "maxLength": 200},
            "session_id": {
                "bsonType": ["string", "null"],
                "maxLength": 200,
            },
            "fact": {"bsonType": "string", "maxLength": 2000},
            "importance": {
                "bsonType": "number",
                "minimum": 0.0,
                "maximum": 1.0,
            },
            "embedding": {
                "bsonType": "array",
                "items": {"bsonType": "number"},
            },
            "created_at": {"bsonType": "date"},
        },
    }
}

# Named compound indexes make the intended access patterns visible when the
# collection is inspected and keep common memory queries bounded and quick.
MEMORY_INDEXES: dict[str, tuple[tuple[str, tuple[tuple[str, int], ...]], ...]] = {
    MESSAGES_COLLECTION_NAME: (
        (
            "messages_user_session_created_desc",
            (("user_id", ASCENDING), ("session_id", ASCENDING), ("created_at", DESCENDING)),
        ),
        (
            "messages_user_created_desc",
            (("user_id", ASCENDING), ("created_at", DESCENDING)),
        ),
        (
            "messages_role_asc",
            (("role", ASCENDING),),
        ),
    ),
    SUMMARIES_COLLECTION_NAME: (
        (
            "summaries_user_scope_created_desc",
            (("user_id", ASCENDING), ("scope", ASCENDING), ("created_at", DESCENDING)),
        ),
        (
            "summaries_user_session_created_desc",
            (("user_id", ASCENDING), ("session_id", ASCENDING), ("created_at", DESCENDING)),
        ),
    ),
    EPISODES_COLLECTION_NAME: (
        (
            "episodes_user_created_desc",
            (("user_id", ASCENDING), ("created_at", DESCENDING)),
        ),
        (
            "episodes_user_importance_desc",
            (("user_id", ASCENDING), ("importance", DESCENDING)),
        ),
    ),
}

MEMORY_VALIDATORS: dict[str, dict[str, Any]] = {
    MESSAGES_COLLECTION_NAME: MESSAGES_VALIDATOR,
    SUMMARIES_COLLECTION_NAME: SUMMARIES_VALIDATOR,
    EPISODES_COLLECTION_NAME: EPISODES_VALIDATOR,
}


def ensure_memory_collections() -> dict[str, Any]:
    """Create or update memory collections and ensure their indexes.

    Setup is explicit so importing a route or repository never unexpectedly
    creates collections, changes validators, or performs database writes.
    Existing collections are updated with ``collMod`` without deleting data.
    """

    database = get_hw6_database()
    existing_collections = set(database.list_collection_names())
    created_collections: list[str] = []
    indexes_ensured: dict[str, list[str]] = {}

    for collection_name, validator in MEMORY_VALIDATORS.items():
        if collection_name not in existing_collections:
            database.create_collection(
                collection_name,
                validator=validator,
                validationLevel="strict",
                validationAction="error",
            )
            created_collections.append(collection_name)
        else:
            database.command(
                "collMod",
                collection_name,
                validator=validator,
                validationLevel="strict",
                validationAction="error",
            )

        collection = database[collection_name]
        existing_indexes = collection.index_information()
        indexes_ensured[collection_name] = []

        for index_name, keys in MEMORY_INDEXES[collection_name]:
            if index_name not in existing_indexes:
                collection.create_index(list(keys), name=index_name)
            indexes_ensured[collection_name].append(index_name)

    return {
        "database": database.name,
        "collections_processed": list(MEMORY_VALIDATORS),
        "created_collections": created_collections,
        "indexes_ensured": indexes_ensured,
    }


__all__ = [
    "EPISODES_COLLECTION_NAME",
    "EPISODES_VALIDATOR",
    "MEMORY_INDEXES",
    "MEMORY_VALIDATORS",
    "MESSAGES_COLLECTION_NAME",
    "MESSAGES_VALIDATOR",
    "SUMMARIES_COLLECTION_NAME",
    "SUMMARIES_VALIDATOR",
    "ensure_memory_collections",
]
