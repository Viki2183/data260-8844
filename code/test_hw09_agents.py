from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from hw09.agent_system import AnsweringAgent, load_reference
from hw09.evaluator import evaluate
from hw09.lesson_store import LessonStore
from hw09.run_agent_variants import retain_lesson_after_validation, run_variant


class Hw09AgentTests(unittest.TestCase):
    def setUp(self):
        self.reference = load_reference(
            ROOT / "reports" / "hw09" / "cases" / "reference_data.json"
        )

    def test_evaluator_pass_and_revise(self):
        agent = AnsweringAgent(self.reference)
        question = "Which versions of package alpha are affected?"
        bad = "Package alpha is affected."
        self.assertEqual(evaluate(question, bad, self.reference)["result"], "REVISE")
        good = agent.answer(
            question,
            attempt=2,
            feedback="Include the complete reference fact and avoid unsupported claims.",
        )
        self.assertEqual(evaluate(question, good, self.reference)["result"], "PASS")

    def test_repair_is_bounded_to_two_attempts(self):
        question = "Which versions of package alpha are affected?"
        result = run_variant("Evaluator Repair", [question], self.reference)[0]
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["evaluation"]["result"], "PASS")
        self.assertTrue(result["feedback_used"])

    def test_feedback_changes_second_attempt_outcome(self):
        agent = AnsweringAgent(self.reference)
        question = "Which versions of package alpha are affected?"
        without_feedback = agent.answer(question, attempt=2)
        with_feedback = agent.answer(
            question,
            attempt=2,
            feedback="Include the complete reference fact and avoid unsupported claims.",
        )
        self.assertEqual(evaluate(question, without_feedback, self.reference)["result"], "REVISE")
        self.assertEqual(evaluate(question, with_feedback, self.reference)["result"], "PASS")

    def test_lesson_is_created_loaded_and_counted(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LessonStore(Path(directory) / "lessons.json")
            lesson = store.create("alpha incomplete answer", "Include the complete reference fact.")
            selected = store.relevant("alpha incomplete answer")
            self.assertEqual(selected[0]["lesson_id"], lesson["lesson_id"])
            self.assertEqual(store.load()[0]["use_count"], 1)

    def test_input_datasets_do_not_contain_answers(self):
        for name in ("training_data.json", "validation_data.json", "test_data.json"):
            path = ROOT / "reports" / "hw09" / "cases" / name
            records = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(all(set(record) == {"question"} for record in records))

    def test_validated_improvement_retains_only_non_regressions(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LessonStore(Path(directory) / "lessons.json")
            candidate = {"failure_pattern": "alpha", "correction": "use the reference fact"}
            kept = retain_lesson_after_validation(
                store, candidate,
                {"failure_cases_incorrect": 2, "unrelated_unsupported": 0},
                {"failure_cases_incorrect": 1, "previously_correct_still_correct": True,
                 "unrelated_unsupported": 0},
            )
            self.assertTrue(kept)
            rejected = retain_lesson_after_validation(
                store, candidate,
                {"failure_cases_incorrect": 1, "unrelated_unsupported": 0},
                {"failure_cases_incorrect": 2, "previously_correct_still_correct": False,
                 "unrelated_unsupported": 1},
            )
            self.assertFalse(rejected)


if __name__ == "__main__":
    unittest.main()
