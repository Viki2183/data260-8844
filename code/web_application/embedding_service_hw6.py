"""Embedding helpers for DATA 260 Homework 6 episodic memory retrieval."""

from __future__ import annotations

import math
import os
from typing import Any


DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MAX_EPISODIC_TOP_K = 20
_embedding_model: Any | None = None


def get_embedding_model() -> Any:
    """Load and cache the SentenceTransformer model only when first needed.

    Importing this module does not load model weights.  The first real
    embedding request may load local weights or download them if unavailable.
    """

    global _embedding_model

    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        model_name = os.getenv(
            "HW6_EMBEDDING_MODEL",
            DEFAULT_EMBEDDING_MODEL,
        )
        _embedding_model = SentenceTransformer(model_name)

    return _embedding_model


def _as_float_list(vector: Any, field_name: str) -> list[float]:
    """Convert an embedding-like value into ordinary Python floats."""

    try:
        values = [float(value) for value in vector]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must contain numeric values") from exc

    if not values:
        raise ValueError(f"{field_name} must not be empty")

    return values


def embed_text(text: str) -> list[float]:
    """Turn text into a normalized vector for episodic-memory retrieval.

    Similar meanings tend to produce nearby vectors.  Normalization makes
    cosine similarity stable and lets vector direction carry the comparison.
    """

    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must contain meaningful content")

    model = get_embedding_model()
    encoded = model.encode(text, normalize_embeddings=True)
    return _as_float_list(encoded, "embedding")


def cosine_similarity(
    vector_a: list[float],
    vector_b: list[float],
) -> float:
    """Return cosine similarity, safely handling empty, mismatched, or zero vectors."""

    first = _as_float_list(vector_a, "vector_a")
    second = _as_float_list(vector_b, "vector_b")

    if len(first) != len(second):
        raise ValueError("vectors must have matching dimensions")

    dot_product = sum(left * right for left, right in zip(first, second))
    first_norm = math.sqrt(sum(value * value for value in first))
    second_norm = math.sqrt(sum(value * value for value in second))
    denominator = first_norm * second_norm

    if denominator == 0.0:
        return 0.0

    similarity = dot_product / denominator
    return max(-1.0, min(1.0, float(similarity)))


def rank_episodes_by_similarity(
    query_embedding: list[float],
    episodes: list[dict],
    top_k: int = 3,
) -> list[dict]:
    """Return copies of the most similar episodic facts.

    Each returned copy receives a temporary ``similarity`` field.  The source
    dictionaries are left untouched so repository results remain reusable.
    """

    if top_k < 1 or top_k > MAX_EPISODIC_TOP_K:
        raise ValueError(
            f"top_k must be between 1 and {MAX_EPISODIC_TOP_K}"
        )

    ranked: list[dict] = []
    for episode in episodes:
        if "embedding" not in episode:
            raise ValueError("each episode must contain an embedding")

        episode_copy = dict(episode)
        episode_copy["similarity"] = cosine_similarity(
            query_embedding,
            episode["embedding"],
        )
        ranked.append(episode_copy)

    ranked.sort(key=lambda episode: episode["similarity"], reverse=True)
    return ranked[:top_k]


__all__ = [
    "DEFAULT_EMBEDDING_MODEL",
    "MAX_EPISODIC_TOP_K",
    "cosine_similarity",
    "embed_text",
    "get_embedding_model",
    "rank_episodes_by_similarity",
]
