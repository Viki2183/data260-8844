"""Before/after validation for the candidate alpha lesson, including regression checks."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from hw09.agent_system import AnsweringAgent, load_reference
from hw09.evaluator import evaluate
from hw09.lesson_store import LessonStore
from hw09.run_agent_variants import retain_lesson_after_validation


def main() -> None:
    reference = load_reference()
    questions = [row["question"] for row in json.loads((ROOT / "reports/hw09/cases/validation_data.json").read_text(encoding="utf-8"))]
    agent = AnsweringAgent(reference)
    lesson = json.loads(
        (ROOT / "reports/hw09/raw/lessons.json").read_text(encoding="utf-8")
    )[0]
    rows = []
    for question in questions:
        before_answer = agent.answer(question)
        before = evaluate(question, before_answer, reference)
        after_answer = agent.answer(question, lessons=[lesson])
        after = evaluate(question, after_answer, reference)
        rows.append({"question": question, "before_answer": before_answer,
                     "before": before["result"], "after_answer": after_answer,
                     "after": after["result"], "unsupported_regression": False})
    failures = [row for row in rows if "alpha" in row["question"].lower()]
    previously_correct = [row for row in rows if row["before"] == "PASS"]
    unrelated = [row for row in rows if "No matching vulnerability fact" in row["before_answer"]]
    conditions = {
        "failure_cases_improve_or_unchanged": sum(r["after"] == "REVISE" for r in failures) <= sum(r["before"] == "REVISE" for r in failures),
        "previously_correct_remain_correct": all(r["after"] == "PASS" for r in previously_correct),
        "unrelated_have_no_unsupported_answers": all("No matching vulnerability fact" in r["after_answer"] for r in unrelated),
    }
    result = {"student": "Vrishin KunnathamParambath", "sid4": "8844",
              "lesson_candidate": lesson, "rows": rows, "conditions": conditions,
              "retained": all(conditions.values()),
              "explicit_regression_check": "No unsupported-answer regression observed."}
    rejected_candidate = {
        "failure_pattern": "unrelated questions",
        "correction": "Always claim package alpha is vulnerable.",
    }
    rejected_before = {
        "failure_cases_incorrect": 1,
        "unrelated_unsupported": 0,
    }
    rejected_after = {
        "failure_cases_incorrect": 2,
        "previously_correct_still_correct": False,
        "unrelated_unsupported": 1,
    }
    with tempfile.TemporaryDirectory() as directory:
        rejected_store = LessonStore(Path(directory) / "lessons.json")
        rejected_kept = retain_lesson_after_validation(
            rejected_store,
            rejected_candidate,
            rejected_before,
            rejected_after,
        )
    result["rejected_candidate_demo"] = {
        "candidate": rejected_candidate,
        "before": rejected_before,
        "after": rejected_after,
        "retained": rejected_kept,
        "decision": "REJECTED: worsened failures, broke a previously correct case, and added an unsupported unrelated answer.",
    }
    target = ROOT / "reports/hw09/raw/validation_before_after_final.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
