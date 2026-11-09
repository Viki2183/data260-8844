"""Live Redis Stack vector-index verification without model loading."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from hw09.redis_client import get_redis_client
from hw09.semantic_cache import SemanticCache


def main() -> None:
    client = get_redis_client()
    cache = SemanticCache(client, threshold=0.85)
    first = [0.0] * 384
    first[0] = 1.0
    second = [0.0] * 384
    second[1] = 1.0
    entries = [
        cache.store("alpha affected versions", first, "alpha answer", None, None),
        cache.store("unrelated weather", second, "weather answer", None, None),
    ]
    try:
        hit, hit_similarity = cache.lookup("alpha releases", first, None, None)
        miss, miss_similarity = cache.lookup("orthogonal", [0.0] * 383 + [1.0], None, None)
        info = client.execute_command("FT.INFO", cache._index_key())
        result = {
            "student": "Vrishin KunnathamParambath", "sid4": "8844",
            "redis_image": os.getenv("HW9_REDIS_IMAGE", "redis/redis-stack-server:7.4.0-v8"),
            "index": cache._index_key(), "index_exists": bool(info),
            "inserted_entries": len(entries), "knn_hit_answer": hit["answer"] if hit else None,
            "knn_hit_similarity": hit_similarity, "threshold_filter_rejected": miss is None,
            "rejected_similarity": miss_similarity,
        }
        target = ROOT / "reports/hw09/raw/vector_index_live_final.json"
        target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
    finally:
        for entry in entries:
            client.delete(cache._entry_key(entry["entry_id"]))


if __name__ == "__main__":
    main()
