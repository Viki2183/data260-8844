"""FastAPI routes that expose the DATA 260 Homework 6 memory service."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from pymongo.errors import PyMongoError

try:
    from . import memory_repositories_hw6 as memory_repository
    from .memory_schemas_hw6 import (
        AggregateResponse,
        ChatRequest,
        ChatResponse,
        MemorySnapshotResponse,
    )
    from .memory_service_hw6 import MemoryService
except ImportError:  # pragma: no cover - supports direct module imports
    import memory_repositories_hw6 as memory_repository
    from memory_schemas_hw6 import (
        AggregateResponse,
        ChatRequest,
        ChatResponse,
        MemorySnapshotResponse,
    )
    from memory_service_hw6 import MemoryService


router = APIRouter(prefix="/api", tags=["HW6 Memory"])
_memory_service: MemoryService | None = None


def get_memory_service() -> MemoryService:
    """Create the integrated service only when a chat request needs it."""

    global _memory_service

    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service


def _require_user_id(user_id: str) -> str:
    """Reject empty path identifiers before any database query is attempted."""

    if not isinstance(user_id, str) or not user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id must contain meaningful text.",
        )
    return user_id


def _database_failure() -> HTTPException:
    """Return a safe database error without exposing connection details."""

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="The memory database is unavailable.",
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
def chat(
    payload: ChatRequest,
    service: MemoryService = Depends(get_memory_service),
) -> dict[str, Any]:
    """Translate one HTTP chat request into a complete memory lifecycle."""

    try:
        result = service.chat(
            user_id=payload.user_id,
            session_id=payload.session_id,
            message=payload.message,
            short_term_n=payload.short_term_n,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except PyMongoError as exc:
        raise _database_failure() from exc

    # The service returns a controlled error when model generation fails.  The
    # router turns that into an HTTP failure instead of claiming chat success.
    if result.get("error"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The memory model could not complete the request.",
        )

    try:
        ChatResponse.model_validate(result)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The memory service returned an invalid response.",
        ) from exc

    return result


@router.get(
    "/memory/{user_id}",
    response_model=MemorySnapshotResponse,
    status_code=status.HTTP_200_OK,
)
def get_memory_snapshot(
    user_id: str,
    session_id: str | None = Query(default=None, min_length=1),
) -> dict[str, Any]:
    """Return recent messages, summaries, and episodic facts for one user."""

    user_id = _require_user_id(user_id)
    if session_id is not None and not session_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id must contain meaningful text.",
        )

    try:
        messages = (
            memory_repository.load_short_term_messages(
                user_id,
                session_id,
                limit=16,
            )
            if session_id is not None
            else []
        )
        session_summary = (
            memory_repository.get_latest_session_summary(user_id, session_id)
            if session_id is not None
            else None
        )
        lifetime_summary = memory_repository.get_latest_lifetime_summary(user_id)
        episodic_facts = memory_repository.list_recent_episodes(user_id, limit=20)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except PyMongoError as exc:
        raise _database_failure() from exc

    return {
        "user_id": user_id,
        "messages": messages,
        "latest_session_summary": session_summary,
        "latest_lifetime_summary": lifetime_summary,
        "episodic_facts": episodic_facts,
    }


@router.get(
    "/aggregate/{user_id}",
    response_model=AggregateResponse,
    status_code=status.HTTP_200_OK,
)
def get_memory_aggregate(user_id: str) -> dict[str, Any]:
    """Return UTC daily message counts and recent summaries for one user."""

    user_id = _require_user_id(user_id)
    try:
        daily_counts = memory_repository.get_daily_message_counts(user_id)
        recent_summaries = memory_repository.get_recent_summaries_for_user(
            user_id,
            limit=20,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except PyMongoError as exc:
        raise _database_failure() from exc

    return {
        "user_id": user_id,
        "daily_message_counts": daily_counts,
        "recent_summaries": recent_summaries,
    }


__all__ = ["get_memory_service", "router"]
