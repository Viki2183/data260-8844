"""Offline observation and correlation for the existing HW8 Kafka evidence.

This module never publishes, commits, seeks, or acknowledges Kafka records. It
only reads exported JSONL evidence and joins existing records by
``correlation_id``. The correlation ID is the HW10 trace ID; no second request
identifier is created.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping


STAGE_NAMES = ("input", "planner", "writer", "reviewer")
STAGE_TOPICS = {
    "input": "s8844_inbox",
    "planner": "s8844_tasks",
    "writer": "s8844_drafts",
    "reviewer": "s8844_final",
}


def read_jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    """Yield JSON objects from an exported evidence file."""
    evidence_path = Path(path)
    with evidence_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{evidence_path}:{line_number} is not a JSON object")
            yield value


def _message(record: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = record.get("message")
    return value if isinstance(value, Mapping) else None


def _correlation_id(record: Mapping[str, Any]) -> str | None:
    direct = record.get("correlation_id")
    if direct:
        return str(direct)
    message = _message(record)
    if message and message.get("correlation_id"):
        return str(message["correlation_id"])
    return None


def normalize_observation(record: Mapping[str, Any], source: str | Path) -> dict[str, Any] | None:
    """Normalize one exported stage record without changing its envelope."""
    correlation_id = _correlation_id(record)
    if not correlation_id:
        return None

    stage = str(record.get("stage", "")).lower()
    if stage not in STAGE_NAMES:
        process = str(record.get("process", "")).lower()
        stage = process if process in STAGE_NAMES else stage

    message = _message(record)
    topic = record.get("topic")
    if topic is None and stage in STAGE_TOPICS:
        topic = STAGE_TOPICS[stage]
    timestamp = record.get("timestamp")
    if timestamp is None and message is not None:
        timestamp = message.get("timestamp")

    return {
        "correlation_id": correlation_id,
        "stage": stage or None,
        "topic": topic,
        "partition": record.get("partition"),
        "offset": record.get("offset"),
        "timestamp": timestamp,
        "message_type": message.get("message_type") if message else record.get("message_type"),
        "message": dict(message) if message else None,
        "source_file": str(source),
    }


def join_by_correlation(
    records: Iterable[Mapping[str, Any]],
    *,
    source: str | Path,
) -> list[dict[str, Any]]:
    """Join observed stages by the existing correlation ID."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        observation = normalize_observation(record, source)
        if observation is not None:
            grouped[observation["correlation_id"]].append(observation)

    traces: list[dict[str, Any]] = []
    for correlation_id, observations in sorted(grouped.items()):
        by_stage: dict[str, dict[str, Any]] = {}
        for observation in observations:
            stage = observation.get("stage")
            if stage in STAGE_NAMES:
                by_stage.setdefault(stage, observation)
        missing = [stage for stage in STAGE_NAMES if stage not in by_stage]
        traces.append(
            {
                "correlation_id": correlation_id,
                "stages": by_stage,
                "complete": not missing,
                "missing_stages": missing,
                "observation_count": len(observations),
                "source_files": sorted({item["source_file"] for item in observations}),
            }
        )
    return traces


def observe_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Read one exported JSONL file and return correlation-joined traces."""
    return join_by_correlation(read_jsonl(path), source=path)
