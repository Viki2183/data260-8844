"""Measure the fixed 40-case cache experiment when Redis and embeddings exist."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from .redis_client import get_redis_client
from .semantic_cache import SemanticCache
from .agent_system import load_reference, retrieve_facts


THRESHOLDS = (0.75, 0.80, 0.85, 0.90, 0.95)


def load_cases(path: Path) -> list[dict[str, Any]]:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def measure(path: Path, cache_miss_cost: float, false_hit_cost: float) -> list[dict[str, Any]]:
    cases = load_cases(path)
    results = []
    redis_client = get_redis_client()
    reference = load_reference()
    created_entry_ids: list[str] = []
    try:
        for threshold in THRESHOLDS:
            for entry_id in created_entry_ids:
                redis_client.delete(SemanticCache._entry_key(entry_id))
            created_entry_ids.clear()

            cache = SemanticCache(redis_client, threshold=threshold)
            for seed in cases:
                if seed.get("cached_query") == seed["query"]:
                    embedding = cache.embed(seed["cached_query"])
                    facts = retrieve_facts(seed["cached_query"], reference)
                    answer = facts[0]["fact"] if facts else "No matching vulnerability fact was found."
                    entry = cache.store(seed["cached_query"], embedding, answer, None, None)
                    created_entry_ids.append(str(entry["entry_id"]))
            hits = 0
            false_hits = 0
            false_hit_example = None
            latencies = []
            for case in cases:
                started = time.perf_counter()
                embedding = cache.embed(case["query"])
                candidate, similarity = cache.lookup(case["query"], embedding, None, None)
                is_hit = candidate is not None
                hits += int(is_hit)
                false_hits += int(
                    is_hit
                    and case["label"]
                    in {"superficially_similar_different_answer", "unrelated"}
                )
                if (
                    false_hit_example is None
                    and is_hit
                    and case["label"] == "superficially_similar_different_answer"
                    and candidate is not None
                ):
                    correct = retrieve_facts(case["query"], reference)
                    false_hit_example = {
                        "cached_query": candidate["question"],
                        "incoming_query": case["query"],
                        "similarity": similarity,
                        "cached_answer_returned": candidate["answer"],
                        "correct_answer": (
                            correct[0]["fact"] if correct else
                            "No matching vulnerability fact was found in the reference dataset."
                        ),
                        "confusion": "The questions share vulnerability-domain wording while differing in the package or CVE identifier that determines the answer.",
                    }
                latencies.append((time.perf_counter() - started) * 1000)
            misses = len(cases) - hits
            results.append({
                "threshold": threshold,
                "hit_rate": hits / len(cases),
                "false_hit_rate": false_hits / len(cases),
                "mean_latency_ms": sum(latencies) / len(latencies),
                "total_cost": misses * cache_miss_cost + false_hits * false_hit_cost,
                "hits": hits,
                "misses": misses,
                "false_hits": false_hits,
                "cache_miss_cost": cache_miss_cost,
                "false_hit_cost": false_hit_cost,
                "false_hit_example": false_hit_example,
            })
    finally:
        for entry_id in created_entry_ids:
            redis_client.delete(SemanticCache._entry_key(entry_id))
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("reports/hw09/cases/cache_cases.yaml"),
    )
    parser.add_argument("--cache-miss-cost", type=float, default=1.0)
    parser.add_argument("--false-hit-cost", type=float, default=5.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/hw09/raw/cache_thresholds.json"),
    )
    args = parser.parse_args()
    results = measure(args.cases, args.cache_miss_cost, args.false_hit_cost)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
