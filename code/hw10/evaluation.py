"""Offline checks for HW10 Writer-draft evaluation candidates."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


ALLOWED_HUMAN_LABELS = {
    "correct",
    "minor_error",
    "major_error",
    "unsupported",
    "unanswerable",
}


def load_cases(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, list):
        raise ValueError("evaluation cases must be a JSON list")
    return [dict(item) for item in value]


def load_candidate_labels(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def evaluate_writer_shape(case: Mapping[str, Any]) -> dict[str, Any]:
    """Check only deterministic Writer-shape invariants, not semantic truth."""
    question = str(case["question"])
    draft = str(case["candidate_draft"])
    expected_prefix = "Draft based on Plan: answer "
    return {
        "correlation_id": str(case["correlation_id"]),
        "question_preserved": question in draft,
        "writer_prefix_present": draft.startswith(expected_prefix),
        "plan_marker_present": "Plan: answer " in draft,
        "semantic_label": None,
        "human_label_required": True,
    }


def validate_candidate_labels(
    cases: Iterable[Mapping[str, Any]],
    labels: Iterable[Mapping[str, str]],
) -> dict[str, Any]:
    """Validate the pending label file without freezing or changing labels."""
    case_ids = {str(case["case_id"]) for case in cases}
    rows = list(labels)
    label_ids = {str(row.get("case_id", "")) for row in rows}
    invalid_labels = sorted(
        {
            row.get("candidate_label", "")
            for row in rows
            if row.get("candidate_label", "") and row.get("candidate_label") not in ALLOWED_HUMAN_LABELS
        }
    )
    return {
        "case_count": len(case_ids),
        "label_row_count": len(rows),
        "all_cases_covered": case_ids == label_ids,
        "invalid_labels": invalid_labels,
        "labels_frozen": False,
        "manual_confirmation_required": True,
    }
