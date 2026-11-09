"""Create a lesson from training data and prove reuse on a later related question."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from hw09.agent_system import AnsweringAgent, load_reference
from hw09.evaluator import evaluate
from hw09.lesson_store import LessonStore


def main() -> None:
    reference = load_reference()
    agent = AnsweringAgent(reference)
    path = ROOT / "reports" / "hw09" / "raw" / "lessons.json"
    path.write_text("[]\n", encoding="utf-8")
    store = LessonStore(path)
    first_question = "Which versions of package alpha are affected?"
    initial = agent.answer(first_question)
    initial_evaluation = evaluate(first_question, initial, reference)
    lesson = store.create("alpha affected versions", initial_evaluation["correction"])
    later_question = "Which releases of alpha are affected?"
    loaded = store.relevant(later_question)
    later_answer = agent.answer(later_question, lessons=loaded)
    result = {
        "student": "Vrishin KunnathamParambath", "sid4": "8844",
        "first_failed_question": first_question, "initial_answer": initial,
        "evaluator_feedback": initial_evaluation["feedback"],
        "lesson_created": lesson, "lessons_after_creation": [lesson],
        "later_related_question": later_question, "lesson_loaded": loaded,
        "use_count_after_reuse": store.load()[0]["use_count"],
        "later_answer": later_answer,
        "later_evaluation": evaluate(later_question, later_answer, reference),
    }
    target = ROOT / "reports" / "hw09" / "raw" / "lesson_reuse_final.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
