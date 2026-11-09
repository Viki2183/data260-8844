"""Run the four independent HW9 agent variants on input-only datasets."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .agent_system import AnsweringAgent
from .evaluator import evaluate
from .lesson_store import LessonStore


def load_questions(path: Path) -> list[str]:
    return [str(row["question"]) for row in json.loads(path.read_text(encoding="utf-8"))]


def retain_lesson_after_validation(
    store: LessonStore,
    candidate: dict[str, Any],
    before: dict[str, int],
    after: dict[str, int],
) -> bool:
    """Keep only when all three assignment validation conditions pass."""
    acceptable = (
        after["failure_cases_incorrect"] <= before["failure_cases_incorrect"]
        and after["previously_correct_still_correct"]
        and after["unrelated_unsupported"] <= before["unrelated_unsupported"]
    )
    if acceptable:
        store.create(candidate["failure_pattern"], candidate["correction"])
    return acceptable


def run_variant(
    name: str,
    questions: list[str],
    reference: list[dict[str, Any]],
    store: LessonStore | None = None,
) -> list[dict[str, Any]]:
    agent = AnsweringAgent(reference)
    results = []
    for question in questions:
        started = time.perf_counter()
        lessons = (
            store.relevant(question)
            if name in {"Lesson Memory", "Validated Improvement"} and store
            else []
        )
        answer = agent.answer(question, lessons=lessons)
        attempts = 1
        evaluation = evaluate(question, answer, reference)
        if name == "Evaluator Repair" and evaluation["result"] == "REVISE":
            answer = agent.answer(
                question,
                lessons=lessons,
                attempt=2,
                feedback=evaluation["feedback"],
            )
            evaluation = evaluate(question, answer, reference)
            attempts = 2
        results.append(
            {
                "question": question,
                "answer": answer,
                "evaluation": evaluation,
                "attempts": attempts,
                "feedback_used": attempts == 2,
                "latency_ms": (time.perf_counter() - started) * 1000,
            }
        )
    return results
