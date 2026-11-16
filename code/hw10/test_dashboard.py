"""Offline tests for the HW10 Streamlit dashboard data layer."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from dashboard_data import REPO_ROOT, STAGE_ORDER, load_evaluation, load_summary, load_traces, trace_rows


class DashboardDataTests(unittest.TestCase):
    def test_summary_metrics_are_historical_and_error_rate_uses_phase5_window(self) -> None:
        data = load_summary(REPO_ROOT)
        metrics = {item["metric"]: item for item in data["metrics"]}
        self.assertEqual(metrics["Recent request count"]["value"], 10)
        self.assertEqual(metrics["Cache-hit count"]["value"], 6)
        self.assertEqual(metrics["Cache-miss count"]["value"], 4)
        self.assertEqual(metrics["Cache hit rate"]["value"], 60.0)
        self.assertEqual(metrics["Average cache-hit latency"]["value"], 21.844)
        self.assertEqual(metrics["Average cache-miss latency"]["value"], 3075.926)
        self.assertEqual(metrics["Error count"]["value"], 0)
        self.assertEqual(metrics["Error rate"]["value"], 0.0)
        self.assertEqual(metrics["Error rate"]["status"], "live")
        self.assertIn("50 requests", metrics["Error rate"]["time_window"])
        self.assertTrue(all(item["source"] for item in data["metrics"]))
        self.assertTrue(all(item["time_window"] for item in data["metrics"]))

    def test_trace_order_and_observed_hw8_stages(self) -> None:
        traces = load_traces(REPO_ROOT)
        trace = next(item for item in traces if item["trace_id"] == "hw8-8844-agent-journey-001")
        rows = trace_rows(trace)
        self.assertEqual([row["stage"] for row in rows], list(STAGE_ORDER))
        statuses = {row["stage"]: row["status"] for row in rows}
        self.assertEqual(statuses["inbox"], "observed")
        self.assertEqual(statuses["planner"], "observed")
        self.assertEqual(statuses["tasks"], "observed_same_topic_record")
        self.assertEqual(statuses["writer"], "observed")
        self.assertEqual(statuses["drafts"], "observed_same_topic_record")
        self.assertEqual(statuses["reviewer"], "observed")
        self.assertEqual(statuses["final"], "observed_same_reviewer_record")
        self.assertEqual(statuses["cache_lookup"], "unavailable")
        self.assertEqual(statuses["evaluation"], "unavailable")

    def test_cache_hit_and_miss_trace_rows_are_distinguished(self) -> None:
        traces = load_traces(REPO_ROOT)
        hit = next(item for item in traces if item["trace_id"] == "warm-cache-02-8844")
        miss = next(item for item in traces if item["trace_id"] == "warm-cache-01-8844")
        hit_row = next(row for row in trace_rows(hit) if row["stage"] == "cache_lookup")
        miss_row = next(row for row in trace_rows(miss) if row["stage"] == "cache_lookup")
        self.assertEqual(hit_row["status"], "cache_hit")
        self.assertEqual(miss_row["status"], "cache_miss")
        self.assertEqual(hit_row["cache_status"], "hit")
        self.assertEqual(miss_row["cache_status"], "miss")

    def test_evaluation_page_data_and_constant_label_spearman(self) -> None:
        data = load_evaluation(REPO_ROOT)
        self.assertEqual(len(data["rows"]), 20)
        self.assertTrue(all(row["writer_score_trial_1"] == 1 for row in data["rows"]))
        self.assertTrue(all(row["planner_score"] is None for row in data["rows"]))
        self.assertTrue(all(row["reviewer_final_score"] is None for row in data["rows"]))
        self.assertEqual(data["statistics"]["spearman_correlation"], None)
        self.assertEqual(data["statistics"]["spearman_status"], "undefined_constant_human_labels")
        self.assertEqual(data["statistics"]["repeatability_percentage"], 100.0)
        self.assertIn("not evidence of correct vulnerability answers", data["interpretation"])

    def test_offline_evaluation_trace_is_explicitly_not_live(self) -> None:
        traces = load_traces(REPO_ROOT)
        trace = next(item for item in traces if item["trace_id"] == "hw10-offline-eval-01")
        rows = trace_rows(trace)
        writer = next(row for row in rows if row["stage"] == "writer")
        evaluation = next(row for row in rows if row["stage"] == "evaluation")
        self.assertEqual(writer["status"], "offline_reconstructed")
        self.assertEqual(evaluation["status"], "offline_evaluation")
        self.assertEqual(trace["source_kinds"], ["offline"])

    def test_phase5_live_trace_index_and_latency_summary_are_loaded(self) -> None:
        traces = load_traces(REPO_ROOT)
        index = json.loads((REPO_ROOT / "reports/hw10/raw/traces/trace_index.json").read_text(encoding="utf-8"))
        live_ids = set(index["trace_ids"].values())
        self.assertTrue(live_ids.issubset({trace["trace_id"] for trace in traces}))
        hit = next(trace for trace in traces if trace["trace_id"] == index["trace_ids"]["cache_hit"])
        miss = next(trace for trace in traces if trace["trace_id"] == index["trace_ids"]["cache_miss"])
        failed = next(trace for trace in traces if trace["trace_id"] == index["trace_ids"]["failed"])
        self.assertEqual(next(row for row in trace_rows(hit) if row["stage"] == "cache_lookup")["status"], "cache_hit")
        self.assertEqual(next(row for row in trace_rows(miss) if row["stage"] == "final")["status"], "observed_same_topic_record")
        self.assertEqual(next(row for row in trace_rows(failed) if row["stage"] == "cache_lookup")["status"], "failed_before_cache_decision")
        self.assertEqual(failed["source_kinds"], ["live"])

    def test_live_end_to_end_evaluation_is_loaded_without_fabricating_scores(self) -> None:
        data = load_evaluation(REPO_ROOT)
        live = data["live_evaluation"]
        self.assertIsNotNone(live)
        self.assertEqual(live["trace_id"], "hw10-live-e2e-eval-fdc655292734")
        self.assertIn("Which version fixes CVE-2026-1001", live["question"])
        self.assertTrue(live["plan"])
        self.assertTrue(live["writer_draft"])
        self.assertTrue(live["reviewer_final"])
        self.assertEqual(len(live["criteria"]), 4)
        self.assertTrue(all(item["score"] is None for item in live["criteria"]))

    def test_live_trace_uses_evaluator_span_as_evaluation_stage(self) -> None:
        traces = load_traces(REPO_ROOT)
        trace = next(item for item in traces if item["trace_id"] == "hw10-live-e2e-eval-fdc655292734")
        evaluation = next(row for row in trace_rows(trace) if row["stage"] == "evaluation")
        self.assertEqual(evaluation["status"], "completed_with_errors")
        self.assertTrue(evaluation["start_time"])
        self.assertTrue(evaluation["end_time"])
        self.assertIn("instrumented span", evaluation["timing_provenance"])


if __name__ == "__main__":
    unittest.main()
