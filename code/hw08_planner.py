"""Separate HW8 Planner process entry point."""

from __future__ import annotations

import asyncio

from hw08_agent_pipeline import run_stage
from hw08_kafka_config import INBOX_TOPIC, PLANNER_CONSUMER_GROUP, TASKS_TOPIC


def main() -> None:  # pragma: no cover - live execution only
    asyncio.run(
        run_stage(
            input_topic=INBOX_TOPIC,
            output_topic=TASKS_TOPIC,
            group_id=PLANNER_CONSUMER_GROUP,
            stage="planner",
        )
    )


if __name__ == "__main__":
    main()

