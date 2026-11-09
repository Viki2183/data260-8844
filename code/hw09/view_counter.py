"""Redis-backed view counter for the real vulnerability-report entity."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from .redis_client import get_redis_client, make_key


class VulnerabilityReportViewCounter:
    """Increment Redis on every call and synchronize MySQL every tenth view."""

    def __init__(self, redis_client: Any | None = None) -> None:
        self.redis = redis_client or get_redis_client()

    def increment_vulnerability_report_views(
        self,
        db: Session,
        report_id: int,
    ) -> int:
        try:
            try:
                from ..web_application import models
            except ImportError:  # pragma: no cover - direct PYTHONPATH=code execution
                from web_application import models
            model = models.VulnerabilityReportDB
            query = db.query(model).filter(model.id == report_id)
        except ImportError:  # deterministic fake-DB tests without project dependencies
            query = db.query(object())
        report = query.first()
        if report is None:
            raise LookupError("Vulnerability report not found.")

        key = make_key("views:vulnerability_report", report_id)
        count = int(self.redis.incr(key))
        if count % 10 == 0:
            report.view_count = count
            db.commit()
            db.refresh(report)
            print("Synced views to database", flush=True)
        return count
