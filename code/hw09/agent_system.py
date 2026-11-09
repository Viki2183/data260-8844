"""Deterministic vulnerability-domain Answering Agent variants."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REFERENCE_PATH = ROOT / "reports" / "hw09" / "cases" / "reference_data.json"


def load_reference(path: Path = REFERENCE_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def retrieve_facts(question: str, reference: list[dict[str, Any]]) -> list[dict[str, Any]]:
    words = set(question.lower().replace("?", " ").replace(",", " ").split())
    ranked = []
    for fact in reference:
        overlap = len(words & set(fact["keywords"]))
        if overlap:
            ranked.append((overlap, fact))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [fact for _, fact in ranked[:3]]


class AnsweringAgent:
    def __init__(self, reference: list[dict[str, Any]] | None = None):
        self.reference = reference or load_reference()

    def answer(
        self,
        question: str,
        lessons: list[dict[str, Any]] | None = None,
        attempt: int = 1,
        feedback: str | None = None,
    ) -> str:
        facts = retrieve_facts(question, self.reference)
        if not facts:
            return "No matching vulnerability fact was found in the reference dataset."
        applicable = [
            lesson for lesson in (lessons or [])
            if fact_matches_lesson(facts[0], lesson)
        ]
        if applicable:
            return str(applicable[0]["correction"])
        if facts[0].get("baseline_failure"):
            if attempt == 1:
                return str(facts[0]["incomplete_fact"])
            if feedback and "complete reference fact" in feedback.lower():
                # The Answering Agent retrieves the full fact only when the
                # evaluator identifies the omission in its feedback.
                return str(facts[0]["fact"])
            return str(facts[0]["incomplete_fact"])
        return str(facts[0]["fact"])


def fact_matches_lesson(fact: dict[str, Any], lesson: dict[str, Any]) -> bool:
    pattern = set(str(lesson["failure_pattern"]).lower().split())
    return bool(pattern & set(fact["keywords"]))


def run_baseline(question: str, agent: AnsweringAgent) -> dict[str, Any]:
    started = time.perf_counter()
    answer = agent.answer(question)
    return {
        "question": question,
        "answer": answer,
        "attempts": 1,
        "latency_ms": (time.perf_counter() - started) * 1000,
    }
