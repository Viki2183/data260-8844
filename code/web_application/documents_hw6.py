"""FastAPI routes for the HW6 MongoDB document API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from pymongo.errors import PyMongoError

try:
    from .mongo_repositories_hw6 import (
        DocumentNotFoundError,
        InvalidDocumentIdError,
        create_document,
        delete_document,
        get_document,
        list_documents,
        update_document,
    )
    from .schemas_hw6 import DocumentCreate, DocumentResponse, DocumentUpdate
except ImportError:
    from mongo_repositories_hw6 import (
        DocumentNotFoundError,
        InvalidDocumentIdError,
        create_document,
        delete_document,
        get_document,
        list_documents,
        update_document,
    )
    from schemas_hw6 import DocumentCreate, DocumentResponse, DocumentUpdate


router = APIRouter(
    prefix="/api/documents",
    tags=["HW6 Documents"],
)


def _database_failure() -> HTTPException:
    """Create one safe response for expected MongoDB operation failures."""

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="The document database is unavailable.",
    )


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document_route(payload: DocumentCreate) -> dict[str, Any]:
    """Create a document and return it with HTTP 201 Created."""

    try:
        return create_document(payload)
    except PyMongoError as error:
        # The client receives a useful generic error, not a URI or traceback.
        raise _database_failure() from error


@router.get(
    "",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_200_OK,
)
def list_document_route(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict[str, Any]]:
    """Return bounded, newest-first document results with HTTP 200 OK."""

    try:
        return list_documents(skip=skip, limit=limit)
    except PyMongoError as error:
        raise _database_failure() from error


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
)
def get_document_route(document_id: str) -> dict[str, Any]:
    """Return one document, translating malformed or missing IDs."""

    try:
        return get_document(document_id)
    except InvalidDocumentIdError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except PyMongoError as error:
        raise _database_failure() from error


@router.put(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
)
def update_document_route(
    document_id: str,
    payload: DocumentUpdate,
) -> dict[str, Any]:
    """Update one document and return the updated representation."""

    try:
        return update_document(document_id, payload)
    except InvalidDocumentIdError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except PyMongoError as error:
        raise _database_failure() from error


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_document_route(document_id: str) -> Response:
    """Delete one document and return an empty HTTP 204 response."""

    try:
        delete_document(document_id)
    except InvalidDocumentIdError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except DocumentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except PyMongoError as error:
        raise _database_failure() from error

    # A 204 response must not contain a JSON body.
    return Response(status_code=status.HTTP_204_NO_CONTENT)
