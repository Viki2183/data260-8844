"""Explicit report-scoped versions used to reject stale cache entries."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from .redis_client import get_redis_client, make_key


def report_data_version(db: Session, report_id: int | None) -> str | None:
    if report_id is None:
        return None
    try:
        from ..web_application import models
    except ImportError:  # pragma: no cover
        from web_application import models
    report = (
        db.query(models.VulnerabilityReportDB)
        .filter(models.VulnerabilityReportDB.id == report_id)
        .first()
    )
    if report is None:
        raise LookupError("Vulnerability report not found")
    return str(report.updated_at)


def version_key(report_id: int) -> str:
    return make_key("semantic_cache:version", report_id)


def current_or_recorded_version(
    db: Session,
    report_id: int | None,
    redis_client: Any,
) -> str | None:
    if report_id is None:
        return None
    marker = report_data_version(db, report_id)
    stored = redis_client.get(version_key(report_id))
    if stored is None:
        redis_client.set(version_key(report_id), 1)
        return "1"
    if isinstance(stored, bytes):
        stored = stored.decode("utf-8")
    return str(stored)


def invalidate_report_version(report_id: int, redis_client: Any | None = None) -> int:
    client = redis_client or get_redis_client()
    return int(client.incr(version_key(report_id)))
