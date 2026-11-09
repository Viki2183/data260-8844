"""Reversible report-scoped stale-hit and explicit-version invalidation demo."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "code" / "web_application"))

from hw09.data_versions import current_or_recorded_version, invalidate_report_version
from hw09.redis_client import get_redis_client
from hw09.semantic_cache import SemanticCache
from web_application.database import db_session_basede26
from web_application.models import VulnerabilityReportDB


def main() -> None:
    db = db_session_basede26()
    redis = get_redis_client()
    cache = SemanticCache(redis, threshold=0.85)
    report = db.query(VulnerabilityReportDB).order_by(VulnerabilityReportDB.id).first()
    if report is None:
        raise RuntimeError("No vulnerability report exists for the reversible test")
    original_severity, original_updated = report.severity, report.updated_at
    changed_severity = "Critical" if original_severity != "Critical" else "Low"
    question = f"What is the severity of vulnerability report {report.id}?"
    embedding = cache.embed(question)
    version_before = current_or_recorded_version(db, report.id, redis)
    entry = cache.store(question, embedding, f"Report {report.id} severity is {original_severity}.",
                        report.id, version_before)
    original_hit, _ = cache.lookup(question, embedding, version_before, report.id)
    regenerated_entry = None
    print("Vrishin KunnathamParambath\nSID4: 8844")
    print(f"Original database value: {original_severity}")
    try:
        report.severity = changed_severity
        report.updated_at = datetime.now()
        db.commit()
        db.refresh(report)
        print(f"Changed database value: {report.severity}")
        stale_hit, stale_similarity = cache.lookup(question, embedding, version_before, report.id)
        print(f"Before invalidation: cache_status=hit answer={stale_hit['answer']}")
        version_after = str(invalidate_report_version(report.id, redis))
        invalidated, invalidated_similarity = cache.lookup(
            question, embedding, version_after, report.id
        )
        new_answer = f"Report {report.id} severity is {report.severity}."
        regenerated_entry = cache.store(
            question, embedding, new_answer, report.id, version_after
        )
        regenerated, _ = cache.lookup(question, embedding, version_after, report.id)
        print(f"Invalidated version: {version_before} -> {version_after}")
        print(f"After invalidation: cache_status=miss regenerated_answer={regenerated['answer']}")
        result = {
            "student": "Vrishin KunnathamParambath", "sid4": "8844",
            "report_id": report.id, "question": question,
            "original_database_value": original_severity,
            "original_cached_answer": original_hit["answer"],
            "changed_database_value": report.severity,
            "stale_hit_before_invalidation": True,
            "stale_cached_answer": stale_hit["answer"],
            "stale_similarity": stale_similarity,
            "old_version": version_before, "new_version": version_after,
            "old_entry_rejected_after_invalidation": invalidated is None,
            "post_invalidation_similarity": invalidated_similarity,
            "regenerated_answer": regenerated["answer"],
        }
    finally:
        report.severity = original_severity
        report.updated_at = original_updated
        db.commit()
        db.refresh(report)
        invalidate_report_version(report.id, redis)
        redis.delete(cache._entry_key(entry["entry_id"]))
        if regenerated_entry is not None:
            redis.delete(cache._entry_key(regenerated_entry["entry_id"]))
        result["restored_database_value"] = report.severity
        result["restored"] = report.severity == original_severity
        print(f"Restored database value: {report.severity}")
        db.close()
    target = ROOT / "reports/hw09/raw/stale_answer_content_final.json"
    target.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
