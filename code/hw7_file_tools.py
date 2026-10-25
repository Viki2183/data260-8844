"""Safe local file tools and a model-independent bash safety gate."""

from __future__ import annotations

import difflib
import re
import subprocess
from pathlib import Path

SAFE_PREFIXES = ("python ", "python3 ", "pytest ", "ruff ", "git status", "git diff", "git log")
DESTRUCTIVE_PATTERNS = (
    r"\brm\s+(-[a-z]*r|--recursive)", r"\bdel\s+/s", r"\bformat\b", r"\bmkfs\b",
    r"\bsudo\b", r"\b(runas|chmod|chown)\b", r"/dev/", r"\b(init|mount)\b",
    r"(^|\s)>\s*/", r"\b(erase|rmdir)\b",
    r"\bpython(?:3)?\s+-c\b",
)


def _safe(path: str | Path, root: Path) -> Path:
    candidate = (root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()
    root = root.resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("path is outside the sandbox")
    return candidate


def read_file(path: str | Path, root: Path, max_lines: int | None = None) -> str:
    lines = _safe(path, root).read_text(encoding="utf-8").splitlines()
    return "\n".join(lines if max_lines is None else lines[:max_lines])


def write_file(path: str | Path, content: str, root: Path) -> str:
    target = _safe(path, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return str(target.relative_to(root.resolve()))


def edit_file(path: str | Path, old: str, new: str, root: Path) -> str:
    target = _safe(path, root)
    before = target.read_text(encoding="utf-8")
    if old not in before:
        raise ValueError("text to replace was not found")
    after = before.replace(old, new, 1)
    target.write_text(after, encoding="utf-8")
    return "".join(
        difflib.unified_diff(
            before.splitlines(True),
            after.splitlines(True),
            fromfile=str(path),
            tofile=str(path),
        )
    )


def glob_files(pattern: str, root: Path) -> list[str]:
    return sorted(str(p.relative_to(root.resolve())) for p in root.rglob(pattern) if p.is_file())


def search_in_files(query: str, root: Path, file_pattern: str = "*") -> list[dict[str, object]]:
    matches = []
    for path in root.rglob(file_pattern):
        if not path.is_file():
            continue
        try:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if query in line:
                    matches.append(
                        {
                            "path": str(path.relative_to(root.resolve())),
                            "line": number,
                            "text": line,
                        }
                    )
        except UnicodeDecodeError:
            continue
    return matches


def is_destructive(command: str) -> bool:
    return any(re.search(pattern, command, re.IGNORECASE) for pattern in DESTRUCTIVE_PATTERNS)


def confirm_bash(command: str, auto_approve: bool = False) -> dict[str, object]:
    if is_destructive(command):
        reason = (
            "destructive command requires explicit confirmation"
            if not auto_approve
            else "explicit confirmation supplied"
        )
        return {"allowed": bool(auto_approve), "reason": reason}
    if not any(command.strip().startswith(prefix) for prefix in SAFE_PREFIXES):
        return {"allowed": False, "reason": "command is not on SAFE_PREFIXES allow-list"}
    return {"allowed": True, "reason": "command matches SAFE_PREFIXES"}


def bash(command: str, auto_approve: bool = False) -> dict[str, object]:
    decision = confirm_bash(command, auto_approve)
    if not decision["allowed"]:
        return decision
    completed = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return {
        **decision,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
