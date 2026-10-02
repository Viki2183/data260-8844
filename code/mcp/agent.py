import json
import sys
from pathlib import Path
from typing import Any

import httpx

from execute_tool import execute_tool


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = PROJECT_ROOT / "reports" / "hw05" / "raw" / "agent_runs.jsonl"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)


class MockModel:
    """Small offline model used for repeatable tests."""

    def __init__(self, responses):
        self.responses = responses
        self.index = 0

    def complete(self, prompt: str) -> dict[str, Any]:
        if self.index >= len(self.responses):
            return {"action": "final", "answer": "Mock model finished."}

        response = self.responses[self.index]
        self.index += 1
        return response


class OllamaModel:
    """Adapter for a local Ollama model."""

    def __init__(self, model_name="qwen3:8b"):
        self.model_name = model_name

    def complete(self, prompt: str) -> dict[str, Any]:
        system = """
Return only valid JSON in one of these forms:

{"action":"tool","name":"search","inputs":{"query":"...","limit":5}}
{"action":"tool","name":"detail","inputs":{"package_id":1}}
{"action":"tool","name":"aggregate","inputs":{"severity":"Medium"}}
{"action":"final","answer":"..."}

Available tools are search, detail, and aggregate.
"""

        response = httpx.post(
    "http://127.0.0.1:11434/api/chat",
    json={
    "model": self.model_name,
    "stream": False,
    "format": "json",
    "think": False,
    "keep_alive": "10m",
    "options": {
        "temperature": 0,
        "num_predict": 512,
    },
    "messages": [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ],
},
    timeout=180.0,
)
        response.raise_for_status()

        content = response.json()["message"]["content"]
        return json.loads(content)


def safety_check(name: str, inputs: dict[str, Any]) -> str | None:
    """Block queries that look like credential or secret searches."""
    if name == "search":
        query = str(inputs.get("query", "")).lower()
        blocked_words = {"password", "secret", "token", "credential"}

        if any(word in query for word in blocked_words):
            return "safety rule blocked credential-like search"

    return None


def safe_execute_tool(
    name: str,
    inputs: dict[str, Any],
    handlers=None,
) -> str:
    blocked_reason = safety_check(name, inputs)

    if blocked_reason:
        return json.dumps({
            "ok": False,
            "data": None,
            "error": blocked_reason,
        })

    return execute_tool(name, inputs, handlers)


def append_log(record: dict[str, Any]) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, default=str) + "\n")


def run_agent(
    user_input: str,
    model,
    max_steps: int = 4,
    handlers=None,
) -> dict[str, Any]:
    """Run the bounded agent loop and log every step."""
    conversation = user_input
    trace = []

    for step in range(1, max_steps + 1):
        decision = model.complete(conversation)

        if decision.get("action") == "final":
            record = {
                "user_input": user_input,
                "step": step,
                "action": "final",
                "final_answer": decision.get("answer", ""),
                "stop_reason": "model_final",
                "trace": trace,
            }
            append_log(record)
            return record

        if decision.get("action") != "tool":
            record = {
                "user_input": user_input,
                "step": step,
                "action": "final",
                "final_answer": "Invalid model action.",
                "stop_reason": "invalid_model_action",
                "trace": trace,
            }
            append_log(record)
            return record

        tool_name = decision.get("name")
        inputs = decision.get("inputs", {})

        tool_result = safe_execute_tool(
            tool_name,
            inputs,
            handlers,
        )

        trace.append({
            "step": step,
            "tool": tool_name,
            "inputs": inputs,
            "result": json.loads(tool_result),
        })

        conversation = (
            f"Original request: {user_input}\n"
            f"Tool result: {tool_result}\n"
            "Decide whether to call another tool or return a final answer."
        )

    record = {
        "user_input": user_input,
        "step": max_steps,
        "action": "final",
        "final_answer": "The maximum step limit was reached.",
        "stop_reason": "max_steps",
        "trace": trace,
    }
    append_log(record)
    return record


def run_offline_tests():
    fixture_handlers = {
        "search": lambda query, limit=10: json.dumps({
            "ok": True,
            "data": [{"name": "fixture-package"}],
            "error": None,
        }),
        "detail": lambda package_id: json.dumps({
            "ok": True,
            "data": {"id": package_id},
            "error": None,
        }),
        "aggregate": lambda severity=None: json.dumps({
            "ok": True,
            "data": [{"severity": severity or "Medium", "count": 1}],
            "error": None,
        }),
    }

    allowed = safe_execute_tool(
        "search",
        {"query": "package"},
        fixture_handlers,
    )
    allowed_data = json.loads(allowed)

    blocked = safe_execute_tool(
        "search",
        {"query": "password"},
        fixture_handlers,
    )
    blocked_data = json.loads(blocked)

    assert allowed_data["ok"] is True
    print("PASS safety allowed call")

    assert blocked_data["ok"] is False
    assert "safety rule" in blocked_data["error"]
    print("PASS safety blocked call")

    normal_model = MockModel([
        {
            "action": "tool",
            "name": "search",
            "inputs": {"query": "package"},
        },
        {
            "action": "final",
            "answer": "The package search completed.",
        },
    ])

    normal_result = run_agent(
        "Find the package.",
        normal_model,
        max_steps=3,
        handlers=fixture_handlers,
    )

    assert normal_result["stop_reason"] == "model_final"
    print("PASS MockModel normal completion")

    looping_model = MockModel([
        {
            "action": "tool",
            "name": "search",
            "inputs": {"query": "package"},
        },
        {
            "action": "tool",
            "name": "search",
            "inputs": {"query": "package"},
        },
        {
            "action": "tool",
            "name": "search",
            "inputs": {"query": "package"},
        },
    ])

    limited_result = run_agent(
        "Keep searching.",
        looping_model,
        max_steps=2,
        handlers=fixture_handlers,
    )

    assert limited_result["stop_reason"] == "max_steps"
    print("PASS MockModel max_steps")

    print("SUMMARY: 4/4 agent tests passed")


if __name__ == "__main__":
    if "--tests" in sys.argv:
        run_offline_tests()
    else:
        print("Use --tests to run offline tests.")