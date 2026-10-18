"""MongoDB repository functions for the HW6 document API.

Keeping database operations here gives future FastAPI routes a small, clear
interface.  Routes can focus on HTTP concerns while this module handles
MongoDB queries, ObjectId conversion, timestamps, and serialization.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo import DESCENDING
from pymongo.collection import Collection

try:
    from .mongo_database_hw6 import get_hw6_database
    from .schemas_hw6 import DocumentCreate, DocumentUpdate
except ImportError:
    from mongo_database_hw6 import get_hw6_database
    from schemas_hw6 import DocumentCreate, DocumentUpdate


DOCUMENTS_COLLECTION_NAME = "documents"
MAX_DOCUMENT_LIMIT = 100


class InvalidDocumentIdError(ValueError):
    """Raised when a document ID is not a valid MongoDB ObjectId string."""


class DocumentNotFoundError(LookupError):
    """Raised when the requested document does not exist."""


def get_documents_collection() -> Collection[dict[str, Any]]:
    """Return the HW6 documents collection handle on demand.

    Accessing the handle does not explicitly create a collection.  MongoDB
    will create it naturally only when the first document is inserted.
    """

    return get_hw6_database()[DOCUMENTS_COLLECTION_NAME]


def is_valid_document_id(document_id: str) -> bool:
    """Return whether a string can be converted to a MongoDB ObjectId."""

    return isinstance(document_id, str) and ObjectId.is_valid(document_id)


def to_object_id(document_id: str) -> ObjectId:
    """Convert a valid document ID string or raise a clear repository error."""

    if not is_valid_document_id(document_id):
        raise InvalidDocumentIdError(
            f"Invalid document ID: {document_id!r}"
        )

    return ObjectId(document_id)


def _serialize_value(value: Any) -> Any:
    """Convert values used by documents into JSON-friendly representations."""

    if isinstance(value, datetime):
        return value.isoformat()

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


def serialize_document(document: dict[str, Any]) -> dict[str, Any]:
    """Return a document with a string ``id`` and no raw ``_id`` value."""

    serialized = {
        "id": str(document["_id"]),
        "title": document.get("title"),
        "description": document.get("description"),
        "severity": document.get("severity"),
        "status": document.get("status"),
        "document_date": document.get("document_date"),
        "package_code": document.get("package_code"),
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at"),
    }

    return _serialize_value(serialized)


def create_document(payload: DocumentCreate) -> dict[str, Any]:
    """Insert and return one new vulnerability-reporting document."""

    now = datetime.now(timezone.utc)
    document = payload.model_dump()
    document["created_at"] = now
    document["updated_at"] = now

    result = get_documents_collection().insert_one(document)
    document["_id"] = result.inserted_id

    return serialize_document(document)


def _validate_pagination(skip: int, limit: int) -> None:
    """Reject unsafe pagination values before they reach MongoDB."""

    if skip < 0:
        raise ValueError("skip must be zero or greater")

    if limit < 1 or limit > MAX_DOCUMENT_LIMIT:
        raise ValueError(
            f"limit must be between 1 and {MAX_DOCUMENT_LIMIT}"
        )


def list_documents(skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
    """Return documents newest-first with bounded pagination."""

    _validate_pagination(skip, limit)

    cursor = (
        get_documents_collection()
        .find({})
        .sort("created_at", DESCENDING)
        .skip(skip)
        .limit(limit)
    )

    return [serialize_document(document) for document in cursor]


def get_document(document_id: str) -> dict[str, Any]:
    """Return one document or raise a clear not-found error."""

    object_id = to_object_id(document_id)
    document = get_documents_collection().find_one({"_id": object_id})

    if document is None:
        raise DocumentNotFoundError(
            f"Document not found: {document_id}"
        )

    return serialize_document(document)


def update_document(
    document_id: str,
    payload: DocumentUpdate,
) -> dict[str, Any]:
    """Update supplied fields, refresh ``updated_at``, and return the result."""

    object_id = to_object_id(document_id)
    updates = payload.model_dump(exclude_unset=True)
    updates["updated_at"] = datetime.now(timezone.utc)

    result = get_documents_collection().update_one(
        {"_id": object_id},
        {"$set": updates},
    )

    if result.matched_count == 0:
        raise DocumentNotFoundError(
            f"Document not found: {document_id}"
        )

    document = get_documents_collection().find_one({"_id": object_id})

    if document is None:
        raise DocumentNotFoundError(
            f"Document not found after update: {document_id}"
        )

    return serialize_document(document)


def delete_document(document_id: str) -> dict[str, Any]:
    """Delete one document and return its public string ID."""

    object_id = to_object_id(document_id)
    result = get_documents_collection().delete_one({"_id": object_id})

    if result.deleted_count == 0:
        raise DocumentNotFoundError(
            f"Document not found: {document_id}"
        )

    return {
        "id": document_id,
        "deleted": True,
    }
