"""Persistent JSON lesson memory for HW9 experiments."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class LessonStore:
    def __init__(self, path: Path):
        self.path = path
        if not self.path.exists():
            self.path.write_text("[]\n", encoding="utf-8")

    def load(self) -> list[dict[str, Any]]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, lessons: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(lessons, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def create(self, failure_pattern: str, correction: str) -> dict[str, Any]:
        lesson = {
            "lesson_id": f"lesson-{uuid.uuid4().hex[:12]}",
            "failure_pattern": failure_pattern,
            "correction": correction,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "use_count": 0,
        }
        lessons = self.load()
        lessons.append(lesson)
        self.save(lessons)
        return lesson

    def relevant(self, question: str) -> list[dict[str, Any]]:
        words = set(question.lower().replace("?", " ").split())
        lessons = self.load()
        selected = [
            lesson
            for lesson in lessons
            if words & set(lesson["failure_pattern"].lower().split())
        ]
        for lesson in selected:
            lesson["use_count"] += 1
        if selected:
            self.save(lessons)
        return selected
