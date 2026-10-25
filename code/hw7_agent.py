"""Bounded HW7 agent loop, repair path, and deterministic Reflexion support."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


class Model(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]: ...


Tool = Callable[..., Any]


@dataclass
class AgentResult:
    answer: str
    stop_reason: str
    trace: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: int = 0
    repair_count: int = 0
    latency_ms: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "stop_reason": self.stop_reason,
            "trace": self.trace,
            "tool_calls": self.tool_calls,
            "repair_count": self.repair_count,
            "latency_ms": round(self.latency_ms, 3),
        }


def _validate_decision(decision: Any, tools: dict[str, Tool]) -> tuple[str, str, dict[str, Any]]:
    if not isinstance(decision, dict):
        raise ValueError("model output must be an object")
    action = decision.get("action")
    if action == "final" and isinstance(decision.get("answer"), str):
        return "final", "", {}
    if action != "tool":
        raise ValueError("model must choose tool or final")
    name = decision.get("name")
    inputs = decision.get("inputs")
    if not isinstance(name, str) or name not in tools:
        raise ValueError(f"unknown tool: {name}")
    if not isinstance(inputs, dict):
        raise ValueError("tool inputs must be an object")
    return "tool", name, inputs


def run_agent(
    user_input: str,
    model: Model,
    tools: dict[str, Tool],
    max_steps: int = 8,
    max_repairs: int = 1,
    required_tool_sequence: list[str] | None = None,
) -> dict[str, Any]:
    """Execute bounded model/tool turns with one explicit repair per failure."""
    started = time.perf_counter()
    messages = [{"role": "user", "content": user_input}]
    trace: list[dict[str, Any]] = []
    repairs = 0
    calls = 0
    for step in range(1, max_steps + 1):
        decision = model.complete(messages)
        try:
            action, name, inputs = _validate_decision(decision, tools)
        except ValueError as exc:
            if repairs >= max_repairs:
                return AgentResult(
                    "The request could not be completed safely.",
                    "human_review",
                    trace,
                    calls,
                    repairs,
                    (time.perf_counter() - started) * 1000,
                ).as_dict()
            repairs += 1
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"Repair once. Problem: {exc}. Return a valid tool or final JSON object."
                    ),
                }
            )
            continue
        if action == "final":
            used_tools = [item.get("tool") for item in trace]
            required = required_tool_sequence or []
            sequence_incomplete = (
                used_tools[: len(required)] != required[: len(used_tools)]
                or len(used_tools) < len(required)
            )
            if sequence_incomplete:
                if repairs >= max_repairs:
                    return AgentResult(
                        "The request could not be completed safely.",
                        "human_review",
                        trace,
                        calls,
                        repairs,
                        (time.perf_counter() - started) * 1000,
                    ).as_dict()
                repairs += 1
                next_tool = (
                    required[len(used_tools)]
                    if len(used_tools) < len(required)
                    else "the required tool sequence"
                )
                repair_detail = ""
                if next_tool == "detail" and trace:
                    latest_observation = trace[-1].get("observation", {})
                    candidates = latest_observation.get("data") or latest_observation.get("rows")
                    if isinstance(candidates, list) and candidates:
                        first = candidates[0]
                        if isinstance(first, dict) and first.get("id") is not None:
                            repair_detail = (
                                f" Use detail with inputs {{\"package_id\": {first['id']}}}."
                            )
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"Repair once. The required tool sequence is incomplete; "
                            f"call {next_tool} before providing a final answer.{repair_detail}"
                        ),
                    }
                )
                continue
            return AgentResult(
                str(decision.get("answer", "")),
                "success",
                trace,
                calls,
                repairs,
                (time.perf_counter() - started) * 1000,
            ).as_dict()
        try:
            observation = tools[name](**inputs)
        except Exception as exc:  # tool failures become bounded observations
            observation = {"success": False, "error": type(exc).__name__}
        if isinstance(observation, str):
            try:
                observation = json.loads(observation)
            except json.JSONDecodeError:
                observation = {"success": False, "error": "invalid tool response"}
        calls += 1
        trace.append(
            {"step": step, "tool": name, "inputs": inputs, "observation": observation}
        )
        messages.append(
            {
                "role": "tool",
                "tool_call_id": f"hw7-tool-call-{calls}",
                "content": json.dumps(observation, default=str),
            }
        )
        messages.append(
            {"role": "user", "content": "Continue or provide the final answer as JSON."}
        )
    return AgentResult(
        "The tool-call budget was exhausted.",
        "budget_exhausted",
        trace,
        calls,
        repairs,
        (time.perf_counter() - started) * 1000,
    ).as_dict()


def verify_task(result: dict[str, Any], required_tools: set[str]) -> dict[str, Any]:
    used = {item.get("tool") for item in result.get("trace", [])}
    answer = result.get("answer", "")
    return {
        "success": result.get("stop_reason") == "success" and required_tools.issubset(used),
        "unsupported_claims": not bool(answer.strip()),
        "missing_tools": sorted(required_tools - used),
    }


def reflexion_run(
    user_input: str,
    model_factory: Callable[[str | None], Model],
    tools: dict[str, Tool],
    required_tools: set[str],
    max_retries: int = 2,
) -> dict[str, Any]:
    """Retry only after a deterministic verifier failure, with concise reflections."""
    reflections: list[dict[str, Any]] = []
    reflection: str | None = None
    for attempt in range(max_retries + 1):
        result = run_agent(user_input, model_factory(reflection), tools)
        check = verify_task(result, required_tools)
        if check["success"]:
            result.update(
                {"attempt": attempt + 1, "reflections": reflections, "verifier": check}
            )
            return result
        if attempt == max_retries:
            result.update(
                {
                    "stop_reason": "human_review",
                    "attempt": attempt + 1,
                    "reflections": reflections,
                    "verifier": check,
                }
            )
            return result
        missing = ", ".join(check["missing_tools"]) or "the answer was empty"
        reflection = (
            f"Failed because required tools were missing: {missing}. "
            "Use the missing tool chain before finalizing."
        )
        reflections.append(
            {
                "attempt": attempt + 1,
                "evidence": {"trace": result.get("trace", []), "verifier": check},
                "reflection": reflection,
            }
        )
    raise AssertionError("unreachable")
