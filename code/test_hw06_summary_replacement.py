"""Offline checks for the opt-in HW6 summary-replacement prompt policy."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


# Import the pure helper without importing FastAPI, MongoDB, Ollama, or the
# embedding service. The tests operate entirely on deterministic dictionaries.
sys.path.insert(0, str(Path(__file__).resolve().parent / "web_application"))
import memory_logic_hw6 as memory_logic  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_hw06_part3_experiments as part3_runner  # noqa: E402


def _messages(count: int, current: str) -> list[dict[str, object]]:
    prior = [
        {"role": "user", "content": f"Earlier message {index}", "created_at": index}
        for index in range(count)
    ]
    prior.append({"role": "user", "content": current, "created_at": count})
    return prior


class SummaryReplacementTests(unittest.TestCase):
    def test_oldest_messages_are_replaced_after_threshold(self) -> None:
        result = memory_logic.apply_summary_replacement_policy(
            _messages(6, "Current question"),
            "The session summary preserves the older project context.",
            "Current question",
            enabled=True,
            threshold=3,
        )
        contents = [str(item["content"]) for item in result["messages"]]
        self.assertTrue(result["triggered"])
        self.assertEqual(result["replaced_message_count"], 3)
        self.assertEqual(len(contents), 4)
        self.assertNotIn("Earlier message 0", contents)
        self.assertIn("Earlier message 5", contents)
        self.assertEqual(contents.count("Current question"), 1)
        self.assertTrue(result["summary_included"])

    def test_summary_is_included_and_current_message_appears_once(self) -> None:
        current = "What is my preferred topic?"
        summary = "The user prefers distributed systems."
        result = memory_logic.apply_summary_replacement_policy(
            _messages(5, current),
            summary,
            current,
            enabled=True,
            threshold=2,
        )
        prompt = memory_logic.build_memory_prompt(
            "Helpful assistant.",
            None,
            summary,
            result["messages"],
            current,
            [],
        )
        self.assertEqual(prompt.count(current), 1)
        self.assertIn(summary, prompt)
        self.assertLessEqual(len(result["messages"]), 3)

    def test_component_tokens_follow_reduced_recent_context(self) -> None:
        current = "Current question"
        original = _messages(6, current)
        result = memory_logic.apply_summary_replacement_policy(
            original,
            "Older context summary.",
            current,
            enabled=True,
            threshold=2,
        )
        before = memory_logic.get_memory_usage_breakdown(
            "Primer", "", "Older context summary.", original, current, []
        )
        after = memory_logic.get_memory_usage_breakdown(
            "Primer", "", "Older context summary.", result["messages"], current, []
        )
        self.assertLess(after["short_term_window"], before["short_term_window"])
        self.assertEqual(
            after["estimated_prompt_total"],
            sum(after[key] for key in (
                "primer", "session_summary", "lifetime_summary",
                "short_term_window", "episodic_facts", "current_user_message",
            )),
        )

    def test_policy_is_disabled_without_changing_existing_behavior(self) -> None:
        messages = _messages(6, "Current question")
        result = memory_logic.apply_summary_replacement_policy(
            messages,
            "Summary exists but policy is disabled.",
            "Current question",
            enabled=False,
            threshold=2,
        )
        self.assertFalse(result["triggered"])
        self.assertEqual(result["replaced_message_count"], 0)
        self.assertEqual(result["messages"], messages)

    def test_threshold_is_bounded(self) -> None:
        with self.assertRaises(ValueError):
            memory_logic.apply_summary_replacement_policy(
                [], "summary", "current", enabled=True, threshold=0
            )

    def test_offline_runner_fixture_is_explicit_and_unmeasured(self) -> None:
        result = part3_runner.build_summary_replacement_fixture(
            short_term_n=12,
            threshold=3,
        )
        self.assertTrue(result["offline_fixture_only"])
        self.assertEqual(result["baseline_name"], "N=12 prompt estimate with summary replacement disabled")
        self.assertGreater(result["messages_replaced"], 0)
        self.assertEqual(result["summary_included"], True)
        self.assertEqual(result["current_user_message_occurrences"], 1)
        self.assertEqual(result["raw_messages_preserved"], True)
        self.assertIsNone(result["mean_latency_ms"])
        self.assertIsNone(result["mean_quality_score"])
        self.assertIsNone(result["quality_change_vs_N12"])
        self.assertGreater(result["token_savings_vs_N12_baseline"], 0)


if __name__ == "__main__":
    unittest.main()
