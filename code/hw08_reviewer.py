"""Separate HW8 Reviewer process entry point."""

from __future__ import annotations

import asyncio

from hw08_agent_pipeline import run_stage
from hw08_kafka_config import DRAFTS_TOPIC, FINAL_TOPIC, REVIEWER_CONSUMER_GROUP


def main() -> None:  # pragma: no cover - live execution only
    asyncio.run(
        run_stage(
            input_topic=DRAFTS_TOPIC,
            output_topic=FINAL_TOPIC,
            group_id=REVIEWER_CONSUMER_GROUP,
            stage="reviewer",
        )
    )


if __name__ == "__main__":
    main()

