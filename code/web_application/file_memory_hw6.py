"""Standalone file-based memory helpers for DATA 260 Homework 6.

This module intentionally does not import the MongoDB, Ollama, or embedding
layers.  File memory is useful for durable human-readable notes, but it should
remain independently testable and must never silently replace database memory.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


FILE_MEMORY_MAX_LINES = 40
FILE_MEMORY_MAX_AGE_HOURS = 24

_DATE_PATTERN = re.compile(r"^\s*(?:last\s+modified|modified_at)\s*:\s*(.+?)\s*$", re.I | re.M)
_CONTRADICTION_PAIRS = (
    ("concise", "detailed"),
    ("short", "long"),
    ("include", "exclude"),
    ("enabled", "disabled"),
    ("allow", "deny"),
    ("prefer", "avoid"),
)


def read_memory_file(path: str | Path) -> str:
    """Read one UTF-8 memory file without contacting any external service."""

    return Path(path).read_text(encoding="utf-8")


def write_memory_file(path: str | Path, content: str) -> None:
    """Write file memory explicitly; callers choose the safe evidence path."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")


def count_memory_lines(content: str) -> int:
    """Count physical, non-empty-or-empty lines consistently for the policy."""

    return len(content.splitlines())


def _coerce_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _modified_at_from_content(content: str, fallback: datetime) -> datetime:
    match = _DATE_PATTERN.search(content)
    if not match:
        return fallback
    value = match.group(1).strip().replace("Z", "+00:00")
    try:
        return _coerce_datetime(datetime.fromisoformat(value))
    except ValueError:
        return fallback


def memory_file_requires_consolidation(
    content: str,
    modified_at: datetime,
    now: datetime,
) -> bool:
    """Apply the bounded policy: more than 40 lines or older than 24 hours."""

    current = _coerce_datetime(now)
    modified = _coerce_datetime(modified_at)
    too_many_lines = count_memory_lines(content) > FILE_MEMORY_MAX_LINES
    too_old = current - modified > timedelta(hours=FILE_MEMORY_MAX_AGE_HOURS)
    return too_many_lines or too_old


def _clean_fact(line: str) -> str:
    cleaned = re.sub(r"^\s*[-*]\s*", "", line.strip())
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_memory_facts(content: str) -> list[str]:
    """Extract human-readable fact lines while ignoring headings and metadata."""

    facts: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("---"):
            continue
        if _DATE_PATTERN.match(stripped) or stripped.lower().startswith("metadata:"):
            continue
        fact = _clean_fact(stripped)
        if fact.lower().startswith("conflict:"):
            continue
        if fact:
            # Consolidated groups use a visible separator so they remain
            # compact on disk while still being recoverable as individual facts.
            facts.extend(part.strip() for part in fact.split(" | ") if part.strip())
    return facts


def _fact_key(fact: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", fact.lower()).strip()


def remove_duplicate_facts(facts: list[str]) -> tuple[list[str], int]:
    """Keep first occurrences in order and count exact normalized duplicates."""

    unique: list[str] = []
    seen: set[str] = set()
    duplicates = 0
    for fact in facts:
        key = _fact_key(fact)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        unique.append(fact)
    return unique, duplicates


def _contains_word(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text.lower()) is not None


def detect_contradictions(facts: list[str]) -> list[dict[str, str]]:
    """Find explicit opposing terms and retain both sides for human review."""

    conflicts: list[dict[str, str]] = []
    for index, left in enumerate(facts):
        left_lower = left.lower()
        for right in facts[index + 1 :]:
            right_lower = right.lower()
            for first, second in _CONTRADICTION_PAIRS:
                opposing = (_contains_word(left_lower, first) and _contains_word(right_lower, second)) or (
                    _contains_word(left_lower, second) and _contains_word(right_lower, first)
                )
                if opposing:
                    conflicts.append({"left": left, "right": right})
                    break
    return conflicts


def _format_consolidated(facts: list[str], conflicts: list[dict[str, str]], now: datetime) -> str:
    grouped: dict[str, list[str]] = {}
    for fact in facts:
        prefix = fact.split(":", 1)[0].strip() if ":" in fact else "General"
        group = "Project notes" if prefix.lower().startswith("note ") else prefix
        grouped.setdefault(group, []).append(fact)

    lines = [
        "# Consolidated file memory",
        f"Generated at: {_coerce_datetime(now).isoformat()}",
        "",
        "## Retained facts",
    ]
    for group in sorted(grouped):
        lines.append(f"### {group}")
        # Joining related notes keeps the consolidated file bounded while
        # retaining their meaning in one human-readable group.
        lines.append(f"- {' | '.join(grouped[group])}")
    lines.extend(["", "## Needs review"])
    if conflicts:
        for conflict in conflicts:
            lines.append(f"- Conflict: {conflict['left']} | CONTRADICTS | {conflict['right']}")
    else:
        lines.append("- No contradictions detected.")
    return "\n".join(lines) + "\n"


def consolidate_memory(
    content: str,
    now: datetime | None = None,
    modified_at: datetime | None = None,
) -> dict[str, Any]:
    """Create deterministic consolidated text while preserving the original."""

    current = _coerce_datetime(now or datetime.now(timezone.utc))
    modified = _coerce_datetime(modified_at) if modified_at is not None else _modified_at_from_content(content, current)
    facts = extract_memory_facts(content)
    unique, duplicate_count = remove_duplicate_facts(facts)
    conflicts = detect_contradictions(unique)
    consolidated = _format_consolidated(unique, conflicts, current)
    return {
        "original_text": content,
        "consolidated_text": consolidated,
        "before_line_count": count_memory_lines(content),
        "after_line_count": count_memory_lines(consolidated),
        "duplicate_count": duplicate_count,
        "contradiction_count": len(conflicts),
        "contradictions": conflicts,
        "triggered": memory_file_requires_consolidation(content, modified, current),
        "modified_at": modified.isoformat(),
        "generated_at": current.isoformat(),
    }


def compare_file_memory_with_mongodb(
    file_facts: list[str],
    mongo_facts: list[str],
) -> dict[str, Any]:
    """Compare supplied facts only; this function never opens MongoDB."""

    file_by_key = {_fact_key(fact): fact for fact in file_facts}
    mongo_by_key = {_fact_key(fact): fact for fact in mongo_facts}
    shared_keys = sorted(set(file_by_key) & set(mongo_by_key))
    file_only_keys = sorted(set(file_by_key) - set(mongo_by_key))
    mongo_only_keys = sorted(set(mongo_by_key) - set(file_by_key))
    conflicts = detect_contradictions([*file_facts, *mongo_facts])
    return {
        "facts_known_by_file": list(file_by_key.values()),
        "facts_known_by_mongodb": list(mongo_by_key.values()),
        "shared": [file_by_key[key] for key in shared_keys],
        "only_in_file": [file_by_key[key] for key in file_only_keys],
        "only_in_mongodb": [mongo_by_key[key] for key in mongo_only_keys],
        "contradictions_or_conflicts": conflicts,
    }


def generate_consolidation_function() -> Callable[..., dict[str, Any]]:
    """Return the generated consolidation function for offline verification."""

    return consolidate_memory


def verify_generated_consolidation(test_content: str) -> dict[str, Any]:
    """Verify determinism, duplicate handling, conflicts, and both triggers."""

    generated = generate_consolidation_function()
    now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
    first = generated(test_content, now=now)
    second = generated(test_content, now=now)
    old_content = "Last modified: 2026-10-15T00:00:00Z\n" + test_content
    old_result = generated(old_content, now=now)
    line_trigger = first["before_line_count"] > FILE_MEMORY_MAX_LINES and first["triggered"]
    age_trigger = old_result["triggered"]
    return {
        "deterministic": first["consolidated_text"] == second["consolidated_text"],
        "duplicate_removal": first["duplicate_count"] > 0,
        "contradiction_detection": first["contradiction_count"] > 0,
        "line_rule": line_trigger,
        "age_rule": age_trigger,
        "duplicate_count": first["duplicate_count"],
        "contradiction_count": first["contradiction_count"],
        "before_line_count": first["before_line_count"],
        "after_line_count": first["after_line_count"],
        "passed": all((
            first["consolidated_text"] == second["consolidated_text"],
            first["duplicate_count"] > 0,
            first["contradiction_count"] > 0,
            line_trigger,
            age_trigger,
        )),
    }


__all__ = [
    "FILE_MEMORY_MAX_AGE_HOURS",
    "FILE_MEMORY_MAX_LINES",
    "compare_file_memory_with_mongodb",
    "consolidate_memory",
    "count_memory_lines",
    "detect_contradictions",
    "extract_memory_facts",
    "generate_consolidation_function",
    "memory_file_requires_consolidation",
    "read_memory_file",
    "remove_duplicate_facts",
    "verify_generated_consolidation",
    "write_memory_file",
]
