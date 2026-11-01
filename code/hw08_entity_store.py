"""Worker-local entity dictionary and idempotency cache for HW8."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from hw08_messages import idempotency_key


class EntityStore:
    def __init__(self) -> None:
        self.entities: dict[str, dict[str, Any]] = {}
        self.responses: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    def get_cached_response(self, message: Mapping[str, Any]) -> dict[str, Any] | None:
        response = self.responses.get(idempotency_key(message))
        return deepcopy(response) if response is not None else None

    def cache_response(self, message: Mapping[str, Any], response: Mapping[str, Any]) -> None:
        self.responses[idempotency_key(message)] = deepcopy(dict(response))

    def create(self, entity_id: str, data: Mapping[str, Any]) -> dict[str, Any]:
        entity = {"entity_id": entity_id, **dict(data)}
        self.entities[entity_id] = deepcopy(entity)
        return deepcopy(entity)

    def get(self, entity_id: str) -> dict[str, Any] | None:
        entity = self.entities.get(entity_id)
        return deepcopy(entity) if entity is not None else None

