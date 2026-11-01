"""Live HW8 API demo: one CREATE/GET flow plus required error cases.

This script makes one request per case and never retries or resends a request.
It is intentionally separate from the historical application demo scripts.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


VALID_REPORT = {
    "packageName": "requests",
    "vulnerabilityId": "CVE-2026-0001",
    "submitterEmail": "student@example.com",
    "vulnerabilityDescription": "A sufficiently detailed vulnerability description.",
    "severity": "High",
    "affectedVersionsCount": 2,
    "termsAccepted": True,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DATA260 HW8 live API demo")
    parser.add_argument("--base-url", default="http://127.0.0.1:8744")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--run-label", default="demo")
    return parser.parse_args(argv)


def one_request(
    method: str,
    url: str,
    *,
    correlation_id: str,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request = Request(
        url,
        method=method,
        headers={"X-Correlation-ID": correlation_id, "Content-Type": "application/json"},
        data=json.dumps(json_body).encode("utf-8") if json_body is not None else None,
    )
    with urlopen(request, timeout=45) as response:
        body = json.loads(response.read().decode("utf-8"))
    return {
        "method": method,
        "url": url,
        "correlation_id": correlation_id,
        "status_code": response.status,
        "body": body,
    }


def run_demo(args: argparse.Namespace) -> list[dict[str, Any]]:
    base = args.base_url.rstrip("/")
    prefix = f"hw8-8844-{args.run_label}"
    events = [
        {"event": "demo_started", "base_url": base, "automatic_retries": 0},
        one_request(
            "POST",
            f"{base}/hw8/entity",
            correlation_id=f"{prefix}-create-001",
            json_body=VALID_REPORT,
        ),
    ]
    create_response = events[-1]["body"]["response"]
    entity_id = create_response.get("entity_id")
    events.append(
        one_request(
            "GET",
            f"{base}/hw8/entity/{entity_id}",
            correlation_id=f"{prefix}-get-001",
        )
    )
    events.append(
        one_request(
            "POST",
            f"{base}/hw8/entity",
            correlation_id=f"{prefix}-validation-error-001",
            json_body={"packageName": "requests"},
        )
    )
    events.append(
        one_request(
            "GET",
            f"{base}/hw8/entity/missing-8844",
            correlation_id=f"{prefix}-missing-001",
        )
    )
    events.append(
        one_request(
            "POST",
            f"{base}/hw8/entity/raw",
            correlation_id=f"{prefix}-unknown-operation-001",
            json_body={"operation": "UNKNOWN_OPERATION", "data": {}},
        )
    )
    return events


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    events = run_demo(args)
    for event in events:
        print(json.dumps(event, sort_keys=True), flush=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            "".join(json.dumps(event, sort_keys=True) + "\n" for event in events),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
