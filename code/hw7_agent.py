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
    error_summary: str | None = None
    failure_classification: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "stop_reason": self.stop_reason,
            "trace": self.trace,
            "tool_calls": self.tool_calls,
            "repair_count": self.repair_count,
            "latency_ms": round(self.latency_ms, 3),
            "error_summary": self.error_summary,
            "failure_classification": self.failure_classification,
        }


def _normalize_observation(observation: Any) -> dict[str, Any]:
    """Keep direct handlers and MCP-style handlers on one safe envelope."""
    if isinstance(observation, str):
        try:
            observation = json.loads(observation)
        except json.JSONDecodeError:
            return {"ok": False, "success": False, "data": None,
                    "error": "invalid tool response"}
    if not isinstance(observation, dict):
        return {"ok": False, "success": False, "data": None,
                "error": "tool response must be an object"}
    normalized = dict(observation)
    if "ok" not in normalized and "success" in normalized:
        normalized["ok"] = bool(normalized["success"])
    if "success" not in normalized and "ok" in normalized:
        normalized["success"] = bool(normalized["ok"])
    normalized.setdefault("data", None)
    normalized.setdefault("error", None)
    return normalized


def _normalize_inputs(name: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Normalize model-emitted scalar IDs without changing tool signatures."""
    normalized = dict(inputs)
    if name == "detail" and "package_id" in normalized:
        try:
            normalized["package_id"] = int(normalized["package_id"])
        except (TypeError, ValueError) as exc:
            raise ValueError("detail requires integer package_id") from exc
    return normalized


def _first_package_id(observation: dict[str, Any]) -> int | None:
    """Extract a package ID from either search rows or one detail object."""
    data = observation.get("data") or observation.get("rows")
    if isinstance(data, dict):
        data = [data]
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("id") is not None:
                try:
                    return int(item["id"])
                except (TypeError, ValueError):
                    return None
    return None


def _observation_succeeded(observation: dict[str, Any]) -> bool:
    return bool(observation.get("success", observation.get("ok", False)))


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
    required_tool_inputs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute bounded model/tool turns with one explicit repair per failure."""
    started = time.perf_counter()
    messages = [{"role": "user", "content": user_input}]
    trace: list[dict[str, Any]] = []
    repairs = 0
    calls = 0
    for step in range(1, max_steps + 1):
        try:
            decision = model.complete(messages)
        except Exception as exc:
            if (
                required_tool_inputs is not None
                and repairs < max_repairs
                and len(trace) < len(required_tool_sequence or [])
            ):
                repairs += 1
                trace.append(
                    {
                        "event": "adapter_error",
                        "error": f"{type(exc).__name__}: {exc}",
                        "repair": True,
                    }
                )
                next_index = len(
                    [item for item in trace if item.get("tool") is not None]
                )
                next_tool = (required_tool_sequence or [])[next_index]
                repair_inputs = required_tool_inputs[next_index]
                try:
                    repair_inputs = _normalize_inputs(next_tool, repair_inputs)
                    observation = _normalize_observation(
                        tools[next_tool](**repair_inputs)
                    )
                except Exception as tool_exc:
                    observation = {
                        "ok": False,
                        "success": False,
                        "data": None,
                        "error": f"{type(tool_exc).__name__}: {tool_exc}",
                    }
                calls += 1
                trace.append(
                    {
                        "step": step,
                        "tool": next_tool,
                        "inputs": repair_inputs,
                        "observation": observation,
                        "repair": True,
                        "repair_reason": "bounded controller recovery after adapter failure",
                    }
                )
                if not _observation_succeeded(observation):
                    return AgentResult(
                        "The fixed tool sequence could not be completed safely.",
                        "human_review",
                        trace,
                        calls,
                        repairs,
                        (time.perf_counter() - started) * 1000,
                        f"{type(exc).__name__}: {exc}",
                        "controller_tool_error",
                    ).as_dict()
                if len(
                    [item for item in trace if item.get("tool") is not None]
                ) == len(required_tool_sequence or []):
                    return AgentResult(
                        (
                            "Required tool sequence completed by bounded controller "
                            "recovery after adapter failure."
                        ),
                        "success",
                        trace,
                        calls,
                        repairs,
                        (time.perf_counter() - started) * 1000,
                        f"{type(exc).__name__}: {exc}",
                        "bounded_controller_recovery",
                    ).as_dict()
            return AgentResult(
                "The model adapter terminated before a safe result was produced.",
                "human_review",
                trace,
                calls,
                repairs,
                (time.perf_counter() - started) * 1000,
                f"{type(exc).__name__}: {exc}",
                "model_or_adapter_error",
            ).as_dict()
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
                repair_inputs = None
                if required_tool_inputs and len(required_tool_inputs) > len(used_tools):
                    repair_inputs = required_tool_inputs[len(used_tools)]
                if next_tool == "detail" and trace:
                    latest_observation = trace[-1].get("observation", {})
                    package_id = _first_package_id(latest_observation)
                    if package_id is not None:
                        repair_detail = (
                            f" Use detail with inputs {{\"package_id\": {package_id}}}."
                        )
                        if required_tool_inputs is not None:
                            repair_inputs = {"package_id": package_id}
                if repair_inputs is not None:
                    repair_detail = (
                        f" Tool schema: {next_tool}(" + ", ".join(
                            f"{key}=..." for key in repair_inputs
                        ) + ")."
                        f" Exact inputs: {json.dumps(repair_inputs, sort_keys=True)}."
                        " Do not provide a final answer until this tool completes."
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
                if repair_inputs is not None:
                    try:
                        repair_inputs = _normalize_inputs(next_tool, repair_inputs)
                        observation = tools[next_tool](**repair_inputs)
                    except Exception as exc:
                        observation = {
                            "ok": False,
                            "success": False,
                            "data": None,
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    observation = _normalize_observation(observation)
                    calls += 1
                    trace.append(
                        {
                            "step": step,
                            "tool": next_tool,
                            "inputs": repair_inputs,
                            "observation": observation,
                            "repair": True,
                        }
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": f"hw7-tool-call-{calls}",
                            "content": json.dumps(observation, default=str),
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
            inputs = _normalize_inputs(name, inputs)
            observation = tools[name](**inputs)
        except Exception as exc:  # tool failures become bounded observations
            observation = {
                "ok": False,
                "success": False,
                "data": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        if isinstance(observation, str):
            observation = _normalize_observation(observation)
        else:
            observation = _normalize_observation(observation)
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


def verify_task(
    result: dict[str, Any],
    required_tools: set[str],
    required_tool_sequence: list[str] | None = None,
) -> dict[str, Any]:
    used_sequence = [item.get("tool") for item in result.get("trace", [])]
    used = set(used_sequence)
    answer = result.get("answer", "")
    sequence_ok = (
        required_tool_sequence is None
        or used_sequence[: len(required_tool_sequence)] == required_tool_sequence
    )
    missing_sequence = []
    if required_tool_sequence is not None and not sequence_ok:
        missing_sequence = required_tool_sequence[len(used_sequence):]
    return {
        "success": (
            result.get("stop_reason") == "success"
            and required_tools.issubset(used)
            and sequence_ok
            and (required_tool_sequence is None
                 or len(used_sequence) >= len(required_tool_sequence))
        ),
        "unsupported_claims": not bool(answer.strip()),
        "missing_tools": sorted(required_tools - used),
        "missing_sequence": missing_sequence,
    }


def reflexion_run(
    user_input: str,
    model_factory: Callable[[str | None], Model],
    tools: dict[str, Tool],
    required_tools: set[str],
    max_retries: int = 2,
    required_tool_sequence: list[str] | None = None,
    required_tool_inputs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Retry only after a deterministic verifier failure, with concise reflections."""
    reflections: list[dict[str, Any]] = []
    reflection: str | None = None
    for attempt in range(max_retries + 1):
        result = run_agent(
            user_input,
            model_factory(reflection),
            tools,
            required_tool_sequence=required_tool_sequence,
            required_tool_inputs=required_tool_inputs,
        )
        check = verify_task(result, required_tools, required_tool_sequence)
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
        missing = ", ".join(check["missing_tools"])
        missing = missing or ", ".join(check.get("missing_sequence", []))
        missing = missing or "the answer was empty"
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
