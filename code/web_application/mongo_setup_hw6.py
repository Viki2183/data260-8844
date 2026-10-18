"""MongoDB collection validation and index setup for DATA 260 Homework 6."""

from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, DESCENDING
from pymongo.database import Database
from pymongo.errors import PyMongoError

try:
    from .mongo_database_hw6 import get_hw6_database
except ImportError:  # pragma: no cover - supports direct module imports
    from mongo_database_hw6 import get_hw6_database


DOCUMENTS_COLLECTION_NAME = "documents"

# Pydantic validates incoming API requests, while this validator protects the
# collection from malformed writes made by scripts, migrations, or other
# clients that bypass FastAPI.
DOCUMENT_VALIDATOR: dict[str, Any] = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": [
            "title",
            "severity",
            "status",
            "document_date",
            "created_at",
            "updated_at",
        ],
        "properties": {
            "title": {
                "bsonType": "string",
                "minLength": 1,
                "maxLength": 100,
            },
            "description": {
                "bsonType": ["string", "null"],
                "maxLength": 2000,
            },
            "severity": {
                "bsonType": "string",
                "enum": ["Critical", "High", "Medium", "Low"],
            },
            "status": {
                "bsonType": "string",
                "enum": ["Open", "Resolved", "Accepted", "Rejected"],
            },
            "document_date": {"bsonType": "date"},
            "package_code": {
                "bsonType": ["string", "null"],
                "maxLength": 100,
            },
            "created_at": {"bsonType": "date"},
            "updated_at": {"bsonType": "date"},
        },
    }
}

INDEX_DEFINITIONS: tuple[tuple[str, str, int], ...] = (
    ("created_at_desc", "created_at", DESCENDING),
    ("severity_asc", "severity", ASCENDING),
    ("status_asc", "status", ASCENDING),
    ("document_date_desc", "document_date", DESCENDING),
)


def ensure_documents_collection() -> dict[str, Any]:
    """Create or update the documents collection and ensure its indexes.

    This function is deliberately explicit and is never called during module
    import.  Updating an existing validator uses ``collMod`` and does not
    delete or replace existing documents.
    """

    database: Database[Any] = get_hw6_database()
    collection_names = database.list_collection_names()
    collection_created = DOCUMENTS_COLLECTION_NAME not in collection_names

    if collection_created:
        database.create_collection(
            DOCUMENTS_COLLECTION_NAME,
            validator=DOCUMENT_VALIDATOR,
            validationLevel="strict",
            validationAction="error",
        )
    else:
        database.command(
            "collMod",
            DOCUMENTS_COLLECTION_NAME,
            validator=DOCUMENT_VALIDATOR,
            validationLevel="strict",
            validationAction="error",
        )

    collection = database[DOCUMENTS_COLLECTION_NAME]
    existing_indexes = collection.index_information()
    indexes_ensured: list[str] = []

    for index_name, field_name, direction in INDEX_DEFINITIONS:
        if index_name not in existing_indexes:
            collection.create_index(
                [(field_name, direction)],
                name=index_name,
            )
        indexes_ensured.append(index_name)

    return {
        "database": database.name,
        "collection": DOCUMENTS_COLLECTION_NAME,
        "collection_created": collection_created,
        "indexes_ensured": indexes_ensured,
    }


__all__ = [
    "DOCUMENTS_COLLECTION_NAME",
    "DOCUMENT_VALIDATOR",
    "INDEX_DEFINITIONS",
    "ensure_documents_collection",
    "PyMongoError",
]
