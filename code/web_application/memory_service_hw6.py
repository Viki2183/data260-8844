"""Integrated memory lifecycle for DATA 260 Homework 6 chat operations."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

try:
    from . import embedding_service_hw6 as embedding_service
    from . import file_memory_hw6 as file_memory
    from . import memory_logic_hw6 as memory_logic
    from . import memory_repositories_hw6 as memory_repository
    from .memory_model_hw6 import MemoryModelAdapter
except ImportError:  # pragma: no cover - supports direct module imports
    import embedding_service_hw6 as embedding_service
    import file_memory_hw6 as file_memory
    import memory_logic_hw6 as memory_logic
    import memory_repositories_hw6 as memory_repository
    from memory_model_hw6 import MemoryModelAdapter


LIFETIME_SUMMARY_EVERY_SESSION_SUMMARIES = 3
MAX_SESSION_SUMMARIES_FOR_LIFETIME = 100
SYSTEM_PRIMER = (
    "You are a helpful assistant. Use the supplied memory carefully, "
    "do not invent facts, and answer the current user message directly."
)
COMMAND_HELP = (
    "Available HW6 memory commands:\n"
    "- /memory: display the current user-scoped memory snapshot.\n"
    "- /compact: summarize older messages and consolidate MEMORY.md when its policy requires it.\n"
    "- /dream: add verified non-sensitive durable facts to MEMORY.md after deduplication.\n"
    "- /help: show this command guide.\n"
    "MongoDB and file memory are compared rather than silently merged.\n"
    "Commands are bounded to one user and session, and never display credentials."
)


class MemoryService:
    """Coordinate message storage, retrieval, generation, and consolidation."""

    def __init__(
        self,
        repository: Any = memory_repository,
        model_adapter: Any | None = None,
        embed_text: Callable[[str], list[float]] = embedding_service.embed_text,
        rank_episodes: Callable[..., list[dict]] = embedding_service.rank_episodes_by_similarity,
        config: dict[str, int] | None = None,
        system_primer: str = SYSTEM_PRIMER,
        file_memory_path: str | Path | None = None,
    ) -> None:
        self.repository = repository
        self.model_adapter = model_adapter or MemoryModelAdapter()
        self.embed_text = embed_text
        self.rank_episodes = rank_episodes
        self.config = config or memory_logic.get_memory_config()
        self.system_primer = system_primer
        # The environment override makes tests and deployments explicit while
        # keeping the repository-root MEMORY.md as the safe default.
        self.file_memory_path = Path(file_memory_path or os.getenv(
            "HW6_FILE_MEMORY_PATH",
            str(Path(__file__).resolve().parents[2] / "MEMORY.md"),
        ))
        self.diagnostics: list[dict[str, str]] = []

    @staticmethod
    def ensure_session_id(session_id: str | None) -> str:
        """Keep a supplied session ID or generate a separate safe identifier."""

        if session_id is not None:
            if not isinstance(session_id, str) or not session_id.strip():
                raise ValueError("session_id must contain meaningful text")
            return session_id
        return f"hw6-{uuid4().hex}"

    @staticmethod
    def _require_text(value: str, field_name: str) -> str:
        """Validate required chat text before any repository operation."""

        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must contain meaningful text")
        return value

    def _diagnose(self, category: str, detail: str) -> None:
        """Keep safe diagnostic categories without storing stack traces."""

        self.diagnostics.append({"category": category, "detail": detail})

    @staticmethod
    def _model_value(result: Any, name: str, default: Any = None) -> Any:
        """Read fields from dataclass-like or dictionary model results."""

        if isinstance(result, dict):
            return result.get(name, default)
        return getattr(result, name, default)

    def _model_error(self, result: Any) -> str | None:
        """Return a controlled model error, if the adapter reported one."""

        error = self._model_value(result, "error")
        return str(error) if error else None

    @staticmethod
    def _without_current_message(
        messages: list[dict[str, Any]],
        current_message: str,
    ) -> list[dict[str, Any]]:
        """Remove a duplicated current user message from prompt history."""

        current = current_message.strip()
        return [
            message
            for message in messages
            if not (
                str(message.get("role", "")).lower() == "user"
                and str(message.get("content", "")).strip() == current
            )
        ]

    def _usage(
        self,
        model_result: Any,
        lifetime_summary: str | None,
        session_summary: str | None,
        short_term_messages: list[dict[str, Any]],
        current_message: str,
        episodic_facts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Combine exact adapter fields with explicitly estimated breakdowns."""

        prior_messages = self._without_current_message(
            short_term_messages,
            current_message,
        )
        breakdown = memory_logic.get_memory_usage_breakdown(
            self.system_primer,
            lifetime_summary,
            session_summary,
            prior_messages,
            current_message,
            episodic_facts,
        )
        return {
            "prompt_tokens": self._model_value(model_result, "prompt_tokens"),
            "completion_tokens": self._model_value(model_result, "completion_tokens"),
            "total_tokens": self._model_value(model_result, "total_tokens"),
            "system_primer_tokens": breakdown["system_primer_tokens"],
            "long_term_tokens": breakdown["long_term_tokens"],
            "short_term_tokens": breakdown["short_term_tokens"],
            "episodic_tokens": breakdown["episodic_tokens"],
            "latency_ms": max(0.0, float(self._model_value(model_result, "latency_ms", 0.0))),
            "component_tokens": {
                key: breakdown[key]
                for key in (
                    "primer",
                    "session_summary",
                    "lifetime_summary",
                    "short_term_window",
                    "episodic_facts",
                    "current_user_message",
                    "estimated_prompt_total",
                )
            },
            "prompt_token_total_estimate": breakdown["estimated_prompt_total"],
        }

    def _store_facts(
        self,
        user_id: str,
        session_id: str,
        facts_result: Any,
    ) -> list[dict[str, Any]]:
        """Embed and store only clean facts extracted from the user message."""

        facts = self._model_value(facts_result, "facts", []) or []
        stored: list[dict[str, Any]] = []
        for fact in facts[:3]:
            fact_text = str(fact.get("fact", "")).strip()
            if not fact_text:
                continue
            try:
                importance = max(0.0, min(1.0, float(fact.get("importance", 0.5))))
                vector = self.embed_text(fact_text)
                stored.append(
                    self.repository.save_episode(
                        user_id=user_id,
                        session_id=session_id,
                        fact=fact_text,
                        importance=importance,
                        embedding=vector,
                    )
                )
            except Exception as exc:  # optional memory must not erase a reply
                self._diagnose("episode_save_failure", type(exc).__name__)
        return stored

    def _memory_snapshot(
        self,
        user_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        """Load one user/session snapshot without invoking the model."""

        messages = self.repository.load_short_term_messages(
            user_id,
            session_id,
            limit=16,
        )
        session_summary = self.repository.get_latest_session_summary(
            user_id,
            session_id,
        )
        lifetime_summary = self.repository.get_latest_lifetime_summary(user_id)
        episodic_facts = self.repository.list_recent_episodes(user_id, limit=20)
        return {
            "user_id": user_id,
            "messages": messages,
            "latest_session_summary": session_summary,
            "latest_lifetime_summary": lifetime_summary,
            "episodic_facts": episodic_facts,
            "file_memory": self._file_memory_metadata(),
        }

    def _file_memory_metadata(self) -> dict[str, Any]:
        """Describe file memory without returning its potentially sensitive text."""

        if not self.file_memory_path.exists():
            return {
                "path": str(self.file_memory_path),
                "line_count": 0,
                "physical_line_count": 0,
                "non_comment_line_count": 0,
                "fact_count": 0,
                "age_hours": 0.0,
                "requires_consolidation": False,
            }
        content = file_memory.read_memory_file(self.file_memory_path)
        modified_at = datetime.fromtimestamp(
            self.file_memory_path.stat().st_mtime,
            tz=timezone.utc,
        )
        now = datetime.now(timezone.utc)
        physical_lines = len(content.splitlines())
        non_comment_lines = sum(
            1 for line in content.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
        return {
            "path": str(self.file_memory_path),
            "line_count": file_memory.count_memory_lines(content),
            "physical_line_count": physical_lines,
            "non_comment_line_count": non_comment_lines,
            "fact_count": len(file_memory.extract_memory_facts(content)),
            "age_hours": max(0.0, (now - modified_at).total_seconds() / 3600),
            "requires_consolidation": file_memory.memory_file_requires_consolidation(
                content,
                modified_at,
                now,
            ),
        }

    def _compact_counts(self, user_id: str, session_id: str) -> dict[str, Any]:
        """Capture read-only counts without guessing from a bounded window.

        The production repository exposes MongoDB collection handles, while
        offline fakes can provide equivalent count methods.  If neither is
        available, the field is explicitly unavailable rather than inferred.
        """

        counts: dict[str, Any] = {
            "messages": None,
            "summaries": None,
            "episodes": None,
            "unavailable": {},
        }
        queries = {
            "messages": {"user_id": user_id, "session_id": session_id},
            "summaries": {
                "user_id": user_id,
                "session_id": session_id,
                "scope": "session",
            },
            "episodes": {"user_id": user_id, "session_id": session_id},
        }
        collection_getters = {
            "messages": "get_messages_collection",
            "summaries": "get_summaries_collection",
            "episodes": "get_episodes_collection",
        }
        method_names = {
            "messages": ("count_messages", "count_all_messages"),
            "summaries": ("count_summaries",),
            "episodes": ("count_episodes",),
        }
        for name, query in queries.items():
            try:
                for method_name in method_names[name]:
                    method = getattr(self.repository, method_name, None)
                    if callable(method):
                        counts[name] = int(method(user_id, session_id))
                        break
                if counts[name] is None:
                    getter = getattr(self.repository, collection_getters[name], None)
                    collection = getter() if callable(getter) else None
                    if collection is not None and hasattr(collection, "count_documents"):
                        counts[name] = int(collection.count_documents(query))
                if counts[name] is None:
                    counts["unavailable"][name] = (
                        "repository exposes no bounded read-only count method"
                    )
            except Exception as exc:
                counts["unavailable"][name] = (
                    f"read-only count unavailable: {type(exc).__name__}"
                )
        if not counts["unavailable"]:
            counts.pop("unavailable")
        return counts

    def _compact_state(self, user_id: str, session_id: str) -> dict[str, Any]:
        """Combine database counts with non-sensitive file-memory metadata."""

        file_metadata = self._file_memory_metadata()
        return {
            **self._compact_counts(user_id, session_id),
            "file_memory_physical_lines": file_metadata.get("physical_line_count", 0),
            "file_memory_non_comment_lines": file_metadata.get("non_comment_line_count", 0),
            "file_memory_facts": file_metadata.get("fact_count", 0),
        }

    def _backup_file_memory(self, original: str) -> str:
        """Preserve the pre-write file beside it before any command changes it."""

        backup_path = self.file_memory_path.with_name(
            self.file_memory_path.name + ".before-hw6"
        )
        if not backup_path.exists():
            file_memory.write_memory_file(backup_path, original)
        return str(backup_path)

    @staticmethod
    def _safe_durable_fact(fact: Any) -> str | None:
        """Reject secrets and connection material before file-memory writes."""

        text = str(fact).strip()
        lowered = text.lower()
        sensitive_markers = (
            "password", "api key", "apikey", "token", "connection string",
            "mongodb://", "mysql://", "secret", "authorization:",
        )
        if not text or any(marker in lowered for marker in sensitive_markers):
            return None
        return text[:500]

    def _consolidate_file_memory(self, now: datetime | None = None) -> dict[str, Any]:
        """Apply file policy separately while MongoDB raw messages remain intact."""

        current = now or datetime.now(timezone.utc)
        original = file_memory.read_memory_file(self.file_memory_path) if self.file_memory_path.exists() else ""
        modified_at = (
            datetime.fromtimestamp(self.file_memory_path.stat().st_mtime, tz=timezone.utc)
            if self.file_memory_path.exists()
            else current
        )
        result = file_memory.consolidate_memory(
            original,
            now=current,
            modified_at=modified_at,
        )
        if result["triggered"] and original:
            # The backup makes the rewrite recoverable; MongoDB messages are
            # never deleted because file compression is only a prompt policy.
            backup_path = self._backup_file_memory(original)
            file_memory.write_memory_file(self.file_memory_path, result["consolidated_text"])
            result["file_path"] = str(self.file_memory_path)
            result["backup_path"] = backup_path
            result["written"] = True
        else:
            result["file_path"] = str(self.file_memory_path)
            result["written"] = False
        return result

    def _add_facts_to_file_memory(self, facts: list[Any]) -> dict[str, Any]:
        """Write only verified, non-sensitive facts and preserve the prior file."""

        original = file_memory.read_memory_file(self.file_memory_path) if self.file_memory_path.exists() else ""
        existing = file_memory.extract_memory_facts(original)
        safe_facts = [fact for fact in (self._safe_durable_fact(item.get("fact", "")) for item in facts) if fact]
        unique_existing, _ = file_memory.remove_duplicate_facts(existing)
        existing_keys = {fact.lower().strip() for fact in unique_existing}
        new_facts: list[str] = []
        for fact in safe_facts:
            if fact.lower().strip() not in existing_keys and fact not in new_facts:
                new_facts.append(fact)
        combined = [*unique_existing, *safe_facts]
        unique_combined, duplicate_count = file_memory.remove_duplicate_facts(combined)
        conflicts = file_memory.detect_contradictions(unique_combined)
        if safe_facts:
            backup_path = self._backup_file_memory(original) if original else None
            consolidated = file_memory.consolidate_memory(
                "# File memory\n" + "\n".join(f"- {fact}" for fact in unique_combined),
                now=datetime.now(timezone.utc),
            )
            file_memory.write_memory_file(self.file_memory_path, consolidated["consolidated_text"])
        else:
            backup_path = None
        return {
            "facts_added": new_facts,
            "facts_skipped_as_duplicates": max(0, len(combined) - len(unique_combined)),
            "contradictions_detected": conflicts,
            "line_count": self._file_memory_metadata()["line_count"],
            "file_path": str(self.file_memory_path),
            "backup_path": backup_path,
            "written": bool(safe_facts),
        }

    def _command_memory_used(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Adapt a snapshot to the memory metadata used by ChatResponse."""

        session_summary = snapshot.get("latest_session_summary") or {}
        lifetime_summary = snapshot.get("latest_lifetime_summary") or {}
        return {
            "short_term_count": len(snapshot.get("messages", [])),
            "short_term_messages": snapshot.get("messages", []),
            "session_summary": session_summary.get("text"),
            "lifetime_summary": lifetime_summary.get("text"),
            "episodic_facts": snapshot.get("episodic_facts", []),
            "file_memory": snapshot.get("file_memory"),
        }

    def _command_response(
        self,
        command: str,
        user_id: str,
        session_id: str,
        answer: str,
        snapshot: dict[str, Any],
        command_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a schema-compatible command response without saving a chat turn."""

        # Commands are control operations, not assistant turns.  Avoiding a
        # synthetic assistant message keeps chat counts and raw evidence honest.
        return {
            "answer": answer,
            "user_id": user_id,
            "session_id": session_id,
            "memory_used": self._command_memory_used(snapshot),
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "system_primer_tokens": 0,
                "long_term_tokens": 0,
                "short_term_tokens": 0,
                "episodic_tokens": 0,
                "latency_ms": 0.0,
            },
            "component_tokens": {
                "primer": 0,
                "session_summary": 0,
                "lifetime_summary": 0,
                "short_term_window": 0,
                "episodic_facts": 0,
                "current_user_message": 0,
                "estimated_prompt_total": 0,
            },
            "prompt_token_total_estimate": 0,
            "command": command,
            "command_result": command_result,
            "diagnostics": list(self.diagnostics),
        }

    def _command_help(
        self,
        user_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        """Explain commands locally, without MongoDB or Ollama."""

        return self._command_response(
            "/help",
            user_id,
            session_id,
            COMMAND_HELP,
            {"user_id": user_id, "messages": [], "episodic_facts": []},
            {"help": COMMAND_HELP},
        )

    def _command_memory(
        self,
        user_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        """Return the bounded memory snapshot without generating a reply."""

        snapshot = self._memory_snapshot(user_id, session_id)
        return self._command_response(
            "/memory",
            user_id,
            session_id,
            "Here is the current memory snapshot for this user and session.",
            snapshot,
            {"snapshot": snapshot},
        )

    def _load_compaction_text(
        self,
        user_id: str,
        session_id: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Load a bounded conversation and separate older messages from the window."""

        messages = self.repository.load_short_term_messages(
            user_id,
            session_id,
            limit=100,
        )
        short_term_n = self.config["short_term_n"]
        return messages, messages[:-short_term_n] if len(messages) > short_term_n else []

    def _command_compact(
        self,
        user_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        """Consolidate older messages while retaining every raw message."""

        before = self._compact_state(user_id, session_id)
        snapshot = self._memory_snapshot(user_id, session_id)
        file_result = self._consolidate_file_memory()
        snapshot["file_memory"] = self._file_memory_metadata()
        _, older_messages = self._load_compaction_text(user_id, session_id)
        if not older_messages:
            after = self._compact_state(user_id, session_id)
            return self._command_response(
                "/compact",
                user_id,
                session_id,
                "There are no messages outside the current short-term window to compact.",
                snapshot,
                {
                    "compacted_message_count": 0,
                    "facts_saved": 0,
                    "summary": None,
                    "file_consolidation": file_result,
                    "raw_messages_preserved": True,
                    "before": before,
                    "after": after,
                    "facts_added": 0,
                    "summary_created": False,
                    "lifetime_summary_created": False,
                },
            )

        conversation_text = memory_logic.format_messages_for_prompt(older_messages)
        summary_result = self.model_adapter.generate_session_summary(conversation_text)
        if self._model_error(summary_result):
            self._diagnose("compact_summary_failure", self._model_error(summary_result) or "unknown")
            after = self._compact_state(user_id, session_id)
            return self._command_response(
                "/compact",
                user_id,
                session_id,
                "Compaction could not create a summary.",
                snapshot,
                {
                    "compacted_message_count": len(older_messages),
                    "facts_saved": 0,
                    "summary": None,
                    "file_consolidation": file_result,
                    "raw_messages_preserved": True,
                    "before": before,
                    "after": after,
                    "facts_added": 0,
                    "summary_created": False,
                    "lifetime_summary_created": False,
                },
            )

        summary_text = str(self._model_value(summary_result, "text", "")).strip()
        saved_summary = None
        if summary_text:
            # Raw messages are preserved; this adds a compressed view rather
            # than replacing evidence that may be needed for HW6 verification.
            saved_summary = self.repository.save_summary(
                user_id=user_id,
                session_id=session_id,
                scope="session",
                text=summary_text,
            )

        generated_lifetime_summary = None
        if saved_summary is not None:
            # /compact creates the same kind of session summary as normal chat.
            # Reusing the shared check keeps lifetime memory consistent no
            # matter which supported path created the session summary.
            generated_lifetime_summary = self._maybe_save_lifetime_summary(user_id)

        facts_result = self.model_adapter.extract_episode_facts(conversation_text)
        saved_facts = self._store_facts(user_id, session_id, facts_result)
        after = self._compact_state(user_id, session_id)
        return self._command_response(
            "/compact",
            user_id,
            session_id,
            "Older messages were compacted into a session summary and durable facts; raw messages were preserved.",
            snapshot,
            {
                "compacted_message_count": len(older_messages),
                "facts_saved": len(saved_facts),
                "summary": saved_summary,
                "lifetime_summary": generated_lifetime_summary,
                "file_consolidation": file_result,
                "raw_messages_preserved": True,
                "before": before,
                "after": after,
                "facts_added": len(saved_facts),
                "summary_created": saved_summary is not None,
                "lifetime_summary_created": generated_lifetime_summary is not None,
            },
        )

    def _command_dream(
        self,
        user_id: str,
        session_id: str,
    ) -> dict[str, Any]:
        """Persist only verified, non-sensitive durable facts to file memory."""

        snapshot = self._memory_snapshot(user_id, session_id)
        messages, _ = self._load_compaction_text(user_id, session_id)
        bounded_text = memory_logic.format_messages_for_prompt(messages)
        facts_result = self.model_adapter.extract_episode_facts(bounded_text)
        proposed_facts = self._model_value(facts_result, "facts", []) or []
        safe_facts = [
            {"fact": safe, "importance": item.get("importance", 0.5)}
            for item in proposed_facts[:3]
            if (safe := self._safe_durable_fact(item.get("fact", "")))
        ]
        file_result = self._add_facts_to_file_memory(safe_facts)
        return self._command_response(
            "/dream",
            user_id,
            session_id,
            "Dream added only verified, non-sensitive durable facts to file memory; MongoDB raw messages were unchanged.",
            snapshot,
            {
                "proposed_facts": proposed_facts[:3],
                "messages_reviewed": len(messages),
                "file_memory": file_result,
                "persisted": file_result["written"],
            },
        )

    def _handle_command(
        self,
        user_id: str,
        session_id: str,
        message: str,
    ) -> dict[str, Any] | None:
        """Handle slash commands before normal chat-model generation."""

        stripped = message.strip()
        if not stripped.startswith("/"):
            return None

        command = stripped.split(maxsplit=1)[0].lower()
        handlers = {
            "/help": self._command_help,
            "/memory": self._command_memory,
            "/compact": self._command_compact,
            "/dream": self._command_dream,
        }
        handler = handlers.get(command)
        if handler is None:
            return self._command_response(
                command,
                user_id,
                session_id,
                "Unknown memory command. Use /help to see the available commands.",
                {"user_id": user_id, "messages": [], "episodic_facts": []},
                {"help": COMMAND_HELP, "unknown_command": command},
            )
        return handler(user_id, session_id)

    def _maybe_save_lifetime_summary(
        self,
        user_id: str,
    ) -> dict[str, Any] | None:
        """Create one bounded lifetime summary when the session count qualifies."""

        session_summaries = self.repository.list_recent_summaries(
            user_id,
            limit=MAX_SESSION_SUMMARIES_FOR_LIFETIME,
        )
        session_summaries = [
            item for item in session_summaries if item.get("scope") == "session"
        ]
        count = len(session_summaries)
        if count < LIFETIME_SUMMARY_EVERY_SESSION_SUMMARIES or (
            count % LIFETIME_SUMMARY_EVERY_SESSION_SUMMARIES != 0
        ):
            return None

        # A lifetime summary is the durable checkpoint for the threshold that
        # has been reached.  If one already exists, do not create a duplicate
        # every time /compact or a later request revisits the same checkpoint.
        if self.repository.get_latest_lifetime_summary(user_id) is not None:
            return None

        summaries_text = "\n".join(
            str(item.get("text", "")) for item in reversed(session_summaries)
        )
        lifetime_result = self.model_adapter.generate_lifetime_summary(summaries_text)
        if self._model_error(lifetime_result):
            self._diagnose(
                "lifetime_summary_failure",
                self._model_error(lifetime_result) or "unknown",
            )
            return None

        lifetime_text = str(self._model_value(lifetime_result, "text", "")).strip()
        if not lifetime_text:
            self._diagnose("lifetime_summary_empty", "model returned no summary text")
            return None

        try:
            return self.repository.save_summary(
                user_id=user_id,
                session_id=None,
                scope="user",
                text=lifetime_text,
            )
        except Exception as exc:
            self._diagnose("lifetime_summary_save_failure", type(exc).__name__)
            return None

    def _maybe_save_summaries(
        self,
        user_id: str,
        session_id: str,
        user_message_count: int,
        conversation_text: str,
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Generate session memory at the trigger and lifetime memory periodically."""

        interval = self.config["summarize_every_user_msgs"]
        if not memory_logic.should_trigger_summary(user_message_count, interval):
            return None, None

        session_result = self.model_adapter.generate_session_summary(conversation_text)
        if self._model_error(session_result):
            self._diagnose("session_summary_failure", self._model_error(session_result) or "unknown")
            return None, None

        session_text = str(self._model_value(session_result, "text", "")).strip()
        if not session_text:
            self._diagnose("session_summary_empty", "model returned no summary text")
            return None, None

        try:
            session_summary = self.repository.save_summary(
                user_id=user_id,
                session_id=session_id,
                scope="session",
                text=session_text,
            )
        except Exception as exc:
            self._diagnose("session_summary_save_failure", type(exc).__name__)
            return None, None

        # Normal chat and /compact now share exactly the same lifetime policy.
        lifetime_summary = self._maybe_save_lifetime_summary(user_id)
        return session_summary, lifetime_summary

    def chat(
        self,
        user_id: str,
        session_id: str | None,
        message: str,
        short_term_n: int | None = None,
    ) -> dict[str, Any]:
        """Run one complete memory-aware chat lifecycle."""

        self.diagnostics = []
        user_id = self._require_text(user_id, "user_id")
        message = self._require_text(message, "message")
        final_session_id = self.ensure_session_id(session_id)
        # Keep the configured value as the default, while allowing Part 3 to
        # select 4, 12, or 30 for a reproducible request-level comparison.
        selected_short_term_n = memory_logic.resolve_short_term_n(
            short_term_n,
            self.config["short_term_n"],
        )

        # Commands are handled before message persistence and model generation
        # so administrative memory actions do not masquerade as chat turns.
        command_result = self._handle_command(user_id, final_session_id, message)
        if command_result is not None:
            return command_result

        self.repository.save_message(
            user_id=user_id,
            session_id=final_session_id,
            role="user",
            content=message,
        )
        user_message_count = self.repository.count_user_messages(
            user_id,
            final_session_id,
        )
        short_term_messages = self.repository.load_short_term_messages(
            user_id,
            final_session_id,
            selected_short_term_n,
        )
        session_summary = self.repository.get_latest_session_summary(
            user_id,
            final_session_id,
        )
        lifetime_summary = self.repository.get_latest_lifetime_summary(user_id)
        session_text = session_summary.get("text") if session_summary else None
        lifetime_text = lifetime_summary.get("text") if lifetime_summary else None

        # The summary-replacement policy is opt-in. When enabled, it replaces
        # only the oldest eligible prompt messages; MongoDB raw messages remain
        # untouched and the current-session summary carries their meaning.
        replacement = memory_logic.apply_summary_replacement_policy(
            short_term_messages,
            session_text,
            message,
            enabled=bool(self.config.get("summary_replacement_enabled", 0)),
            threshold=int(
                self.config.get(
                    "summary_replacement_threshold",
                    memory_logic.SUMMARY_REPLACEMENT_THRESHOLD,
                )
            ),
        )
        prompt_short_term_messages = replacement["messages"]

        episodic_facts: list[dict[str, Any]] = []
        try:
            query_embedding = self.embed_text(message)
            episode_candidates = self.repository.list_all_episodes_for_user(user_id)
            episodic_facts = self.rank_episodes(
                query_embedding,
                episode_candidates,
                top_k=self.config["episodic_top_k"],
            )
        except Exception as exc:
            self._diagnose("episodic_retrieval_failure", type(exc).__name__)

        prompt = memory_logic.build_memory_prompt(
            self.system_primer,
            lifetime_text,
            session_text,
            prompt_short_term_messages,
            message,
            episodic_facts,
        )
        reply_result = self.model_adapter.generate_reply(prompt)
        reply_error = self._model_error(reply_result)
        usage = self._usage(
            reply_result,
            lifetime_text,
            session_text,
            prompt_short_term_messages,
            message,
            episodic_facts,
        )

        if reply_error:
            self._diagnose("model_reply_failure", reply_error)
            return {
                "answer": "",
                "user_id": user_id,
                "session_id": final_session_id,
                "memory_used": {
                    "short_term_count": len(prompt_short_term_messages),
                    "short_term_messages": prompt_short_term_messages,
                    "session_summary": session_text,
                    "lifetime_summary": lifetime_text,
                    "episodic_facts": episodic_facts,
                    "summary_replacement": replacement,
                },
                "usage": usage,
                "component_tokens": usage["component_tokens"],
                "prompt_token_total_estimate": usage["prompt_token_total_estimate"],
                "error": "model_reply_failed",
                "diagnostics": list(self.diagnostics),
            }

        answer = str(self._model_value(reply_result, "text", self._model_value(reply_result, "content", "")))
        assistant_message = self.repository.save_message(
            user_id=user_id,
            session_id=final_session_id,
            role="assistant",
            content=answer,
            token_count=usage["completion_tokens"],
            latency_ms=usage["latency_ms"],
        )

        facts_result = self.model_adapter.extract_episode_facts(message)
        if self._model_error(facts_result):
            self._diagnose("episode_extraction_failure", self._model_error(facts_result) or "unknown")
        stored_facts = self._store_facts(user_id, final_session_id, facts_result)

        conversation_for_summary = memory_logic.format_messages_for_prompt(
            short_term_messages + [assistant_message]
        )
        generated_session_summary, generated_lifetime_summary = self._maybe_save_summaries(
            user_id,
            final_session_id,
            user_message_count,
            conversation_for_summary,
        )

        return {
            "answer": answer,
            "user_id": user_id,
            "session_id": final_session_id,
            "memory_used": {
                "short_term_count": len(prompt_short_term_messages),
                "short_term_messages": prompt_short_term_messages,
                "session_summary": session_text,
                "lifetime_summary": lifetime_text,
                "episodic_facts": episodic_facts,
                "summary_replacement": replacement,
            },
            "usage": usage,
            "component_tokens": usage["component_tokens"],
            "prompt_token_total_estimate": usage["prompt_token_total_estimate"],
            "stored_episode_facts": stored_facts,
            "generated_session_summary": generated_session_summary,
            "generated_lifetime_summary": generated_lifetime_summary,
            "diagnostics": list(self.diagnostics),
        }


__all__ = [
    "LIFETIME_SUMMARY_EVERY_SESSION_SUMMARIES",
    "MemoryService",
    "SYSTEM_PRIMER",
]
