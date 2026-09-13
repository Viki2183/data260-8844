"""Stateful LangGraph workflow for DATA 260 Homework 2."""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, TypedDict

from pydantic import BaseModel, Field, ValidationError, field_validator
from langgraph.graph import END, START, StateGraph


# Add the repository root so Python can find src/model_client.py.
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent

if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from src.model_client import ModelClient


class PlannerOutput(BaseModel):
    """Validated output required from the Planner."""

    tags: list[str] = Field(..., min_length=3, max_length=3)
    summary: str

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: list[str]) -> list[str]:
        """Require three distinct tags between 3 and 30 characters."""
        cleaned_tags = []

        for tag in tags:
            if not isinstance(tag, str):
                raise ValueError("Every tag must be a string.")

            cleaned_tag = " ".join(tag.split())

            if not 3 <= len(cleaned_tag) <= 30:
                raise ValueError(
                    "Every tag must contain 3 to 30 characters."
                )

            if cleaned_tag.lower() in {
                item.lower() for item in cleaned_tags
            }:
                raise ValueError("Tags must be distinct.")

            cleaned_tags.append(cleaned_tag)

        return cleaned_tags

    @field_validator("summary")
    @classmethod
    def validate_summary(cls, summary: str) -> str:
        """Require a non-empty summary of at most 25 words."""
        cleaned_summary = " ".join(summary.split())

        if not cleaned_summary:
            raise ValueError("The summary cannot be empty.")

        if len(cleaned_summary.split()) > 25:
            raise ValueError(
                "The summary must contain at most 25 words."
            )

        return cleaned_summary


class AgentState(TypedDict, total=False):
    """Shared memory used by every LangGraph node."""

    title: str
    content: str
    email: str
    strict: bool
    task: str
    llm: Any
    planner_proposal: dict[str, Any]
    reviewer_feedback: dict[str, Any]
    validation_error: str
    turn_count: int
    max_turns: int
    final_output: dict[str, Any]


def clean_model_text(value: Any) -> str:
    """Normalize model text before parsing it."""
    text = str(value or "")
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE)
    return " ".join(text.replace("```", "").split())


def extract_json_object(value: Any) -> dict[str, Any]:
    """Extract the first JSON object from model output."""
    cleaned_text = clean_model_text(value)

    try:
        parsed = json.loads(cleaned_text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass

    start = cleaned_text.find("{")

    if start == -1:
        return {}

    depth = 0
    inside_string = False
    escaped = False

    for index in range(start, len(cleaned_text)):
        character = cleaned_text[index]

        if escaped:
            escaped = False
            continue

        if character == "\\":
            escaped = True
            continue

        if character == '"':
            inside_string = not inside_string
            continue

        if inside_string:
            continue

        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1

            if depth == 0:
                candidate = cleaned_text[start:index + 1]

                try:
                    parsed = json.loads(candidate)
                    return parsed if isinstance(parsed, dict) else {}
                except json.JSONDecodeError:
                    return {}

    return {}


def planner_node(state: AgentState) -> dict[str, Any]:
    """Ask the model for tags and a summary, then validate the result."""
    print("--- NODE: Planner ---")

    client: ModelClient = state["llm"]

    planner_prompt = {
        "task": state["task"],
        "title": state["title"],
        "content": state["content"],
        "previous_validation_error": state.get(
            "validation_error",
            "",
        ),
        "requirements": {
            "tags": "exactly three distinct strings",
            "tag_length": "each tag must contain 3 to 30 characters",
            "summary": "at most 25 words",
        },
    }

    messages = [
        {
            "role": "system",
            "content": (
                "You are the Planner. Return only one JSON object "
                "with this shape: "
                '{"tags": ["tag one", "tag two", "tag three"], '
                '"summary": "one short summary"}. '
                "Use only information from the supplied input."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(planner_prompt),
        },
    ]

    started = time.perf_counter()
    response = client.complete(messages)
    latency_ms = (time.perf_counter() - started) * 1000

    raw_output = extract_json_object(response.get("content", ""))
    data = raw_output.get("data", raw_output)

    try:
        validated = PlannerOutput.model_validate(data)

        proposal = validated.model_dump()

        print(
            f"Planner produced valid output in "
            f"{latency_ms:.0f} ms."
        )

        return {
            "planner_proposal": proposal,
            "validation_error": "",
        }

    except ValidationError as error:
        error_message = "; ".join(
            item["msg"] for item in error.errors()
        )

        print(f"Planner validation failed: {error_message}")

        return {
            "planner_proposal": {},
            "validation_error": error_message,
        }


def reviewer_node(state: AgentState) -> dict[str, Any]:
    """Review the Planner output and decide whether to approve it."""
    print("--- NODE: Reviewer ---")

    client: ModelClient = state["llm"]

    reviewer_prompt = {
        "title": state["title"],
        "content": state["content"],
        "planner_proposal": state.get(
            "planner_proposal",
            {},
        ),
        "requirements": {
            "exactly_three_tags": True,
            "summary_at_most_25_words": True,
            "tags_must_be_related_to_input": True,
        },
    }

    messages = [
        {
            "role": "system",
            "content": (
                "You are the Reviewer. Review the Planner proposal. "
                "Return only JSON with this shape: "
                '{"approved": true, "issues": []}. '
                "Set approved to false and list issues when "
                "the proposal does not satisfy the requirements."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(reviewer_prompt),
        },
    ]

    started = time.perf_counter()
    response = client.complete(messages)
    latency_ms = (time.perf_counter() - started) * 1000

    raw_output = extract_json_object(response.get("content", ""))
    approved = bool(raw_output.get("approved", False))
    issues = raw_output.get("issues", [])

    if not isinstance(issues, list):
        issues = [str(issues)]

    issues = [
        clean_model_text(issue)
        for issue in issues
        if clean_model_text(issue)
    ]

    proposal = state.get("planner_proposal", {})

    try:
        PlannerOutput.model_validate(proposal)
    except ValidationError as error:
        approved = False
        issues.append(
            "Planner output failed schema validation."
        )

        if not issues:
            issues.append(str(error))

    feedback = {
        "approved": approved and not issues,
        "issues": issues,
        "latency_ms": round(latency_ms, 2),
    }

    print(json.dumps(feedback, indent=2))

    return {
        "reviewer_feedback": feedback,
        "final_output": proposal if feedback["approved"] else {},
    }


def supervisor_node(state: AgentState) -> dict[str, Any]:
    """Increment the turn counter before routing to the next node."""
    next_turn = state.get("turn_count", 0) + 1

    print(
        f"--- NODE: Supervisor "
        f"(turn {next_turn}/{state['max_turns']}) ---"
    )

    return {"turn_count": next_turn}


def router_logic(state: AgentState) -> str:
    """Choose Planner, Reviewer, or END."""
    if state["turn_count"] >= state["max_turns"]:
        return "finish"

    if state.get("validation_error"):
        return "planner"

    if not state.get("planner_proposal"):
        return "planner"

    if not state.get("reviewer_feedback"):
        return "reviewer"

    if state["reviewer_feedback"].get("approved", False):
        return "finish"

    return "planner"


def build_graph():
    """Assemble and compile the stateful LangGraph workflow."""
    graph = StateGraph(AgentState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("planner", planner_node)
    graph.add_node("reviewer", reviewer_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        router_logic,
        {
            "planner": "planner",
            "reviewer": "reviewer",
            "finish": END,
        },
    )

    graph.add_edge("planner", "supervisor")
    graph.add_edge("reviewer", "supervisor")

    return graph.compile()


def run_graph(
    title: str,
    content: str,
    email: str,
    model: str,
    temperature: float,
    max_turns: int,
    strict: bool,
) -> dict[str, Any]:
    """Run one graph execution and return its final state."""
    client = ModelClient(
        model=model,
        temperature=temperature,
    )

    initial_state: AgentState = {
        "title": title,
        "content": content,
        "email": email,
        "strict": strict,
        "task": (
            "Create exactly three topical tags and a concise "
            "summary for the supplied vulnerability report."
        ),
        "llm": client,
        "planner_proposal": {},
        "reviewer_feedback": {},
        "validation_error": "",
        "turn_count": 0,
        "max_turns": max_turns,
        "final_output": {},
    }

    compiled_graph = build_graph()
    final_state: AgentState = initial_state

    for update in compiled_graph.stream(initial_state):
        node_name = next(iter(update))
        final_state = {
            **final_state,
            **update[node_name],
        }

    result = {
        "title": title,
        "email": email,
        "model": model,
        "temperature": temperature,
        "max_turns": max_turns,
        "turn_count": final_state.get("turn_count", 0),
        "completed": bool(final_state.get("final_output")),
        "final_output": final_state.get("final_output", {}),
        "reviewer_feedback": final_state.get(
            "reviewer_feedback",
            {},
        ),
        "validation_error": final_state.get(
            "validation_error",
            "",
        ),
        "token_stats": client.stats([]),
    }

    return result


def main() -> None:
    """Run one graph execution from the command line."""
    parser = argparse.ArgumentParser()

    parser.add_argument("--title", required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--model", default="qwen3:8b")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-turns", type=int, default=10)
    parser.add_argument("--strict", action="store_true")

    args = parser.parse_args()

    result = run_graph(
        title=args.title,
        content=args.content,
        email=args.email,
        model=args.model,
        temperature=args.temperature,
        max_turns=args.max_turns,
        strict=args.strict,
    )

    print("\n--- GRAPH RESULT ---")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()