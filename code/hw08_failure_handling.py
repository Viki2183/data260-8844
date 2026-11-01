"""Pure HW8 failure-handling decisions; no broker access."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from hw08_kafka_config import DEAD_LETTER_TOPIC, DEFAULT_MAX_ATTEMPTS

POISON_FIXTURE_MARKER = "hw8_poison_fixture"


def should_retry(attempt: int, *, max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> bool:
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    return 1 <= attempt < max_attempts


def classify_poison_message(message: Mapping[str, Any]) -> str | None:
    """Recognize only the explicit HW8 poison fixture marker."""
    metadata = message.get("metadata", {})
    if not isinstance(metadata, Mapping):
        return None
    if metadata.get("fixture") == POISON_FIXTURE_MARKER:
        return "intentional_poison_fixture"
    if metadata.get("poison_fixture") is True:
        return "intentional_poison_fixture"
    return None


def poison_attempt_records(
    message: Mapping[str, Any],
    *,
    error_type: str,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> list[dict[str, Any]]:
    """Return bounded failure records without resending the source message."""
    first_attempt = int(message.get("attempt", 1))
    if first_attempt < 1:
        raise ValueError("message attempt must be positive")
    if first_attempt > max_attempts:
        raise ValueError("message attempt exceeds max_attempts")
    return [
        {
            "attempt": attempt,
            "error_type": error_type,
            "classification": "intentional_poison",
            "retry_scheduled": should_retry(attempt, max_attempts=max_attempts),
        }
        for attempt in range(first_attempt, max_attempts + 1)
    ]


def should_commit_after_success(*, processed: bool, published: bool, error: bool) -> bool:
    return processed and published and not error


def dead_letter_message(
    message: Mapping[str, Any],
    *,
    error_type: str,
    source_topic: str,
    source_partition: int | None = None,
    source_offset: int | None = None,
    attempt: int | None = None,
    failure_metadata: list[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    final_attempt = int(attempt if attempt is not None else message.get("attempt", 1))
    metadata = {
        **dict(message.get("metadata", {})),
        "dead_letter_topic": DEAD_LETTER_TOPIC,
        "error_type": error_type,
        "failure_classification": "intentional_poison",
        "source_topic": source_topic,
        "source_partition": source_partition,
        "source_offset": source_offset,
        "attempts": final_attempt,
        "failed_attempts": [dict(item) for item in (failure_metadata or ())],
    }
    return {
        "message_type": "dead_letter",
        "correlation_id": message.get("correlation_id"),
        "data": dict(message.get("data", {})),
        "attempt": final_attempt,
        "timestamp": message.get("timestamp", "offline"),
        "metadata": metadata,
        "original_message": dict(message),
    }


def should_commit_after_dead_letter(*, published: bool) -> bool:
    """Commit the source only after the DLT publication is confirmed."""
    return published


def consumer_death_actions(*, committed_before_failure: bool) -> tuple[str, ...]:
    """Describe expected redelivery behavior without killing a process."""
    if committed_before_failure:
        return ("no_redelivery_expected",)
    return ("restart_consumer", "redeliver_message", "process_idempotently", "commit_after_success")

