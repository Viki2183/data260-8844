"""Authenticated warm 10-query endpoint experiment; cold warm-up is excluded."""

from __future__ import annotations

import json
import statistics
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "code" / "web_application"))

from hw09.redis_client import get_redis_client, make_key
from web_application.auth_hw7 import create_access_token

URL = "http://127.0.0.1:8745/api/agent/ask"


def ask(token: str, question: str, correlation_id: str) -> dict:
    request = urllib.request.Request(
        URL,
        data=json.dumps({"question": question, "correlation_id": correlation_id}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def clear_entries() -> None:
    client = get_redis_client()
    keys = list(client.scan_iter(match=make_key("semantic_cache:entry") + ":*"))
    if keys:
        client.delete(*keys)


def main() -> None:
    token = create_access_token("vikki1", "reader")
    clear_entries()
    warm = ask(token, "Warm-up request about package alpha", "warmup-excluded-8844")
    clear_entries()
    questions = [
        "Which versions of package alpha are affected?",
        "Which versions of package alpha are affected?",
        "What releases of package alpha are vulnerable?",
        "What is the severity of CVE-2026-0003?",
        "What is the severity of CVE-2026-0003?",
        "How severe is CVE-2026-0003?",
        "What mitigation is recommended for package zeta?",
        "What mitigation is recommended for package zeta?",
        "Which ecosystem contains package delta?",
        "Which ecosystem contains package delta?",
    ]
    rows = []
    for index, question in enumerate(questions, 1):
        response = ask(token, question, f"warm-cache-{index:02d}-8844")
        required = {"answer", "is_cached", "similarity", "latency_ms", "cache_status",
                    "correlation_id", "timings_ms"}
        if not required.issubset(response):
            raise RuntimeError(f"response {index} omitted {sorted(required - set(response))}")
        rows.append({"query_number": index, "question": question, **response})
    cached = [row["latency_ms"] for row in rows if row["is_cached"]]
    uncached = [row["latency_ms"] for row in rows if not row["is_cached"]]
    result = {
        "student": "Vrishin KunnathamParambath", "sid4": "8844",
        "warm_up": {"procedure": "one authenticated endpoint request after Ollama qwen3:8b warm-up; excluded from statistics",
                    "excluded_latency_ms": warm["latency_ms"]},
        "total_queries": len(rows), "cached_queries": len(cached),
        "non_cached_queries": len(uncached), "hit_rate": len(cached) / len(rows),
        "average_cached_latency_ms": statistics.mean(cached) if cached else None,
        "average_non_cached_latency_ms": statistics.mean(uncached) if uncached else None,
        "responses": rows,
    }
    target = ROOT / "reports/hw09/raw/warm_cache_10_query_final.json"
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Vrishin KunnathamParambath\nSID4: 8844")
    print(json.dumps({key: value for key, value in result.items() if key != "responses"}, indent=2))
    for row in rows:
        print(f"Q{row['query_number']:02d} {row['cache_status']} is_cached={row['is_cached']} similarity={row['similarity']} latency_ms={row['latency_ms']}")


if __name__ == "__main__":
    main()
