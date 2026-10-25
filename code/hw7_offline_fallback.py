"""Deterministic HW7 checks that do not require pytest, a server, or databases."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import HTTPException
from hw7_agent import reflexion_run, run_agent
from hw7_file_tools import confirm_bash, is_destructive
from hw7_mrkl import calculator, csv_sql
from web_application import auth_hw7


class FakeModel:
    def __init__(self, responses):
        self.responses = list(responses)

    def complete(self, _messages):
        return self.responses.pop(0)


class FakeQuery:
    def __init__(self, user):
        self.user = user

    def filter(self, *_args):
        return self

    def first(self):
        return self.user


class FakeDB:
    def __init__(self, user):
        self.user = user

    def query(self, _model):
        return FakeQuery(self.user)


def expect_http_error(call, status_code: int) -> None:
    try:
        call()
    except HTTPException as exc:
        assert exc.status_code == status_code
    else:
        raise AssertionError(f"expected HTTP {status_code}")


def check_jwt_and_roles() -> None:
    password = "offline-password"
    user = SimpleNamespace(
        username="alice",
        role="reader",
        password_hash=auth_hw7.hash_password(password),
    )
    db = FakeDB(user)
    token = auth_hw7.login(auth_hw7.LoginPayload(username="alice", password=password), db)
    claims = auth_hw7.decode_access_token(token.access_token)
    assert claims["username"] == "alice"
    assert auth_hw7.verify_password(password, user.password_hash)
    assert user.password_hash != password
    expect_http_error(
        lambda: auth_hw7.login(
            auth_hw7.LoginPayload(username="alice", password="wrong"), db
        ),
        401,
    )
    expect_http_error(lambda: auth_hw7.decode_access_token(token.access_token[:-1] + "x"), 401)
    expect_http_error(
        lambda: auth_hw7.decode_access_token(
            auth_hw7.create_access_token("alice", "reader", now=100),
            now=100 + auth_hw7.JWT_TTL_SECONDS,
        ),
        401,
    )
    for role, create_ok, delete_ok in (
        ("reader", False, False),
        ("writer", True, False),
        ("moderator", True, True),
    ):
        identity = SimpleNamespace(username=role, role=role)
        auth_hw7.require_roles("reader", "writer", "moderator")(user=identity)
        if create_ok:
            auth_hw7.require_roles("writer", "moderator")(user=identity)
        else:
            expect_http_error(
                lambda: auth_hw7.require_roles("writer", "moderator")(user=identity),
                403,
            )
        if delete_ok:
            auth_hw7.require_roles("moderator")(user=identity)
        else:
            expect_http_error(
                lambda: auth_hw7.require_roles("moderator")(user=identity),
                403,
            )


def check_agent_and_reflexion() -> None:
    tools = {
        "search": lambda query: {"success": True, "query": query},
        "detail": lambda package_id: {"success": package_id == 1, "id": package_id},
    }
    result = run_agent(
        "verify",
        FakeModel(
            [
                {"action": "tool", "name": "search", "inputs": {"query": "x"}},
                {"action": "tool", "name": "detail", "inputs": {"package_id": 1}},
                {"action": "final", "answer": "done"},
            ]
        ),
        tools,
    )
    assert result["stop_reason"] == "success"
    assert result["tool_calls"] == 2
    repaired = run_agent(
        "repair",
        FakeModel(
            [
                {"action": "tool", "name": "unknown", "inputs": {}},
                {"action": "final", "answer": "recovered"},
            ]
        ),
        tools,
    )
    assert repaired["repair_count"] == 1
    ceiling = run_agent(
        "ceiling",
        FakeModel([{"action": "tool", "name": "search", "inputs": {"query": "x"}}] * 4),
        tools,
        max_steps=2,
    )
    assert ceiling["stop_reason"] == "budget_exhausted"
    assert ceiling["tool_calls"] == 2

    def model_factory(reflection):
        if reflection is None:
            return FakeModel([{"action": "final", "answer": "incomplete"}])
        return FakeModel(
            [
                {"action": "tool", "name": "search", "inputs": {"query": "x"}},
                {"action": "tool", "name": "detail", "inputs": {"package_id": 1}},
                {"action": "final", "answer": "complete"},
            ]
        )

    retried = reflexion_run("task", model_factory, tools, {"search", "detail"})
    assert retried["stop_reason"] == "success"
    assert len(retried["reflections"]) == 1

    def always_fail(_reflection):
        return FakeModel([{"action": "final", "answer": ""}])

    reviewed = reflexion_run("task", always_fail, tools, {"search"}, max_retries=2)
    assert reviewed["stop_reason"] == "human_review"
    assert len(reviewed["reflections"]) == 2


def check_mrkl_and_safety() -> None:
    csv_text = "ride_id,minutes\n1,10\n2,20\n"
    assert csv_sql(csv_text, "SELECT COUNT(*) AS n FROM trips")["success"]
    assert not csv_sql(csv_text, "DELETE FROM trips")["success"]
    assert calculator("2 + 3 * 4")["data"]["value"] == 14.0
    assert not calculator("__import__('os')")["success"]

    allowed = ["python -V", "ruff check .", "git status", "git diff", "pytest -q"]
    blocked = [
        "rm -rf x",
        "sudo whoami",
        "chmod 777 x",
        "mkfs /dev/sda",
        "echo x > /root/x",
    ]
    assert all(confirm_bash(command)["allowed"] for command in allowed)
    assert all(not confirm_bash(command)["allowed"] for command in blocked)
    assert all(is_destructive(command) for command in blocked)


def main() -> None:
    checks = (
        ("JWT, password hashing, and role policy", check_jwt_and_roles),
        ("agent and Reflexion bounds", check_agent_and_reflexion),
        ("MRKL and safety gates", check_mrkl_and_safety),
    )
    for name, check in checks:
        check()
        print(f"PASS {name}")
    print("HW7_OFFLINE_FALLBACK_PASS")


if __name__ == "__main__":
    main()
