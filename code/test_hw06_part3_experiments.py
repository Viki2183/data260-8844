"""Offline checks for the DATA260 HW6 Part 3 aggregation logic."""

from __future__ import annotations

import json
import hashlib
import unittest
from pathlib import Path

import run_hw06_part3_experiments as runner


class Part3AggregationTests(unittest.TestCase):
    """Use a tiny JSONL fixture so aggregation never needs live services."""

    def test_canonical_current_message_mean_and_negative_savings(self) -> None:
        records = [
            {
                "window": 4,
                "turn": 1,
                "kind": "setup",
                "http_status": 200,
                "prompt_tokens": 20,
                "completion_tokens": 5,
                "total_tokens": 25,
                "model_latency_ms": 10,
                "elapsed_ms": 11,
                "component_tokens": {
                    "primer": 1,
                    "session_summary": 0,
                    "lifetime_summary": 0,
                    "short_term_window": 2,
                    "episodic_facts": 0,
                    "current_user_message": 7,
                    "estimated_prompt_total": 10,
                },
                "quality_score": None,
            },
            {
                "window": 4,
                "turn": 2,
                "kind": "probe",
                "http_status": 200,
                "prompt_tokens": 22,
                "completion_tokens": 6,
                "total_tokens": 28,
                "model_latency_ms": 12,
                "elapsed_ms": 13,
                "component_tokens": {
                    "primer": 1,
                    "session_summary": 0,
                    "lifetime_summary": 0,
                    "short_term_window": 3,
                    "episodic_facts": 0,
                    "current_user_message": 9,
                    "estimated_prompt_total": 12,
                },
                "quality_score": 5,
            },
        ]
        probe_scores = [{"quality_score": 5}]

        # Keep the fixture in memory so the test never needs a writable
        # temporary directory and cannot affect repository evidence.
        fixture_text = "\n".join(json.dumps(record) for record in records) + "\n"
        loaded = [json.loads(line) for line in fixture_text.splitlines()]

        summary = runner.aggregate_window_records(
            loaded,
            4,
            probe_scores,
            conversation_messages=("one two three", "four five six"),
        )

        self.assertEqual(summary["mean_current_user_message_tokens"], 8.0)
        self.assertNotIn("mean_current_message_tokens", summary)
        self.assertEqual(summary["estimated_token_savings"], -8)
        self.assertLess(summary["estimated_token_savings"], 0)

    def test_aggregation_does_not_call_external_services(self) -> None:
        original_post_chat = runner.post_chat

        def fail_if_called(*args, **kwargs):
            raise AssertionError("offline aggregation must not send HTTP requests")

        runner.post_chat = fail_if_called
        try:
            summary = runner.aggregate_window_records(
                [
                    {
                        "window": 4,
                        "http_status": 200,
                        "component_tokens": {
                            "current_user_message": 4,
                            "estimated_prompt_total": 4,
                        },
                        "quality_score": None,
                    }
                ],
                4,
                [],
                conversation_messages=("one", "two"),
            )
        finally:
            runner.post_chat = original_post_chat

        self.assertEqual(summary["mean_current_user_message_tokens"], 4.0)

    def test_corrected_cost_formula_and_baseline_comparison(self) -> None:
        summaries = [
            {
                "window": 4,
                "total_turns": 30,
                "mean_prompt_tokens_per_turn": 827.733,
                "mean_completion_tokens_per_turn": 170.733,
                "mean_quality_score": 4.2,
                "mean_model_latency_ms_per_turn": 42393.933,
                "estimated_token_savings": -105,
            },
            {
                "window": 12,
                "total_turns": 30,
                "mean_prompt_tokens_per_turn": 1325.767,
                "mean_completion_tokens_per_turn": 172.667,
                "mean_quality_score": 4.2,
                "mean_model_latency_ms_per_turn": 54340.642,
                "estimated_token_savings": -496,
            },
            {
                "window": 30,
                "total_turns": 30,
                "mean_prompt_tokens_per_turn": 967.8,
                "mean_completion_tokens_per_turn": 196.667,
                "mean_quality_score": 4.0,
                "mean_model_latency_ms_per_turn": 66549.364,
                "estimated_token_savings": -2824,
            },
        ]
        costs = runner.build_cost_rows(summaries)
        self.assertAlmostEqual(costs[0]["total_cost"], 504.4194, places=3)
        self.assertAlmostEqual(costs[1]["total_cost"], 656.7306, places=3)
        self.assertAlmostEqual(costs[2]["total_cost"], 585.3405, places=3)

        comparison = runner.build_cost_comparison_rows(summaries)
        baseline = next(row for row in comparison if row["window"] == 12)
        self.assertEqual(baseline["savings_versus_baseline"], 0)
        self.assertEqual(runner.choose_best_worst(summaries)["best"], 4)
        self.assertEqual(runner.choose_best_worst(summaries)["worst"], 12)
        self.assertEqual(
            [row["estimated_component_minus_raw_history_baseline"] for row in comparison],
            [-105, -496, -2824],
        )

    def test_real_fixture_completion_means_and_checksum(self) -> None:
        raw_path = runner.RUNS_JSONL
        raw_bytes = raw_path.read_bytes()
        self.assertEqual(
            hashlib.sha256(raw_bytes).hexdigest(),
            "38f80d1a7a1ec318683e0a09045956547c64555e1d3c8d52ef1f89b9c724f5d6",
        )
        records = [json.loads(line) for line in raw_bytes.decode("utf-8").splitlines() if line.strip()]
        for window, expected in ((4, 170.733), (12, 172.667), (30, 196.667)):
            values = [r["completion_tokens"] for r in records if r["window"] == window]
            self.assertAlmostEqual(sum(values) / len(values), expected, places=3)


if __name__ == "__main__":
    unittest.main()
