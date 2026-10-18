"""Small MongoDB infrastructure helpers for DATA 260 Homework 6.

This module is intentionally separate from ``database.py``.  The existing
application uses SQLAlchemy and MySQL for its vulnerability-reporting data;
HW6 uses MongoDB for new document and memory features without changing that
established database boundary.
"""

from __future__ import annotations

import os
from typing import Any

from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError


MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://127.0.0.1:27017",
)
MONGODB_DB_NAME = os.getenv(
    "MONGODB_DB_NAME",
    "s8844_doc",
)

# The client is created only when get_mongodb_client() is called.  Keeping the
# value at module scope lets later requests reuse one client and its pool.
_mongodb_client: MongoClient[Any] | None = None


def get_mongodb_client() -> MongoClient[Any]:
    """Return one lazily created MongoDB client for the HW6 features."""

    global _mongodb_client

    if _mongodb_client is None:
        _mongodb_client = MongoClient(
            MONGODB_URI,
            connect=False,
            serverSelectionTimeoutMS=2_000,
        )

    return _mongodb_client


def get_hw6_database() -> Database[Any]:
    """Return the configured HW6 database handle without creating collections."""

    return get_mongodb_client()[MONGODB_DB_NAME]


def ping_mongodb() -> dict[str, Any]:
    """Check MongoDB availability and return a safe, route-friendly result.

    Only expected PyMongo connection errors are converted into a controlled
    result.  Other programming errors are allowed to surface during testing.
    The response deliberately excludes the MongoDB URI.
    """

    try:
        get_mongodb_client().admin.command("ping")
    except PyMongoError:
        return {
            "ok": False,
            "error": "MongoDB is unavailable.",
        }

    return {
        "ok": True,
        "database": MONGODB_DB_NAME,
    }


def close_mongodb_client() -> None:
    """Close the shared client if it has been created, then clear the handle."""

    global _mongodb_client

    if _mongodb_client is not None:
        _mongodb_client.close()
        _mongodb_client = None
