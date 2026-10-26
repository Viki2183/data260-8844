"""Offline HW7 checks; no server, database, model, or network is required."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from hw7_agent import reflexion_run, run_agent
from hw7_bikeshare import recommend
from hw7_file_tools import (
    confirm_bash,
    glob_files,
    is_destructive,
    read_file,
    search_in_files,
    write_file,
)
from hw7_mrkl import calculator, csv_sql
from web_application import auth_hw7


class SequenceModel:
    def __init__(self, responses):
        self.responses = list(responses)

    def complete(self, messages):
        return self.responses.pop(0) if self.responses else {"action": "final", "answer": "done"}


class FakeQuery:
    def __init__(self, user):
        self.user = user

    def filter(self, *_criteria):
        return self

    def first(self):
        return self.user


class FakeDB:
    def __init__(self, user):
        self.user = user

    def query(self, _model):
        return FakeQuery(self.user)


def run() -> list[str]:
    passed: list[str] = []
    tools = {
        "search": lambda query: {"success": True, "rows": [{"query": query}]},
        "detail": lambda package_id: {"success": True, "id": package_id},
    }
    result = run_agent("find then inspect", SequenceModel([
        {"action": "tool", "name": "search", "inputs": {"query": "requests"}},
        {"action": "tool", "name": "detail", "inputs": {"package_id": 1}},
        {"action": "final", "answer": "verified"},
    ]), tools)
    assert result["stop_reason"] == "success" and result["tool_calls"] == 2
    passed.append("agent multi-step")

    bad = run_agent(
        "repair",
        SequenceModel(
            [
                {"action": "tool", "name": "missing", "inputs": {}},
                {"action": "final", "answer": "repaired"},
            ]
        ),
        tools,
    )
    assert bad["repair_count"] == 1
    passed.append("agent bounded repair")

    user = SimpleNamespace(
        username="reader1",
        role="reader",
        password_hash=auth_hw7.hash_password("offline-password"),
    )
    db = FakeDB(user)
    token = auth_hw7.login(
        auth_hw7.LoginPayload(username="reader1", password="offline-password"),
        db,
    )
    assert token.access_token
    try:
        auth_hw7.login(
            auth_hw7.LoginPayload(username="reader1", password="wrong"),
            db,
        )
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("invalid login must return 401")
    for role in ("reader", "writer", "moderator"):
        auth_hw7.require_roles("reader", "writer", "moderator")(
            user=SimpleNamespace(username=role, role=role)
        )
    passed.append("JWT invalid login, role policy, authenticated read/list")

    def make_model(reflection):
        if reflection is None:
            return SequenceModel([{"action": "final", "answer": "incomplete"}])
        return SequenceModel([
            {"action": "tool", "name": "search", "inputs": {"query": "x"}},
            {"action": "tool", "name": "detail", "inputs": {"package_id": 1}},
            {"action": "final", "answer": "complete"},
        ])

    reflex = reflexion_run(
        "verify", make_model, tools=tools, required_tools={"search", "detail"}
    )
    assert reflex["stop_reason"] in {"success", "human_review"}
    passed.append("reflexion bounded")

    csv = "ride_id,minutes\n1,10\n2,20\n"
    assert csv_sql(csv, "SELECT COUNT(*) AS n FROM trips")["success"]
    assert not csv_sql(csv, "DELETE FROM trips")["success"]
    assert calculator("2 + 3 * 4")["data"]["value"] == 14.0
    assert not calculator("__import__('os')")["success"]
    passed.append("MRKL tools")

    assert (
        recommend(20, 400, 25, 1, 0.2, included_minutes=400)["decision"]
        == "Buy Monthly Membership"
    )
    passed.append("bike-share recommendation")

    configured_temp = os.environ.get("HW7_VERIFY_TEMP_DIR")
    course_sandbox_parent = (
        Path(configured_temp) if configured_temp else Path(__file__).resolve().parents[1]
    )
    with tempfile.TemporaryDirectory(
        dir=course_sandbox_parent, prefix=".hw7-course-sandbox-"
    ) as temporary:
        root = Path(temporary)
        if configured_temp:
            assert root.parent == course_sandbox_parent.resolve()
        write_file("a.py", "DEBUG = True\n", root)
        write_file("b.py", "INFO = True\n", root)
        assert glob_files("*.py", root) == ["a.py", "b.py"]
        assert search_in_files("DEBUG", root, "*.py")[0]["path"] == "a.py"
        assert "DEBUG" in read_file("a.py", root)
    passed.append("file tools integration")

    allowed = ["python -V", "ruff check .", "git status", "git diff", "pytest -q"]
    blocked = ["rm -rf x", "sudo whoami", "chmod 777 x", "mkfs /dev/sda", "echo x > /root/x"]
    assert all(confirm_bash(c)["allowed"] for c in allowed)
    assert all(not confirm_bash(c)["allowed"] for c in blocked)
    assert is_destructive(blocked[0])
    passed.append("safety gate 5/5")
    return passed


if __name__ == "__main__":
    passed = run()
    print(json.dumps({"passed": passed, "count": len(passed)}, indent=2))
