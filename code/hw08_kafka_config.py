"""Offline-safe DATA260 HW8 Kafka configuration constants."""

from __future__ import annotations

import os

PORT_BASE = 8744
PREFIX = "s8844"
SEED = 8844
VERIFY_SEED = 268844
DOMAIN_ID = 4
MODEL = "qwen3:8b"
OLLAMA_URL = "http://127.0.0.1:11434"
DATABASE_NAME = "s8844_rel"

ENTITY_REQUESTS_TOPIC = f"{PREFIX}_entity_requests"
ENTITY_RESPONSES_TOPIC = f"{PREFIX}_entity_responses"
INBOX_TOPIC = f"{PREFIX}_inbox"
TASKS_TOPIC = f"{PREFIX}_tasks"
DRAFTS_TOPIC = f"{PREFIX}_drafts"
FINAL_TOPIC = f"{PREFIX}_final"
DEAD_LETTER_TOPIC = f"{PREFIX}_dead_letter"

ENTITY_REQUEST_TOPICS = (ENTITY_REQUESTS_TOPIC, ENTITY_RESPONSES_TOPIC)
AGENT_TOPICS = (INBOX_TOPIC, TASKS_TOPIC, DRAFTS_TOPIC, FINAL_TOPIC)
DEFAULT_MAX_ATTEMPTS = 3
ORDERING_MESSAGE_COUNT = 20
ORDERING_PARTITION_COUNT = 2

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")
ENTITY_CONSUMER_GROUP = f"{PREFIX}-entity-worker"
PLANNER_CONSUMER_GROUP = f"{PREFIX}-planner"
WRITER_CONSUMER_GROUP = f"{PREFIX}-writer"
REVIEWER_CONSUMER_GROUP = f"{PREFIX}-reviewer"


def all_required_topics() -> tuple[str, ...]:
    """Return the exact HW8 topic set without contacting Kafka."""
    return (
        ENTITY_REQUESTS_TOPIC,
        ENTITY_RESPONSES_TOPIC,
        INBOX_TOPIC,
        TASKS_TOPIC,
        DRAFTS_TOPIC,
        FINAL_TOPIC,
        DEAD_LETTER_TOPIC,
    )


def topic_creation_commands(
    bootstrap_servers: str = KAFKA_BOOTSTRAP_SERVERS,
) -> tuple[tuple[str, ...], ...]:
    """Return reviewable Kafka CLI commands; never execute them."""
    commands = []
    for topic in all_required_topics():
        partitions = "2" if topic == TASKS_TOPIC else "1"
        commands.append(
            (
                "kafka-topics",
                "--create",
                "--if-not-exists",
                "--topic",
                topic,
                "--partitions",
                partitions,
                "--replication-factor",
                "1",
                "--bootstrap-server",
                bootstrap_servers,
            )
        )
    return tuple(commands)


def validate_topic_set(actual_topics: set[str]) -> None:
    """Raise if a broker inventory is not exactly the required HW8 set."""
    expected = set(all_required_topics())
    if actual_topics != expected:
        raise ValueError(
            f"HW8 topic mismatch; missing={sorted(expected - actual_topics)}, "
            f"unexpected={sorted(actual_topics - expected)}"
        )

