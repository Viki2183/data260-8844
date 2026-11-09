"""Reference-data evaluator returning PASS or REVISE."""

from __future__ import annotations

from typing import Any

from .agent_system import retrieve_facts


def evaluate(question: str, answer: str, reference: list[dict[str, Any]]) -> dict[str, Any]:
    facts = retrieve_facts(question, reference)
    if not facts:
        passed = "No matching vulnerability fact" in answer
        return {
            "result": "PASS" if passed else "REVISE",
            "feedback": "Keep the answer grounded in the reference dataset.",
            "expected_fact_ids": [],
        }
    expected = facts[0]
    passed = expected["fact"].lower() in answer.lower()
    return {
        "result": "PASS" if passed else "REVISE",
        "feedback": "Include the complete reference fact and avoid unsupported claims.",
        "expected_fact_ids": [expected["fact_id"]],
        "correction": expected["fact"],
    }
