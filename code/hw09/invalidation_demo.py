"""Reproducible, reversible report-version invalidation demonstration."""

from __future__ import annotations

from typing import Any

from .data_versions import report_data_version


def demonstrate_version_change(
    db: Any,
    report_id: int,
    mutate: Any,
    restore: Any,
) -> dict[str, Any]:
    before = report_data_version(db, report_id)
    mutate()
    db.commit()
    after = report_data_version(db, report_id)
    restore()
    db.commit()
    return {
        "report_id": report_id,
        "before_version": before,
        "after_version": after,
        "invalidated": before != after,
        "restored": True,
    }
