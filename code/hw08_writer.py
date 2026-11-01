"""Separate HW8 Writer process entry point."""

from __future__ import annotations

import asyncio

from hw08_agent_pipeline import run_stage
from hw08_kafka_config import DRAFTS_TOPIC, TASKS_TOPIC, WRITER_CONSUMER_GROUP


def main() -> None:  # pragma: no cover - live execution only
    asyncio.run(
        run_stage(
            input_topic=TASKS_TOPIC,
            output_topic=DRAFTS_TOPIC,
            group_id=WRITER_CONSUMER_GROUP,
            stage="writer",
        )
    )


if __name__ == "__main__":
    main()

