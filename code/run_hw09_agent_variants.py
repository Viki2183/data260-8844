"""Run the unchanged held-out dataset independently against four variants."""

from __future__ import annotations

import json
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from hw09.agent_system import load_reference
from hw09.lesson_store import LessonStore
from hw09.run_agent_variants import load_questions, run_variant
from hw09.agent_system import AnsweringAgent
from hw09.evaluator import evaluate


def main() -> None:
    reference = load_reference()
    questions = load_questions(ROOT / "reports" / "hw09" / "cases" / "test_data.json")
    saved_lessons = json.loads((ROOT / "reports" / "hw09" / "raw" / "lessons.json").read_text(encoding="utf-8"))
    output, summary = {}, []
    for name in ("Baseline", "Evaluator Repair", "Lesson Memory", "Validated Improvement"):
        with tempfile.TemporaryDirectory() as directory:
            store = None
            if name in {"Lesson Memory", "Validated Improvement"}:
                lesson_path = Path(directory) / "lessons.json"
                lesson_path.write_text(json.dumps(saved_lessons, indent=2) + "\n", encoding="utf-8")
                store = LessonStore(lesson_path)
            rows = run_variant(name, questions, reference, store)
        output[name] = rows
        correct = sum(row["evaluation"]["result"] == "PASS" for row in rows)
        summary.append({
            "variant": name, "correct": correct, "incorrect": len(rows) - correct,
            "average_attempts": statistics.mean(row["attempts"] for row in rows),
            "average_latency_ms": statistics.mean(row["latency_ms"] for row in rows),
            "agent_type": "deterministic reference-grounded rule system",
        })
    raw = ROOT / "reports" / "hw09" / "raw"
    (raw / "agent_variants_final.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    (raw / "agent_variant_summary_final.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    revision_question = "Which versions of package alpha are affected?"
    revision_agent = AnsweringAgent(reference)
    initial_answer = revision_agent.answer(revision_question)
    initial_evaluation = evaluate(revision_question, initial_answer, reference)
    revised_answer = revision_agent.answer(
        revision_question,
        attempt=2,
        feedback=initial_evaluation["feedback"],
    )
    revision = {
        "question": revision_question,
        "initial_answer": initial_answer,
        "initial_evaluator_result": initial_evaluation["result"],
        "evaluator_feedback": initial_evaluation["feedback"],
        "revision_generated_by": "AnsweringAgent.answer",
        "revised_answer": revised_answer,
        "final_evaluation": evaluate(revision_question, revised_answer, reference),
        "attempt_count": 2,
        "final_returned_response": revised_answer,
    }
    (raw / "revision_sequence_final.json").write_text(json.dumps(revision, indent=2) + "\n", encoding="utf-8")
    print("Vrishin KunnathamParambath\nSID4: 8844")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
