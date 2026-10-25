"""Offline regression test for the HW7 bike-share UI pipeline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from web_application import hw7_bikeshare_routes as routes


def test_bikeshare_pipeline_returns_completed_structured_result(monkeypatch) -> None:
    csv_text = "ride_id,started_at,duration_minutes\n1,2026-09-01T08:00:00Z,30\n"
    monkeypatch.setattr(
        routes,
        "policy_retriever",
        lambda url, query, k=3: {
            "success": True,
            "data": {"passages": [{"text": "membership pricing", "source": url}]},
            "source": url,
            "ts": "offline-test",
        },
    )
    result = routes.run_bikeshare_pipeline(csv_text, "https://example.test/pricing")
    assert result["success"] is True
    data = result["data"]
    assert data["tool_order"] == ["csv_sql", "policy_retriever", "calculator"]
    assert data["stop_reason"] == "success"
    assert data["ride_count"] == 1
    assert data["average_duration"] == 30.0
    assert data["total_steps"] == 3
    assert data["citations"][0]["source"] == "https://example.test/pricing"


def test_bikeshare_pipeline_reports_csv_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        routes,
        "csv_sql",
        lambda csv_text, sql: {"success": False, "error": "fixture failure"},
    )
    result = routes.run_bikeshare_pipeline("not,csv", "https://example.test/pricing")
    assert result == {"success": False, "error": "fixture failure"}
