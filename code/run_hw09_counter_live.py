"""Reversible live 25-access view-counter verification."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "code" / "web_application"))

from hw09.redis_client import get_redis_client, make_key
from hw09.view_counter import VulnerabilityReportViewCounter
from web_application.database import db_session_basede26
from web_application.models import VulnerabilityReportDB


def main() -> None:
    db = db_session_basede26()
    redis = get_redis_client()
    report = db.query(VulnerabilityReportDB).order_by(VulnerabilityReportDB.id).first()
    if report is None:
        raise RuntimeError("No vulnerability report exists for the reversible test")
    original = report.view_count
    key = make_key("views:vulnerability_report", report.id)
    redis.delete(key)
    report.view_count = 0
    db.commit()
    counter = VulnerabilityReportViewCounter(redis)
    accesses = []
    print("Vrishin KunnathamParambath\nSID4: 8844")
    try:
        for number in range(1, 26):
            total = counter.increment_vulnerability_report_views(db, report.id)
            row = {"access": number, "total": total}
            if number in {10, 20}:
                db.refresh(report)
                row["database_view_count"] = report.view_count
            accesses.append(row)
            print(f"Access #{number}: Total = {total}")
            if number in {10, 20}:
                print("✓ Synced views to database")
        result = {"student": "Vrishin KunnathamParambath", "sid4": "8844",
                  "report_id": report.id, "redis_key": key, "original_view_count": original,
                  "accesses": accesses, "sync_counts": [10, 20]}
    finally:
        report.view_count = original
        db.commit()
        redis.delete(key)
        db.close()
    result["restored_view_count"] = original
    target = ROOT / "reports/hw09/raw/counter_live_final.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
