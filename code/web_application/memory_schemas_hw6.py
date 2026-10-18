"""Pydantic schemas for the DATA 260 Homework 6 memory system."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    """Validate the user and message supplied to the memory-aware chat API."""

    user_id: str = Field(min_length=1)
    session_id: str | None = Field(default=None, min_length=1)
    message: str = Field(min_length=1, max_length=4000)
    # This optional override exists for reproducible HW6 window comparisons.
    # Omitting it keeps the configured SHORT_TERM_N default unchanged.
    short_term_n: int | None = Field(default=None, ge=1, le=30)

    @field_validator("user_id", "session_id", "message")
    @classmethod
    def reject_whitespace_only(cls, value: str | None) -> str | None:
        """Reject identifiers and messages that contain no meaningful text."""

        if value is not None and not value.strip():
            raise ValueError("Value must not be whitespace-only")
        return value


class MemoryMessageResponse(BaseModel):
    """Represent one stored user or assistant message."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    token_count: int | None = None
    latency_ms: float | None = None


class SummaryResponse(BaseModel):
    """Represent a session-scoped or lifetime user summary."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    session_id: str | None = None
    scope: Literal["session", "user"]
    text: str
    created_at: datetime
    updated_at: datetime | None = None


class EpisodeResponse(BaseModel):
    """Represent an extracted fact and its embedding for episodic retrieval."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    session_id: str | None = None
    fact: str
    importance: float = Field(ge=0.0, le=1.0)
    embedding: list[float]
    created_at: datetime


class FileMemoryMetadata(BaseModel):
    """Describe the local file-memory source without exposing its contents."""

    path: str
    line_count: int = Field(ge=0)
    age_hours: float = Field(ge=0.0)
    requires_consolidation: bool


class MemoryUsed(BaseModel):
    """Describe which memory sources were included in a chat response."""

    short_term_count: int = Field(ge=0)
    short_term_messages: list[MemoryMessageResponse]
    session_summary: str | None = None
    lifetime_summary: str | None = None
    episodic_facts: list[EpisodeResponse]
    file_memory: dict[str, Any] | None = None


class UsageMetrics(BaseModel):
    """Record token usage and latency for one memory-aware response."""

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    system_primer_tokens: int = Field(ge=0)
    long_term_tokens: int = Field(ge=0)
    short_term_tokens: int = Field(ge=0)
    episodic_tokens: int = Field(ge=0)
    latency_ms: float = Field(ge=0.0)


class ComponentTokenBreakdown(BaseModel):
    """Deterministic estimated tokens for each assembled prompt section."""

    model_config = ConfigDict(from_attributes=True)

    primer: int = Field(ge=0)
    session_summary: int = Field(ge=0)
    lifetime_summary: int = Field(ge=0)
    short_term_window: int = Field(ge=0)
    episodic_facts: int = Field(ge=0)
    current_user_message: int = Field(ge=0)
    estimated_prompt_total: int = Field(ge=0)


class ChatResponse(BaseModel):
    """Return an assistant answer together with memory and usage details."""

    model_config = ConfigDict(from_attributes=True)

    answer: str
    user_id: str
    session_id: str | None = None
    memory_used: MemoryUsed
    usage: UsageMetrics
    component_tokens: ComponentTokenBreakdown = Field(
        default_factory=lambda: ComponentTokenBreakdown(
            primer=0,
            session_summary=0,
            lifetime_summary=0,
            short_term_window=0,
            episodic_facts=0,
            current_user_message=0,
            estimated_prompt_total=0,
        )
    )
    prompt_token_total_estimate: int = Field(default=0, ge=0)
    command: str | None = None
    command_result: dict[str, Any] | None = None
    diagnostics: list[dict[str, str]] = Field(default_factory=list)


class MemorySnapshotResponse(BaseModel):
    """Return the current messages, summaries, and episodic facts for a user."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    messages: list[MemoryMessageResponse]
    latest_session_summary: SummaryResponse | None = None
    latest_lifetime_summary: SummaryResponse | None = None
    episodic_facts: list[EpisodeResponse]
    file_memory: dict[str, Any] | None = None


class DailyMessageCount(BaseModel):
    """Represent a user's message total for one calendar date."""

    date: str
    count: int = Field(ge=0)


class AggregateResponse(BaseModel):
    """Return daily message totals and recent summaries for a user."""

    model_config = ConfigDict(from_attributes=True)

    user_id: str
    daily_message_counts: list[DailyMessageCount]
    recent_summaries: list[SummaryResponse]


__all__ = [
    "AggregateResponse",
    "ChatRequest",
    "ChatResponse",
    "ComponentTokenBreakdown",
    "DailyMessageCount",
    "EpisodeResponse",
    "FileMemoryMetadata",
    "MemoryMessageResponse",
    "MemorySnapshotResponse",
    "MemoryUsed",
    "SummaryResponse",
    "UsageMetrics",
]
