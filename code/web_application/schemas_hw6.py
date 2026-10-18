"""Pydantic schemas for the DATA 260 Homework 6 document API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Severity = Literal["Critical", "High", "Medium", "Low"]
Status = Literal["Open", "Resolved", "Accepted", "Rejected"]


class DocumentFields(BaseModel):
    """Shared document fields and validation rules."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
    )
    severity: Severity
    status: Status = "Open"
    document_date: datetime
    package_code: str | None = Field(
        default=None,
        max_length=100,
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )

    @field_validator("title")
    @classmethod
    def reject_blank_title(cls, value: str) -> str:
        """Reject titles that contain no meaningful text."""

        cleaned = value.strip()

        if not cleaned:
            raise ValueError("title cannot be blank")

        return cleaned

    @field_validator("package_code")
    @classmethod
    def reject_blank_package_code(cls, value: str | None) -> str | None:
        """Prevent an optional package reference from being whitespace only."""

        if value is None:
            return None

        cleaned = value.strip()

        if not cleaned:
            raise ValueError("package_code cannot be blank")

        return cleaned


class DocumentCreate(DocumentFields):
    """Validate a new vulnerability-reporting document."""


class DocumentUpdate(DocumentFields):
    """Validate a partial document update with at least one supplied field."""

    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )
    description: str | None = Field(
        default=None,
        max_length=2000,
    )
    severity: Severity | None = None
    status: Status | None = None
    document_date: datetime | None = None
    package_code: str | None = Field(
        default=None,
        max_length=100,
    )

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "DocumentUpdate":
        """Make an empty update explicit instead of silently doing nothing."""

        if not self.model_fields_set:
            raise ValueError("at least one document field is required")

        return self


class DocumentResponse(DocumentFields):
    """Represent a stored MongoDB document in a JSON-friendly response."""

    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )
