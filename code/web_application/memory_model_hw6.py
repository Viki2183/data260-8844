"""Ollama adapter helpers for DATA 260 Homework 6 memory operations."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable


DEFAULT_MODEL_NAME = "qwen3:8b"
DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_NUM_PREDICT = 256
MIN_NUM_PREDICT = 64
MAX_NUM_PREDICT = 512
MAX_EXTRACTED_FACTS = 3


def _get_hw6_num_predict() -> int:
    """Return a safe HW6 response limit without changing other callers."""

    try:
        configured = int(os.getenv("HW6_NUM_PREDICT", str(DEFAULT_NUM_PREDICT)))
    except (TypeError, ValueError):
        configured = DEFAULT_NUM_PREDICT
    return max(MIN_NUM_PREDICT, min(MAX_NUM_PREDICT, configured))


@dataclass
class ModelResult:
    """Structured output from one model call, including measured usage."""

    text: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    latency_ms: float
    model: str
    error: str | None = None

    @property
    def content(self) -> str:
        """Expose the same response text under the common ``content`` name."""

        return self.text

    def as_dict(self) -> dict[str, Any]:
        """Return a plain dictionary useful for logs and API responses."""

        return asdict(self) | {"content": self.text}


@dataclass
class FactExtractionResult:
    """Facts extracted from only the user message and their model metadata."""

    facts: list[dict[str, float | str]]
    usage: ModelResult
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a serializable fact-extraction result."""

        return {
            "facts": self.facts,
            "usage": self.usage.as_dict(),
            "error": self.error,
        }


class MemoryModelAdapter:
    """Connect memory operations to Ollama while remaining easy to fake-test.

    The existing ``src.model_client.ModelClient`` is used for real calls.  A
    caller can inject a compatible client or factory so unit tests never need
    a live Ollama server.
    """

    def __init__(
        self,
        model_client: Any | None = None,
        client_factory: Callable[..., Any] | None = None,
        model_name: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model_name = model_name or os.getenv(
            "HW6_MODEL_NAME",
            DEFAULT_MODEL_NAME,
        )
        self.base_url = base_url or os.getenv(
            "HW6_OLLAMA_BASE_URL",
            DEFAULT_OLLAMA_BASE_URL,
        )
        self._injected_client = model_client
        self._client_factory = client_factory
        self._clients: dict[bool, Any] = {}

    def _get_client(self, json_mode: bool) -> Any:
        """Return a cached client, creating a real one only when needed."""

        if self._injected_client is not None:
            return self._injected_client

        if json_mode in self._clients:
            return self._clients[json_mode]

        factory = self._client_factory or self._default_client_factory
        client = factory(
            model=self.model_name,
            temperature=0.0,
            base_url=self.base_url,
            json_mode=json_mode,
        )
        self._clients[json_mode] = client
        return client

    @staticmethod
    def _default_client_factory(**kwargs: Any) -> Any:
        """Create the established model adapter only after a real call starts."""

        from src.model_client import ModelClient

        # HW6 uses explicit settings for the CPU-bound local qwen3 model.
        # Injected and custom test clients never come through this factory.
        return ModelClient(
            **kwargs,
            reasoning=False,
            timeout_s=240.0,
            num_predict=_get_hw6_num_predict(),
        )

    @staticmethod
    def _invoke_client(client: Any, messages: list[dict[str, str]]) -> Any:
        """Support the existing complete() contract and simple fake clients."""

        if hasattr(client, "complete"):
            return client.complete(messages)
        if callable(client):
            return client(messages)
        raise TypeError("model client must provide complete() or be callable")

    @staticmethod
    def _usage_value(usage: dict[str, Any], *names: str) -> int | None:
        """Read a token field without inventing exact usage when it is absent."""

        for name in names:
            value = usage.get(name)
            if value is not None:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return None
        return None

    def _normalize_response(
        self,
        response: Any,
        latency_ms: float,
    ) -> ModelResult:
        """Normalize strings, dictionaries, and LangChain-like objects."""

        content: Any = response
        usage: dict[str, Any] = {}

        if isinstance(response, dict):
            content = response.get("content", response.get("text", ""))
            raw_usage = response.get("usage", response.get("usage_metadata", {}))
            if isinstance(raw_usage, dict):
                usage = raw_usage
            metadata = response.get("response_metadata", {})
            if isinstance(metadata, dict):
                usage = {**metadata, **usage}
        elif not isinstance(response, str):
            content = getattr(response, "content", "")
            raw_usage = getattr(response, "usage_metadata", {})
            if not isinstance(raw_usage, dict):
                raw_usage = getattr(response, "usage", {})
            if isinstance(raw_usage, dict):
                usage = raw_usage
            metadata = getattr(response, "response_metadata", {})
            if isinstance(metadata, dict):
                usage = {**metadata, **usage}

        prompt_tokens = self._usage_value(
            usage,
            "prompt_tokens",
            "input_tokens",
            "prompt_eval_count",
        )
        completion_tokens = self._usage_value(
            usage,
            "completion_tokens",
            "output_tokens",
            "eval_count",
        )
        total_tokens = self._usage_value(usage, "total_tokens")
        if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

        return ModelResult(
            text=str(content or ""),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=max(0.0, latency_ms),
            model=self.model_name,
        )

    def _complete(
        self,
        prompt: str,
        json_mode: bool = False,
        system_prompt: str | None = None,
    ) -> ModelResult:
        """Invoke the injected or lazily created model and normalize timing."""

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        started = time.perf_counter()

        try:
            response = self._invoke_client(self._get_client(json_mode), messages)
        except Exception as exc:  # controlled boundary for API/service layers
            latency_ms = (time.perf_counter() - started) * 1000
            exception_name = type(exc).__name__
            if isinstance(exc, TimeoutError) or "timeout" in exception_name.lower():
                category = "timeout"
            elif isinstance(exc, ConnectionError):
                category = "connection_failure"
            else:
                category = "model_invocation_failure"
            return ModelResult(
                text="",
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
                latency_ms=max(0.0, latency_ms),
                model=self.model_name,
                error=f"{category}:{type(exc).__name__}",
            )

        latency_ms = (time.perf_counter() - started) * 1000
        return self._normalize_response(response, latency_ms)

    def generate_reply(self, prompt: str) -> ModelResult:
        """Generate a normal assistant reply through the existing adapter."""

        if not prompt.strip():
            raise ValueError("prompt must contain meaningful text")
        return self._complete(prompt, json_mode=False)

    def generate_session_summary(self, conversation_text: str) -> ModelResult:
        """Ask Ollama for concise bullet points describing one session."""

        instruction = (
            "Summarize the conversation in concise bullet points. "
            "Keep durable preferences, decisions, and unresolved items. "
            "Do not invent facts."
        )
        return self._complete(
            conversation_text,
            json_mode=False,
            system_prompt=instruction,
        )

    def generate_lifetime_summary(self, session_summaries_text: str) -> ModelResult:
        """Ask Ollama to condense session summaries into durable user memory."""

        instruction = (
            "Condense these session summaries into concise durable information "
            "about the user. Return concise bullet points and do not invent facts."
        )
        return self._complete(
            session_summaries_text,
            json_mode=False,
            system_prompt=instruction,
        )

    def extract_episode_facts(self, user_message: str) -> FactExtractionResult:
        """Extract at most three durable facts from only the user message."""

        instruction = (
            "Analyze only the user's message. Return JSON with a facts array. "
            "Each fact must contain fact and importance from 0.0 to 1.0. "
            "Return an empty facts array when no durable fact is present. "
            "Do not include embeddings or assistant information."
        )
        result = self._complete(
            user_message,
            json_mode=True,
            system_prompt=instruction,
        )
        if result.error:
            return FactExtractionResult([], result, result.error)

        try:
            payload = self._parse_json(result.text)
            facts = self._clean_facts(payload)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            return FactExtractionResult(
                [],
                result,
                f"malformed_structured_output:{type(exc).__name__}",
            )

        return FactExtractionResult(facts, result)

    @staticmethod
    def _parse_json(text: str) -> Any:
        """Parse plain JSON or JSON enclosed in a markdown code fence."""

        cleaned = text.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
        if fenced:
            cleaned = fenced.group(1).strip()
        return json.loads(cleaned)

    @staticmethod
    def _clean_facts(payload: Any) -> list[dict[str, float | str]]:
        """Normalize model facts, clamp importance, and omit embeddings."""

        if isinstance(payload, dict):
            raw_facts = payload.get("facts", [])
            if isinstance(payload.get("fact"), str):
                raw_facts = [payload]
        elif isinstance(payload, list):
            raw_facts = payload
        else:
            raise ValueError("structured output must be a list or object")

        if not isinstance(raw_facts, list):
            raise ValueError("facts must be a list")

        cleaned: list[dict[str, float | str]] = []
        for item in raw_facts:
            if not isinstance(item, dict):
                continue
            fact = str(item.get("fact", "")).strip()
            if not fact:
                continue
            try:
                importance = float(item.get("importance", 0.5))
            except (TypeError, ValueError):
                importance = 0.5
            cleaned.append({
                "fact": fact[:500],
                "importance": max(0.0, min(1.0, importance)),
            })
            if len(cleaned) == MAX_EXTRACTED_FACTS:
                break
        return cleaned


__all__ = [
    "DEFAULT_MODEL_NAME",
    "DEFAULT_OLLAMA_BASE_URL",
    "FactExtractionResult",
    "MemoryModelAdapter",
    "ModelResult",
]
