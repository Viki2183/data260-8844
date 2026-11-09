"""Redis Stack semantic cache backed by a RediSearch cosine-vector index."""

from __future__ import annotations

import json
import os
import struct
import uuid
from datetime import datetime, timezone
from typing import Any

try:
    from ..web_application.embedding_service_hw6 import cosine_similarity, embed_text
except ImportError:  # pragma: no cover
    from web_application.embedding_service_hw6 import cosine_similarity, embed_text

from .redis_client import make_key

EMBEDDING_DIMENSION = 384


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


class SemanticCache:
    def __init__(self, redis_client: Any, threshold: float | None = None):
        self.redis = redis_client
        self.threshold = float(
            os.getenv("HW9_SEMANTIC_THRESHOLD", "0.85")
            if threshold is None
            else threshold
        )
        if not getattr(self.redis, "hw9_test_double", False):
            self.ensure_vector_index()

    @staticmethod
    def _entry_key(entry_id: str) -> str:
        return make_key("semantic_cache:entry", entry_id)

    @staticmethod
    def _index_key() -> str:
        return make_key("semantic_cache:index")

    @staticmethod
    def _vector_bytes(embedding: list[float]) -> bytes:
        if len(embedding) != EMBEDDING_DIMENSION:
            raise ValueError(f"embedding must have {EMBEDDING_DIMENSION} dimensions")
        return struct.pack(f"<{EMBEDDING_DIMENSION}f", *embedding)

    def ensure_vector_index(self) -> None:
        """Create the namespaced HNSW cosine index once."""
        try:
            self.redis.execute_command("FT.INFO", self._index_key())
            return
        except Exception as exc:
            message = str(exc).lower()
            if "unknown index" not in message and "no such index" not in message:
                raise RuntimeError("Redis Search FT.INFO is unavailable") from exc
        self.redis.execute_command(
            "FT.CREATE", self._index_key(), "ON", "HASH", "PREFIX", 1,
            make_key("semantic_cache:entry") + ":", "SCHEMA",
            "question", "TEXT", "answer", "TEXT", "report_scope", "TAG",
            "data_version", "TAG", "embedding", "VECTOR", "HNSW", 6,
            "TYPE", "FLOAT32", "DIM", EMBEDDING_DIMENSION,
            "DISTANCE_METRIC", "COSINE",
        )

    def embed(self, question: str) -> list[float]:
        return embed_text(question)

    def _decode_hash(self, raw: dict[Any, Any]) -> dict[str, Any]:
        values = {
            _text(key): _text(value)
            for key, value in raw.items()
            if _text(key) != "embedding"
        }
        return {
            "entry_id": values["entry_id"],
            "question": values["question"],
            "answer": values["answer"],
            "report_id": (
                None if values["report_scope"] == "global" else int(values["report_scope"])
            ),
            "data_version": (
                None if values["data_version"] == "global" else values["data_version"]
            ),
            "metadata": json.loads(values.get("metadata", "{}")),
            "created_at": values["created_at"],
            "last_used_at": values["last_used_at"],
        }

    def _test_lookup(
        self,
        query_embedding: list[float],
        current_version: str | None,
        report_id: int | None,
    ) -> tuple[dict[str, Any] | None, float]:
        best, score = None, 0.0
        for entry in self.redis.hw9_entries.values():
            if entry["report_id"] != report_id or entry["data_version"] != current_version:
                continue
            candidate = cosine_similarity(query_embedding, entry["embedding"])
            if candidate > score:
                best, score = entry, candidate
        return (best if best is not None and score >= self.threshold else None), score

    def lookup(
        self,
        question: str,
        query_embedding: list[float],
        current_version: str | None,
        report_id: int | None,
    ) -> tuple[dict[str, Any] | None, float]:
        if getattr(self.redis, "hw9_test_double", False):
            return self._test_lookup(query_embedding, current_version, report_id)
        scope = "global" if report_id is None else str(report_id)
        version = "global" if current_version is None else str(current_version)
        result = self.redis.execute_command(
            "FT.SEARCH", self._index_key(),
            f"(@report_scope:{{{scope}}} @data_version:{{{version}}})=>[KNN 5 @embedding $vector AS vector_distance]",
            "PARAMS", 2, "vector", self._vector_bytes(query_embedding),
            "SORTBY", "vector_distance", "RETURN", 1, "vector_distance", "DIALECT", 2,
        )
        if int(result[0]) == 0:
            return None, 0.0
        key, fields = result[1], result[2]
        mapping = {
            _text(fields[index]): _text(fields[index + 1])
            for index in range(0, len(fields), 2)
        }
        similarity = max(-1.0, min(1.0, 1.0 - float(mapping["vector_distance"])))
        if similarity < self.threshold:
            return None, similarity
        entry = self._decode_hash(self.redis.hgetall(key))
        entry["last_used_at"] = utc_now()
        self.redis.hset(key, mapping={"last_used_at": entry["last_used_at"]})
        return entry, similarity

    def store(
        self,
        question: str,
        embedding: list[float],
        answer: str,
        report_id: int | None,
        data_version: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        entry = {
            "entry_id": uuid.uuid4().hex,
            "question": question,
            "embedding": [float(value) for value in embedding],
            "answer": answer,
            "report_id": report_id,
            "data_version": data_version,
            "metadata": dict(metadata or {}),
            "created_at": now,
            "last_used_at": now,
        }
        if getattr(self.redis, "hw9_test_double", False):
            self.redis.hw9_entries[entry["entry_id"]] = entry
            return entry
        self.redis.hset(self._entry_key(entry["entry_id"]), mapping={
            "entry_id": entry["entry_id"],
            "question": question,
            "answer": answer,
            "report_scope": "global" if report_id is None else str(report_id),
            "data_version": "global" if data_version is None else str(data_version),
            "metadata": json.dumps(entry["metadata"], sort_keys=True),
            "created_at": now,
            "last_used_at": now,
            "embedding": self._vector_bytes(entry["embedding"]),
        })
        return entry
