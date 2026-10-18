"""Pure prompt and memory-decision helpers for DATA 260 Homework 6."""

from __future__ import annotations

import math
import os
import re
from typing import Any


DEFAULT_SHORT_TERM_N = 12
MIN_SHORT_TERM_N = 1
MAX_SHORT_TERM_N = 30
DEFAULT_SUMMARIZE_EVERY_USER_MSGS = 5
MIN_SUMMARIZE_EVERY_USER_MSGS = 1
MAX_SUMMARIZE_EVERY_USER_MSGS = 1000
DEFAULT_EPISODIC_TOP_K = 3
MIN_EPISODIC_TOP_K = 1
MAX_EPISODIC_TOP_K = 20
SUMMARY_REPLACEMENT_POLICY_ENABLED = False
SUMMARY_REPLACEMENT_THRESHOLD = 12
MIN_SUMMARY_REPLACEMENT_THRESHOLD = 1
MAX_SUMMARY_REPLACEMENT_THRESHOLD = 30
MAX_FACT_LENGTH = 500
MAX_FACT_CANDIDATES = 3


def _bounded_int(
    environment_name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    """Read an integer setting and safely constrain it to its valid range."""

    try:
        value = int(os.getenv(environment_name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def get_memory_config() -> dict[str, int]:
    """Return bounded memory settings used by later chat orchestration."""

    return {
        "short_term_n": _bounded_int(
            "SHORT_TERM_N",
            DEFAULT_SHORT_TERM_N,
            MIN_SHORT_TERM_N,
            MAX_SHORT_TERM_N,
        ),
        "summarize_every_user_msgs": _bounded_int(
            "SUMMARIZE_EVERY_USER_MSGS",
            DEFAULT_SUMMARIZE_EVERY_USER_MSGS,
            MIN_SUMMARIZE_EVERY_USER_MSGS,
            MAX_SUMMARIZE_EVERY_USER_MSGS,
        ),
        "episodic_top_k": _bounded_int(
            "EPISODIC_TOP_K",
            DEFAULT_EPISODIC_TOP_K,
            MIN_EPISODIC_TOP_K,
            MAX_EPISODIC_TOP_K,
        ),
        # This policy is deliberately opt-in so existing HW6 window results
        # retain their original prompt-selection behavior.
        "summary_replacement_enabled": int(
            os.getenv("HW6_SUMMARY_REPLACEMENT_ENABLED", "0").strip().lower()
            in {"1", "true", "yes", "on"}
        ),
        "summary_replacement_threshold": _bounded_int(
            "HW6_SUMMARY_REPLACEMENT_THRESHOLD",
            SUMMARY_REPLACEMENT_THRESHOLD,
            MIN_SUMMARY_REPLACEMENT_THRESHOLD,
            MAX_SUMMARY_REPLACEMENT_THRESHOLD,
        ),
    }


def resolve_short_term_n(requested: int | None, configured_default: int) -> int:
    """Choose a bounded per-request window without changing the default.

    The 1--30 bound keeps experiments reproducible and prevents a request from
    accidentally turning the prompt into an unbounded history dump.
    """

    value = configured_default if requested is None else requested
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 30:
        raise ValueError("short_term_n must be between 1 and 30")
    return value


def apply_summary_replacement_policy(
    messages: list[dict[str, Any]],
    session_summary: str | None,
    current_message: str,
    *,
    enabled: bool = SUMMARY_REPLACEMENT_POLICY_ENABLED,
    threshold: int = SUMMARY_REPLACEMENT_THRESHOLD,
) -> dict[str, Any]:
    """Bound recent context by replacing its oldest eligible block.

    This is a prompt policy, not physical deletion: raw MongoDB messages stay
    intact, while the existing session-summary section stands in for older
    eligible messages. The current user message and newest prior messages are
    retained, making the policy measurable without changing normal behavior
    unless it is explicitly enabled.
    """

    if not MIN_SUMMARY_REPLACEMENT_THRESHOLD <= threshold <= MAX_SUMMARY_REPLACEMENT_THRESHOLD:
        raise ValueError("summary replacement threshold must be between 1 and 30")

    copied = [dict(message) for message in messages]
    if not enabled or not session_summary:
        return {
            "messages": copied,
            "replaced_message_count": 0,
            "triggered": False,
            "threshold": threshold,
            "summary_included": bool(session_summary),
        }

    current = current_message.strip()
    current_entries = [
        message
        for message in copied
        if (
            str(message.get("role", "")).lower() == "user"
            and str(message.get("content", "")).strip() == current
        )
    ]
    prior_entries = [message for message in copied if message not in current_entries]
    if len(prior_entries) <= threshold:
        return {
            "messages": copied,
            "replaced_message_count": 0,
            "triggered": False,
            "threshold": threshold,
            "summary_included": True,
        }

    # Keep the newest prior messages and the current user entry. The omitted
    # oldest block is represented by the already-labeled session-summary
    # prompt section, so it is not silently forgotten or duplicated.
    retained_prior = prior_entries[-threshold:]
    retained = [*retained_prior, *current_entries]
    retained.sort(key=lambda item: item.get("created_at", ""))
    return {
        "messages": retained,
        "replaced_message_count": len(prior_entries) - len(retained_prior),
        "triggered": True,
        "threshold": threshold,
        "summary_included": True,
    }


def should_trigger_summary(
    user_message_count: int,
    summarize_every_user_msgs: int,
) -> bool:
    """Return whether a positive count reaches an exact summary interval."""

    if summarize_every_user_msgs < 1:
        raise ValueError("summarize_every_user_msgs must be at least 1")
    return user_message_count > 0 and user_message_count % summarize_every_user_msgs == 0


def estimate_token_count(text: str) -> int:
    """Estimate tokens deterministically; this is not exact model metadata.

    Local experiments use approximately 1.3 tokens per whitespace-delimited
    word.  Actual Ollama usage values should replace this estimate later.
    """

    words = re.findall(r"\S+", text or "")
    return math.ceil(len(words) * 1.3)


def format_messages_for_prompt(messages: list[dict[str, Any]]) -> str:
    """Format messages chronologically without exposing IDs or database fields."""

    if not messages:
        return "(empty)"

    lines: list[str] = []
    for message in messages:
        role = str(message.get("role", "unknown")).capitalize()
        content = str(message.get("content", "")).strip()
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def format_episodes_for_prompt(episodes: list[dict[str, Any]]) -> str:
    """Format relevance-ordered facts without embeddings or MongoDB IDs."""

    if not episodes:
        return "(empty)"

    lines: list[str] = []
    for episode in episodes:
        fact = str(episode.get("fact", "")).strip()
        if not fact:
            continue

        details = []
        if "importance" in episode:
            details.append(f"importance={episode['importance']}")
        if "similarity" in episode:
            details.append(f"similarity={episode['similarity']}")
        suffix = f" ({', '.join(details)})" if details else ""
        lines.append(f"- {fact}{suffix}")

    return "\n".join(lines) if lines else "(empty)"


def _memory_section(label: str, content: str | None) -> str:
    """Give every prompt section a stable label and explicit empty marker."""

    cleaned = (content or "").strip()
    return f"## {label}\n{cleaned if cleaned else '(empty)'}"


def _prompt_sections(
    system_primer: str,
    lifetime_summary: str | None,
    session_summary: str | None,
    short_term_messages: list[dict[str, Any]],
    current_message: str,
    episodic_facts: list[dict[str, Any]],
) -> dict[str, str]:
    """Build the same labeled sections used by the final prompt.

    Keeping prompt construction and token estimation together prevents the
    metrics from quietly describing a different prompt than the model saw.
    The current user message is removed from history before both operations so
    it is represented exactly once.
    """

    current = current_message.strip()
    prior_messages = [
        message
        for message in short_term_messages
        if not (
            str(message.get("role", "")).lower() == "user"
            and str(message.get("content", "")).strip() == current
        )
    ]
    return {
        # Count meaningful content rather than fixed labels or empty markers.
        # An absent memory source should honestly contribute zero estimate.
        "primer": system_primer.strip(),
        "lifetime_summary": (lifetime_summary or "").strip(),
        "session_summary": (session_summary or "").strip(),
        "episodic_facts": (
            format_episodes_for_prompt(episodic_facts)
            if episodic_facts
            else ""
        ),
        "short_term_window": (
            format_messages_for_prompt(prior_messages)
            if prior_messages
            else ""
        ),
        "current_user_message": current,
    }


def build_memory_prompt(
    system_primer: str,
    lifetime_summary: str | None,
    session_summary: str | None,
    short_term_messages: list[dict[str, Any]],
    current_message: str,
    episodic_facts: list[dict[str, Any]],
) -> str:
    """Build a deterministic, labeled prompt from the available memory.

    The current message is kept separate from prior conversation.  Matching
    user messages are omitted from the recent section so the current message
    appears exactly once when a caller has already included it in that list.
    """

    sections = _prompt_sections(
        system_primer,
        lifetime_summary,
        session_summary,
        short_term_messages,
        current_message,
        episodic_facts,
    )
    prompt_sections = [
        _memory_section("System instructions", sections["primer"]),
        _memory_section("Lifetime memory", sections["lifetime_summary"]),
        _memory_section("Current-session summary", sections["session_summary"]),
        _memory_section("Relevant episodic facts", sections["episodic_facts"]),
        _memory_section("Recent conversation", sections["short_term_window"]),
        _memory_section("Current user message", sections["current_user_message"]),
    ]
    return "\n\n".join(prompt_sections)


def get_memory_usage_breakdown(
    system_primer: str,
    lifetime_summary: str | None,
    session_summary: str | None,
    short_term_messages: list[dict[str, Any]],
    current_message: str,
    episodic_facts: list[dict[str, Any]],
) -> dict[str, int]:
    """Return estimated tokens for the prompt's content sections.

    These are deterministic estimates, not Ollama tokenizer counts.  Legacy
    aliases remain in the result so older experiment readers can continue to
    interpret the existing usage fields. Fixed labels and empty markers are
    excluded, so absent memory contributes zero.
    """

    sections = _prompt_sections(
        system_primer,
        lifetime_summary,
        session_summary,
        short_term_messages,
        current_message,
        episodic_facts,
    )
    component_keys = (
        "primer",
        "lifetime_summary",
        "session_summary",
        "short_term_window",
        "episodic_facts",
        "current_user_message",
    )
    counts = {
        key: estimate_token_count(sections[key]) if sections[key] else 0
        for key in component_keys
    }
    counts["estimated_prompt_total"] = sum(counts.values())

    # Preserve the names used by earlier HW6 usage records for compatibility.
    counts.update(
        {
            "system_primer_tokens": counts["primer"],
            "long_term_tokens": (
                counts["lifetime_summary"] + counts["session_summary"]
            ),
            "short_term_tokens": counts["short_term_window"],
            "episodic_tokens": counts["episodic_facts"],
            "current_message_tokens": counts["current_user_message"],
            "total_estimated_tokens": counts["estimated_prompt_total"],
        }
    )
    return counts


def extract_fact_candidates(
    raw_facts: list[dict[str, Any]],
) -> list[dict[str, float | str]]:
    """Normalize at most three useful fact candidates without embeddings."""

    candidates: list[dict[str, float | str]] = []
    for raw_fact in raw_facts:
        fact = str(raw_fact.get("fact", "")).strip()
        if not fact:
            continue

        try:
            importance = float(raw_fact.get("importance", 0.5))
        except (TypeError, ValueError):
            importance = 0.5

        candidate = {
            "fact": fact[:MAX_FACT_LENGTH],
            "importance": max(0.0, min(1.0, importance)),
        }
        candidates.append(candidate)
        if len(candidates) == MAX_FACT_CANDIDATES:
            break

    return candidates


def summarize_trigger_info(
    user_message_count: int,
    summarize_every_user_msgs: int | None = None,
) -> dict[str, int | bool]:
    """Explain the current summary trigger state for logs and experiments."""

    interval = (
        summarize_every_user_msgs
        if summarize_every_user_msgs is not None
        else get_memory_config()["summarize_every_user_msgs"]
    )
    if interval < 1:
        raise ValueError("summarize_every_user_msgs must be at least 1")
    return {
        "user_message_count": user_message_count,
        "summarize_every_user_msgs": interval,
        "should_generate_summary": should_trigger_summary(
            user_message_count,
            interval,
        ),
    }


__all__ = [
    "apply_summary_replacement_policy",
    "build_memory_prompt",
    "estimate_token_count",
    "extract_fact_candidates",
    "format_episodes_for_prompt",
    "format_messages_for_prompt",
    "get_memory_config",
    "get_memory_usage_breakdown",
    "resolve_short_term_n",
    "should_trigger_summary",
    "summarize_trigger_info",
]
