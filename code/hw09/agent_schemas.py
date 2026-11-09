"""HTTP schemas for the HW9 authenticated agent ingress."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentAskRequest(BaseModel):
    question: str = Field(min_length=1)
    report_id: int | None = Field(default=None, gt=0)
    correlation_id: str | None = Field(default=None, min_length=1, max_length=200)


class AgentAskResponse(BaseModel):
    answer: str
    is_cached: bool
    similarity: float
    latency_ms: float
    cache_status: str
    correlation_id: str
    timings_ms: dict[str, float]
