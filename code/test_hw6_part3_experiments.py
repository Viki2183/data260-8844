"""Offline tests for the DATA260 HW6 Part 3 experiment runner."""

from __future__ import annotations

import sys
import unittest

sys.path.insert(0, str(__file__).replace("\\", "/").rsplit("/", 1)[0])

import run_hw06_part3_experiments as runner


class Part3ExperimentTests(unittest.TestCase):
    def test_same_thirty_messages_and_five_probes(self) -> None:
        self.assertEqual(len(runner.CONVERSATION_MESSAGES), 30)
        self.assertEqual(len(runner.SETUP_MESSAGES), 25)
        self.assertEqual(len(runner.PROBES), 5)
        self.assertEqual(runner.CONVERSATION_MESSAGES[25:], tuple(p["question"] for p in runner.PROBES))

    def test_windows_and_payload_override(self) -> None:
        self.assertEqual(runner.WINDOWS, (4, 12, 30))
        captured = []

        def fake_post(base_url, payload, timeout):
            captured.append(payload)
            return {
                "http_status": 200,
                "response_body": {
                    "answer": "distributed systems reliability modular testable documentation scalability fault tolerance",
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "latency_ms": 2.0},
                    "component_tokens": {
                        "primer": 1,
                        "session_summary": 1,
                        "lifetime_summary": 1,
                        "short_term_window": 1,
                        "episodic_facts": 1,
                        "current_user_message": 1,
                        "estimated_prompt_total": 6,
                    },
                    "memory_used": {},
                },
                "elapsed_ms": 3.0,
                "error": None,
            }

        original = runner.post_chat
        runner.post_chat = fake_post
        try:
            import io
            summary, scores = runner.run_window(12, "http://offline.invalid", 1, io.StringIO())
        finally:
            runner.post_chat = original
        self.assertEqual(len(captured), 30)
        self.assertTrue(all(payload["short_term_n"] == 12 for payload in captured))
        self.assertEqual(summary["total_turns"], 30)
        self.assertEqual(len(scores), 5)
        self.assertTrue(all(1 <= score["quality_score"] <= 5 for score in scores))

    def test_unavailable_means_are_none_and_cost_formula(self) -> None:
        self.assertIsNone(runner._mean([None, "unavailable"]))
        rows = runner.build_cost_rows([{
            "window": 4,
            "total_turns": 30,
            "mean_prompt_tokens_per_turn": 100,
            "mean_completion_tokens_per_turn": 20,
        }])
        row = rows[0]
        self.assertEqual(row["estimated_input_tokens"], 30_000_000)
        self.assertEqual(row["estimated_output_tokens"], 6_000_000)
        self.assertEqual(row["estimated_hypothetical_total_cost"], 24_000.0)

    def test_probe_scores_stay_within_rubric(self) -> None:
        for probe in runner.PROBES:
            score = runner.score_probe(probe, {"answer": "No relevant fact was provided."})
            self.assertIn(score["quality_score"], (1, 2, 3, 4, 5))


if __name__ == "__main__":
    unittest.main(verbosity=2)
