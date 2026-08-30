import json
from pathlib import Path

from src.model_client import ModelClient


AGENT_PATH = Path("AGENT.md")

OUTPUT_PATH = Path(
    "reports/hw01/raw/client_conversation.json"
)


def is_bullet_only(response: str) -> bool:
    """Check that every non-empty response line is a bullet."""

    lines = [
        line.strip()
        for line in response.splitlines()
        if line.strip()
    ]

    return bool(lines) and all(
        line.startswith("- ")
        for line in lines
    )


def save_conversation(
    history: list[dict[str, str]],
    stats_snapshots: list[dict],
    client: ModelClient,
) -> None:
    """Save conversation history and token statistics."""

    output = {
        "history": history,
        "stats_snapshots": stats_snapshots,
        "final_stats": client.stats(history),
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_PATH.write_text(
        json.dumps(output, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    if not AGENT_PATH.exists():
        raise FileNotFoundError(
            "AGENT.md was not found in the project folder."
        )

    system_prompt = AGENT_PATH.read_text(
        encoding="utf-8"
    )

    system_prompt += "\n\n/no_think"

    client = ModelClient(
        model="qwen3:8b",
        temperature=0.0,
        json_mode=False,
    )

    history: list[dict[str, str]] = []
    stats_snapshots: list[dict] = []

    print("DATA 260 HW1 Code Review Client")
    print("Commands: /stats and /exit")
    print(
        "Complete five model turns. Use /stats after "
        "turn 3 and after turn 5.\n"
    )

    try:
        while True:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input == "/exit":
                break

            if user_input == "/stats":
                stats = client.stats(history)
                stats["after_turn"] = client.turn_count
                stats_snapshots.append(stats)

                print("\n/stats")
                print(json.dumps(stats, indent=2))
                print()

                save_conversation(
                    history,
                    stats_snapshots,
                    client,
                )
                continue

            history.append({
                "role": "user",
                "content": user_input,
            })

            messages = [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                *history,
            ]

            try:
                result = client.complete(messages)
            except Exception:
                history.pop()
                raise

            response = result["content"].strip()

            print(f"\nAssistant:\n{response}")
            print(
                "\nBullet-only verification:",
                "PASS" if is_bullet_only(response) else "FAIL",
                "\n",
            )

            history.append({
                "role": "assistant",
                "content": response,
            })

            save_conversation(
                history,
                stats_snapshots,
                client,
            )

    finally:
        save_conversation(
            history,
            stats_snapshots,
            client,
        )
        client.print_final_stats()
        print(f"\nSaved conversation to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()