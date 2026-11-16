"""Prepare HW10 candidate cases from existing-domain questions.

The source questions are copied from the already existing HW9 cache-case
fixture. Candidate drafts replay the unchanged HW8 deterministic Writer
transformation offline. This script is intentionally not run by import and
does not contact Kafka, Redis, Ollama, or the application API.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


QUESTION_PATTERN = re.compile(r"^  query: (.+)$")


def read_existing_questions(source: Path) -> list[str]:
    questions: list[str] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        match = QUESTION_PATTERN.match(line)
        if match:
            questions.append(match.group(1))
    if len(questions) < 20:
        raise ValueError("existing cache fixture does not contain 20 questions")
    return questions[:20]


def build_cases(source: Path) -> list[dict[str, str]]:
    questions = read_existing_questions(source)
    cases = []
    for index, question in enumerate(questions, start=1):
        correlation_id = f"hw10-offline-eval-{index:02d}"
        source_group = "exact_duplicate" if index <= 10 else "paraphrase"
        source_question_id = f"{source_group.replace('_duplicate', '')}-{index:02d}"
        if index <= 10:
            source_question_id = f"exact-{index:02d}"
        else:
            source_question_id = f"paraphrase-{index - 10:02d}"
        cases.append(
            {
                "case_id": f"hw10-case-{index:02d}",
                "correlation_id": correlation_id,
                "source_question_id": source_question_id,
                "source_label": source_group,
                "source_file": "reports/hw09/cases/cache_cases.yaml",
                "question": question,
                "candidate_draft": f"Draft based on Plan: answer {question}",
                "draft_provenance": "offline_replay_of_code/hw08_agent_pipeline.py:transform_stage",
            }
        )
    return cases


def write_cases(source: Path, destination: Path) -> None:
    destination.write_text(json.dumps(build_cases(source), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover - file-preparation CLI
    repository = Path(__file__).resolve().parents[2]
    write_cases(
        repository / "reports" / "hw09" / "cases" / "cache_cases.yaml",
        repository / "reports" / "hw10" / "eval_cases.json",
    )
