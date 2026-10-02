import json
from typing import Any, Callable


Envelope = dict[str, Any]


def envelope(
    ok: bool,
    data: Any = None,
    error: str | None = None,
) -> Envelope:
    return {
        "ok": ok,
        "data": data,
        "error": error,
    }


def execute_tool(
    name: str,
    inputs: dict[str, Any],
    handlers: dict[str, Callable[..., str]] | None = None,
) -> str:
    """
    Safely dispatch one of the three domain tools.

    handlers is injectable so tests can run offline.
    """
    if handlers is None:
        from domain_server import aggregate, detail, search

        handlers = {
            "search": search,
            "detail": detail,
            "aggregate": aggregate,
        }

    if name not in handlers:
        return json.dumps(
            envelope(False, error=f"unknown tool: {name}")
        )

    if not isinstance(inputs, dict):
        return json.dumps(
            envelope(False, error="inputs must be an object")
        )

    try:
        raw_result = handlers[name](**inputs)

        if isinstance(raw_result, str):
            parsed = json.loads(raw_result)
        else:
            parsed = raw_result

        return json.dumps(parsed, default=str)

    except Exception as exc:
        return json.dumps(
            envelope(False, error=f"tool execution failed: {exc}")
        )