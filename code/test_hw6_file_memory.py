"""Offline tests for the standalone HW6 file-memory policy."""

from __future__ import annotations

import tempfile
import unittest
import os
import time
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from web_application.file_memory_hw6 import (
    FILE_MEMORY_MAX_LINES,
    compare_file_memory_with_mongodb,
    consolidate_memory,
    count_memory_lines,
    detect_contradictions,
    memory_file_requires_consolidation,
    read_memory_file,
    remove_duplicate_facts,
    verify_generated_consolidation,
    write_memory_file,
)
from web_application import memory_logic_hw6 as memory_logic
from web_application.memory_service_hw6 import MemoryService


FIXED_CONTENT = "\n".join([
    "Last modified: 2026-10-17T00:00:00Z",
    "Preference: explanation style is concise.",
    "Preference: explanation style is concise.",
    "Preference: explanation style is detailed.",
    "Goal: keep the project modular and testable.",
    "Goal: keep the project modular and testable.",
    *[f"Note {index}: ordinary project memory line." for index in range(1, 52)],
]) + "\n"


class FileMemoryTests(unittest.TestCase):
    def test_short_term_override_validation_and_default(self) -> None:
        self.assertEqual(memory_logic.resolve_short_term_n(None, 12), 12)
        self.assertEqual(memory_logic.resolve_short_term_n(4, 12), 4)
        self.assertEqual(memory_logic.resolve_short_term_n(12, 4), 12)
        self.assertEqual(memory_logic.resolve_short_term_n(30, 12), 30)
        with self.assertRaises(ValueError):
            memory_logic.resolve_short_term_n(0, 12)
        with self.assertRaises(ValueError):
            memory_logic.resolve_short_term_n(31, 12)

    def test_short_term_override_controls_history_and_components(self) -> None:
        class FakeRepository:
            def __init__(self) -> None:
                self.messages = [
                    {"role": "assistant", "content": f"Earlier answer {index}"}
                    for index in range(40)
                ]
                self.load_limits: list[int] = []

            def save_message(self, user_id, session_id, role, content, **kwargs):
                item = {"role": role, "content": content, "id": "new"}
                self.messages.append(item)
                return item

            def count_user_messages(self, user_id, session_id):
                return sum(item["role"] == "user" for item in self.messages)

            def load_short_term_messages(self, user_id, session_id, limit):
                self.load_limits.append(limit)
                return list(self.messages)[-limit:]

            def get_latest_session_summary(self, user_id, session_id):
                return None

            def get_latest_lifetime_summary(self, user_id):
                return None

            def list_all_episodes_for_user(self, user_id):
                return []

            def save_episode(self, **kwargs):
                return kwargs

        class FakeModel:
            def generate_reply(self, prompt):
                return {
                    "text": "A bounded fake answer.",
                    "prompt_tokens": 7,
                    "completion_tokens": 3,
                    "total_tokens": 10,
                    "latency_ms": 1.0,
                }

            def extract_episode_facts(self, text):
                return {"facts": []}

        def run(requested):
            repository = FakeRepository()
            service = MemoryService(
                repository=repository,
                model_adapter=FakeModel(),
                embed_text=lambda text: [1.0, 0.0],
                rank_episodes=lambda query, episodes, top_k=3: episodes[:top_k],
                config={"short_term_n": 12, "summarize_every_user_msgs": 5, "episodic_top_k": 3},
                file_memory_path=Path(tempfile.gettempdir()) / "unused-hw6-memory.md",
            )
            response = service.chat("user", "session", "Current question", requested)
            return repository, response

        default_repo, default_response = run(None)
        small_repo, small_response = run(4)
        large_repo, large_response = run(30)
        self.assertEqual(default_repo.load_limits, [12])
        self.assertEqual(small_repo.load_limits, [4])
        self.assertEqual(large_repo.load_limits, [30])
        self.assertEqual(default_response["memory_used"]["short_term_count"], 12)
        self.assertEqual(small_response["memory_used"]["short_term_count"], 4)
        self.assertEqual(large_response["memory_used"]["short_term_count"], 30)
        self.assertLess(
            small_response["component_tokens"]["short_term_window"],
            large_response["component_tokens"]["short_term_window"],
        )
        self.assertEqual(default_response["answer"], "A bounded fake answer.")

    def test_component_breakdown_is_complete_and_sums_to_estimate(self) -> None:
        current = "I prefer distributed systems."
        messages = [
            {"role": "user", "content": "Earlier context."},
            {"role": "user", "content": current},
        ]
        breakdown = memory_logic.get_memory_usage_breakdown(
            "Answer clearly.",
            "A durable goal.",
            "A session preference.",
            messages,
            current,
            [{"fact": "The user studies distributed systems."}],
        )
        keys = {
            "primer",
            "session_summary",
            "lifetime_summary",
            "short_term_window",
            "episodic_facts",
            "current_user_message",
            "estimated_prompt_total",
        }
        self.assertEqual(set(breakdown).intersection(keys), keys)
        self.assertTrue(all(isinstance(breakdown[key], int) and breakdown[key] >= 0 for key in keys))
        self.assertEqual(
            breakdown["estimated_prompt_total"],
            sum(breakdown[key] for key in keys if key != "estimated_prompt_total"),
        )
        prompt = memory_logic.build_memory_prompt(
            "Answer clearly.",
            "A durable goal.",
            "A session preference.",
            messages,
            current,
            [{"fact": "The user studies distributed systems."}],
        )
        self.assertEqual(prompt.count(current), 1)

    def test_absent_sections_are_zero_and_short_term_changes(self) -> None:
        empty = memory_logic.get_memory_usage_breakdown(
            "Primer", None, None, [], "Current question", []
        )
        self.assertEqual(empty["session_summary"], 0)
        self.assertEqual(empty["lifetime_summary"], 0)
        self.assertEqual(empty["episodic_facts"], 0)
        short = memory_logic.get_memory_usage_breakdown(
            "Primer",
            None,
            None,
            [{"role": "assistant", "content": "Earlier answer."}],
            "Current question",
            [],
        )
        self.assertGreater(short["short_term_window"], empty["short_term_window"])

    def test_service_preserves_usage_and_adds_component_breakdown(self) -> None:
        service = MemoryService.__new__(MemoryService)
        service.system_primer = "Primer"
        result = service._usage(
            {"prompt_tokens": 10, "completion_tokens": 4, "total_tokens": 14, "latency_ms": 12.5},
            None,
            None,
            [{"role": "user", "content": "Current question"}],
            "Current question",
            [],
        )
        self.assertEqual(result["prompt_tokens"], 10)
        self.assertEqual(result["completion_tokens"], 4)
        self.assertEqual(result["total_tokens"], 14)
        self.assertEqual(result["latency_ms"], 12.5)
        self.assertEqual(
            set(result["component_tokens"]),
            {
                "primer",
                "session_summary",
                "lifetime_summary",
                "short_term_window",
                "episodic_facts",
                "current_user_message",
                "estimated_prompt_total",
            },
        )
        self.assertEqual(
            result["prompt_token_total_estimate"],
            result["component_tokens"]["estimated_prompt_total"],
        )

    def test_line_and_age_triggers(self) -> None:
        now = datetime(2026, 10, 17, tzinfo=timezone.utc)
        recent = now - timedelta(hours=1)
        old = now - timedelta(hours=25)
        self.assertTrue(memory_file_requires_consolidation(FIXED_CONTENT, recent, now))
        self.assertTrue(memory_file_requires_consolidation("one line", old, now))
        self.assertFalse(memory_file_requires_consolidation("one line", recent, now))

    def test_required_55_line_fixture_and_audit(self) -> None:
        fixture_path = Path(__file__).resolve().parents[1] / "reports" / "hw06" / "raw" / "file_memory_test_input_55line.md"
        consolidated_path = fixture_path.with_name("file_memory_consolidated_55line.md")
        audit_path = fixture_path.with_name("file_memory_consolidation_audit.json")
        fixture_lines = fixture_path.read_text(encoding="utf-8").splitlines()
        consolidated_lines = [
            line for line in consolidated_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        self.assertEqual(len(fixture_lines), 55)
        self.assertGreaterEqual(len(audit["duplicate_groups"]), 3)
        self.assertEqual(len(audit["contradictions"]), 3)
        self.assertLess(len(consolidated_lines), 40)
        for contradiction in audit["contradictions"]:
            self.assertTrue(contradiction["left_original_fact"])
            self.assertTrue(contradiction["right_conflicting_fact"])
            self.assertTrue(contradiction["kept_fact"])
            self.assertTrue(contradiction["superseded_fact"])
            self.assertTrue(contradiction["reason"])
            self.assertTrue(contradiction["detector_resolved_correctly"])
            self.assertFalse(contradiction["contradiction_missed"])
        self.assertEqual(audit["missed_contradiction_count"], 0)
        self.assertTrue(audit["original_preserved"])
        self.assertTrue(audit["deterministic_output"])
        self.assertFalse(audit["external_services_contacted"])

    def test_duplicate_and_contradiction_detection(self) -> None:
        facts = ["Preference: concise", "Preference: concise", "Preference: detailed"]
        unique, duplicate_count = remove_duplicate_facts(facts)
        self.assertEqual(duplicate_count, 1)
        self.assertEqual(len(detect_contradictions(unique)), 1)

    def test_original_preserved_and_output_deterministic(self) -> None:
        now = datetime(2026, 10, 17, tzinfo=timezone.utc)
        result = consolidate_memory(FIXED_CONTENT, now=now)
        repeated = consolidate_memory(FIXED_CONTENT, now=now)
        self.assertEqual(result["original_text"], FIXED_CONTENT)
        self.assertEqual(result["consolidated_text"], repeated["consolidated_text"])
        self.assertGreater(result["duplicate_count"], 0)
        self.assertGreater(result["contradiction_count"], 0)
        self.assertLess(result["after_line_count"], result["before_line_count"])

    def test_file_round_trip_uses_temporary_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "MEMORY.md"
            write_memory_file(path, FIXED_CONTENT)
            self.assertEqual(read_memory_file(path), FIXED_CONTENT)

    def test_generated_function_verification(self) -> None:
        verification = verify_generated_consolidation(FIXED_CONTENT)
        self.assertTrue(verification["passed"])
        self.assertGreater(verification["before_line_count"], FILE_MEMORY_MAX_LINES)

    def test_fake_mongodb_comparison_is_read_only(self) -> None:
        comparison = compare_file_memory_with_mongodb(
            ["Preference: distributed systems", "Goal: modular design"],
            ["Preference: distributed systems", "Goal: reliable design"],
        )
        self.assertEqual(comparison["shared"], ["Preference: distributed systems"])
        self.assertEqual(comparison["only_in_file"], ["Goal: modular design"])
        self.assertEqual(comparison["only_in_mongodb"], ["Goal: reliable design"])

    def test_commands_integrate_file_memory_with_fake_mongodb(self) -> None:
        class FakeRepository:
            messages = [
                {"role": "user", "content": "I prefer distributed systems."},
                {"role": "assistant", "content": "Noted."},
                {"role": "user", "content": "Keep the project modular."},
            ]
            summaries: list[dict] = []
            episodes: list[dict] = []

            def count_messages(self, user_id, session_id):
                return sum(
                    item.get("user_id", user_id) == user_id
                    and item.get("session_id", session_id) == session_id
                    for item in self.messages
                )

            def count_summaries(self, user_id, session_id):
                return sum(
                    item.get("user_id", user_id) == user_id
                    and item.get("session_id", session_id) == session_id
                    and item.get("scope") == "session"
                    for item in self.summaries
                )

            def count_episodes(self, user_id, session_id):
                return sum(
                    item.get("user_id", user_id) == user_id
                    and item.get("session_id", session_id) == session_id
                    for item in self.episodes
                )

            def load_short_term_messages(self, user_id, session_id, limit):
                return list(self.messages)[-limit:]

            def get_latest_session_summary(self, user_id, session_id):
                return self.summaries[-1] if self.summaries else None

            def get_latest_lifetime_summary(self, user_id):
                return None

            def list_recent_episodes(self, user_id, limit):
                return list(self.episodes)[-limit:]

            def save_summary(self, user_id, session_id, scope, text):
                item = {"id": str(len(self.summaries) + 1), "user_id": user_id, "session_id": session_id, "scope": scope, "text": text}
                self.summaries.append(item)
                return item

            def list_recent_summaries(self, user_id, limit):
                return list(self.summaries)

            def save_episode(self, user_id, session_id, fact, importance, embedding):
                item = {"id": str(len(self.episodes) + 1), "user_id": user_id, "session_id": session_id, "fact": fact, "importance": importance, "embedding": embedding}
                self.episodes.append(item)
                return item

        class FakeModel:
            def generate_session_summary(self, text):
                return {"text": "The user prefers distributed systems and modular design."}

            def extract_episode_facts(self, text):
                return {"facts": [{"fact": "The user prefers distributed systems.", "importance": 1.0}]}

            def generate_lifetime_summary(self, text):
                return {"text": "Durable project preferences."}

        with tempfile.TemporaryDirectory() as directory:
            memory_path = Path(directory) / "MEMORY.md"
            write_memory_file(memory_path, "\n".join(f"- Note {i}" for i in range(45)))
            repository = FakeRepository()
            service = MemoryService(
                repository=repository,
                model_adapter=FakeModel(),
                embed_text=lambda text: [1.0, 0.0],
                rank_episodes=lambda query, episodes, top_k=3: episodes[:top_k],
                config={"short_term_n": 2, "summarize_every_user_msgs": 5, "episodic_top_k": 3},
                file_memory_path=memory_path,
            )
            compact = service.chat("user", "session", "/compact")
            compact_result = compact["command_result"]
            self.assertTrue(compact_result["file_consolidation"]["written"])
            self.assertTrue(compact_result["raw_messages_preserved"])
            self.assertEqual(compact_result["before"]["messages"], 3)
            self.assertEqual(compact_result["after"]["messages"], 3)
            self.assertEqual(compact_result["before"]["summaries"], 0)
            self.assertEqual(compact_result["after"]["summaries"], 1)
            self.assertEqual(compact_result["before"]["episodes"], 0)
            self.assertEqual(compact_result["after"]["episodes"], 1)
            self.assertEqual(compact_result["facts_added"], 1)
            self.assertTrue(compact_result["summary_created"])
            self.assertFalse(compact_result["lifetime_summary_created"])
            self.assertGreaterEqual(
                compact_result["before"]["file_memory_physical_lines"],
                compact_result["after"]["file_memory_physical_lines"],
            )

            dream = service.chat("user", "session", "/dream")
            dream_result = dream["command_result"]["file_memory"]
            self.assertIn("The user prefers distributed systems.", dream_result["facts_added"])
            self.assertTrue(Path(str(memory_path) + ".before-hw6").exists())

            duplicate_dream = service.chat("user", "session", "/dream")
            self.assertEqual(duplicate_dream["command_result"]["file_memory"]["facts_added"], [])

            old_timestamp = time.time() - (25 * 60 * 60)
            os.utime(memory_path, (old_timestamp, old_timestamp))
            age_compact = service.chat("user", "session", "/compact")
            self.assertTrue(age_compact["command_result"]["file_consolidation"]["written"])

            snapshot = service.chat("user", "session", "/memory")
            self.assertIn("file_memory", snapshot["memory_used"])
            help_result = service.chat("user", "session", "/help")
            self.assertIn("MEMORY.md", help_result["answer"])
            self.assertEqual(len(repository.messages), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
