"""Offline-only Phase 3 tests for DATA260 HW7."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException
from hw7_agent import reflexion_run, run_agent
from hw7_bikeshare import recommend
from hw7_file_tools import (
    SAFE_PREFIXES,
    bash,
    confirm_bash,
    edit_file,
    glob_files,
    is_destructive,
    read_file,
    search_in_files,
    write_file,
)
from hw7_mrkl import calculator, csv_sql
from hw7_prompt_security import mark_untrusted
from web_application import auth_hw7


class FakeQuery:
    def __init__(self, user):
        self.user = user

    def filter(self, *criteria):
        for criterion in criteria:
            if getattr(getattr(criterion, "left", None), "key", None) != "username":
                continue
            expected = getattr(getattr(criterion, "right", None), "value", None)
            if expected is not None and getattr(self.user, "username", None) != expected:
                self.user = None
        return self

    def first(self):
        return self.user


class FakeDB:
    def __init__(self, user):
        self.user = user

    def query(self, _model):
        return FakeQuery(self.user)


class SequenceModel:
    def __init__(self, responses):
        self.responses = list(responses)

    def complete(self, _messages):
        return self.responses.pop(0) if self.responses else {"action": "final", "answer": "done"}


class CapturingSequenceModel(SequenceModel):
    def __init__(self, responses):
        super().__init__(responses)
        self.messages = []

    def complete(self, messages):
        self.messages.append(messages)
        return super().complete(messages)


def expect_status(call, status_code: int) -> None:
    try:
        call()
    except HTTPException as exc:
        assert exc.status_code == status_code, exc
    else:
        raise AssertionError(f"expected HTTP {status_code}")


def test_jwt() -> None:
    password = "correct horse battery staple"
    user = SimpleNamespace(
        username="alice",
        role="reader",
        password_hash=auth_hw7.hash_password(password),
    )
    db = FakeDB(user)
    token_response = auth_hw7.login(auth_hw7.LoginPayload(username="alice", password=password), db)
    claims = auth_hw7.decode_access_token(token_response.access_token)
    assert claims["username"] == "alice" and claims["role"] == "reader"
    assert user.password_hash != password
    assert auth_hw7.verify_password(password, user.password_hash)
    expect_status(
        lambda: auth_hw7.login(
            auth_hw7.LoginPayload(username="missing", password=password), db
        ),
        401,
    )
    expect_status(
        lambda: auth_hw7.login(
            auth_hw7.LoginPayload(username="alice", password="wrong"), db
        ),
        401,
    )
    token_parts = token_response.access_token.split(".")
    token_parts[-1] = ("a" if token_parts[-1][0] != "a" else "b") + token_parts[-1][1:]
    tampered = ".".join(token_parts)
    expect_status(lambda: auth_hw7.decode_access_token(tampered), 401)
    expired = auth_hw7.create_access_token("alice", "reader", now=100)
    expect_status(
        lambda: auth_hw7.decode_access_token(
            expired, now=100 + auth_hw7.JWT_TTL_SECONDS
        ),
        401,
    )
    expect_status(lambda: auth_hw7.get_current_user(None, db), 401)
    identity = auth_hw7.me(user)
    assert identity.username == "alice" and identity.role == "reader"
    try:
        auth_hw7.create_access_token("alice", "admin")
    except ValueError:
        pass
    else:
        raise AssertionError("unsupported role should raise ValueError")
    print("PASS JWT valid/invalid/signature/expiry/missing/me/plaintext/role validation")


def test_authorization() -> None:
    roles = (("reader", False, False), ("writer", True, False), ("moderator", True, True))
    for role, can_create, can_delete in roles:
        user = SimpleNamespace(username=role, role=role)
        auth_hw7.require_roles("reader", "writer", "moderator")(user=user)
        if can_create:
            auth_hw7.require_roles("writer", "moderator")(user=user)
        else:
            expect_status(lambda: auth_hw7.require_roles("writer", "moderator")(user=user), 403)
        if can_delete:
            auth_hw7.require_roles("moderator")(user=user)
        else:
            expect_status(lambda: auth_hw7.require_roles("moderator")(user=user), 403)
    print("PASS authorization read/list/create/delete matrix")


def test_agent() -> None:
    tools = {
        "search": lambda query: {
            "success": True,
            "rows": [{"id": 1, "query": query}],
        },
        "detail": lambda package_id: {"success": package_id == 1, "id": package_id},
    }
    result = run_agent("verify", SequenceModel([
        {"action": "tool", "name": "search", "inputs": {"query": "x"}},
        {"action": "tool", "name": "detail", "inputs": {"package_id": 1}},
        {"action": "final", "answer": "verified"},
    ]), tools)
    assert result["stop_reason"] == "success" and result["tool_calls"] == 2
    assert [item["tool"] for item in result["trace"]] == ["search", "detail"]
    assert result["trace"][0]["inputs"] == {"query": "x"}
    repaired = run_agent("repair", SequenceModel([
        {"action": "tool", "name": "unknown", "inputs": {}},
        {"action": "final", "answer": "recovered"},
    ]), tools)
    assert repaired["repair_count"] == 1 and repaired["stop_reason"] == "success"
    malformed = run_agent("repair", SequenceModel([
        {"action": "tool", "name": "search", "inputs": "bad"},
        {"action": "final", "answer": "recovered"},
    ]), tools)
    assert malformed["repair_count"] == 1
    ceiling = run_agent("loop", SequenceModel([
        {"action": "tool", "name": "search", "inputs": {"query": "x"}},
    ] * 5), tools, max_steps=2)
    assert ceiling["stop_reason"] == "budget_exhausted" and ceiling["tool_calls"] == 2
    final = run_agent(
        "answer",
        SequenceModel([{"action": "final", "answer": "already known"}]),
        tools,
    )
    assert final["tool_calls"] == 0

    captured = CapturingSequenceModel([
        {"action": "tool", "name": "search", "inputs": {"query": "x"}},
        {"action": "final", "answer": "captured"},
    ])
    captured_result = run_agent("capture", captured, tools)
    assert captured_result["stop_reason"] == "success"
    tool_messages = [
        message
        for message in captured.messages[1]
        if message.get("role") == "tool"
    ]
    assert tool_messages[0]["tool_call_id"] == "hw7-tool-call-1"

    required_model = CapturingSequenceModel([
        {"action": "tool", "name": "search", "inputs": {"query": "x"}},
        {"action": "final", "answer": "premature"},
        {"action": "tool", "name": "detail", "inputs": {"package_id": 1}},
        {"action": "final", "answer": "complete"},
    ])
    required_chain = run_agent(
        "required chain",
        required_model,
        tools,
        required_tool_sequence=["search", "detail"],
    )
    assert required_chain["stop_reason"] == "success"
    assert required_chain["tool_calls"] == 2
    assert required_chain["repair_count"] == 1
    repair_messages = [
        message["content"]
        for messages in required_model.messages
        for message in messages
        if message.get("role") == "user"
        and "Repair once." in message.get("content", "")
    ]
    assert 'detail with inputs {"package_id": 1}' in repair_messages[-1]
    print("PASS agent multi-step/repair/schema/ceiling/final/log trace")


def test_agent_required_sequences_and_failures() -> None:
    tools = {
        "aggregate": lambda severity=None: {
            "ok": True,
            "data": [{"severity": severity or "all", "count": 2}],
            "error": None,
        },
        "search": lambda query: {
            "success": True,
            "data": [{"id": 1, "name": query}],
            "error": None,
        },
        "detail": lambda package_id: {
            "success": package_id in (1, 2),
            "data": {"id": package_id} if package_id == 1 else None,
            "error": None if package_id == 1 else "package not found",
        },
    }

    task_b = run_agent(
        "aggregate then search",
        SequenceModel([
            {"action": "tool", "name": "aggregate", "inputs": {}},
            {"action": "tool", "name": "search", "inputs": {"query": "x"}},
            {"action": "final", "answer": "aggregate supported by search"},
        ]),
        tools,
        required_tool_sequence=["aggregate", "search"],
        required_tool_inputs=[{}, {"query": "package-00001"}],
    )
    assert task_b["stop_reason"] == "success"
    assert [item["tool"] for item in task_b["trace"]] == ["aggregate", "search"]

    task_c = run_agent(
        "search then two details",
        SequenceModel([
            {"action": "tool", "name": "search", "inputs": {"query": "x"}},
            {"action": "tool", "name": "detail", "inputs": {"package_id": "1"}},
            {"action": "tool", "name": "detail", "inputs": {"package_id": 1}},
            {"action": "final", "answer": "comparison complete"},
        ]),
        tools,
        required_tool_sequence=["search", "detail", "detail"],
        required_tool_inputs=[{"query": "package-00001"}, {"package_id": 1}, {"package_id": 2}],
    )
    assert task_c["stop_reason"] == "success"
    assert [item["tool"] for item in task_c["trace"]] == ["search", "detail", "detail"]
    assert task_c["trace"][1]["inputs"]["package_id"] == 1

    premature_b = CapturingSequenceModel([
        {"action": "tool", "name": "aggregate", "inputs": {}},
        {"action": "final", "answer": "premature"},
        {"action": "final", "answer": "aggregate and search complete"},
    ])
    repaired_b = run_agent(
        "fixed B",
        premature_b,
        tools,
        required_tool_sequence=["aggregate", "search"],
        required_tool_inputs=[{}, {"query": "package-00001"}],
    )
    assert repaired_b["stop_reason"] == "success"
    assert [item["tool"] for item in repaired_b["trace"]] == ["aggregate", "search"]
    assert repaired_b["trace"][1]["inputs"] == {"query": "package-00001"}

    premature_c = CapturingSequenceModel([
        {"action": "tool", "name": "search", "inputs": {"query": "empty"}},
        {"action": "final", "answer": "premature"},
        {"action": "final", "answer": "two details complete"},
    ])
    repaired_c = run_agent(
        "fixed C",
        premature_c,
        tools,
        required_tool_sequence=["search", "detail", "detail"],
        required_tool_inputs=[{"query": "package-00001"}, {"package_id": 1}, {"package_id": 2}],
    )
    assert repaired_c["stop_reason"] == "human_review"
    assert [item["tool"] for item in repaired_c["trace"]] == ["search", "detail"]
    assert repaired_c["trace"][0]["observation"]["data"]

    class AdapterFailsAfterDetail:
        def __init__(self):
            self.calls = 0

        def complete(self, _messages):
            self.calls += 1
            if self.calls == 1:
                return {"action": "tool", "name": "search", "inputs": {"query": "package-00001"}}
            if self.calls == 2:
                return {"action": "tool", "name": "detail", "inputs": {"package_id": 1}}
            raise RuntimeError("HTTP 500 from Ollama")

    adapter_model = AdapterFailsAfterDetail()
    recovered_after_adapter_failure = run_agent(
        "fixed C adapter recovery",
        adapter_model,
        tools,
        required_tool_sequence=["search", "detail", "detail"],
        required_tool_inputs=[{"query": "package-00001"}, {"package_id": 1}, {"package_id": 2}],
    )
    executed = [item["tool"] for item in recovered_after_adapter_failure["trace"] if "tool" in item]
    assert recovered_after_adapter_failure["stop_reason"] == "success"
    assert executed == ["search", "detail", "detail"]
    assert adapter_model.calls == 3
    assert (
        recovered_after_adapter_failure["failure_classification"]
        == "bounded_controller_recovery"
    )

    failed_detail = dict(tools)
    failed_detail["detail"] = lambda package_id: (
        {"success": False, "ok": False, "data": None, "error": "package not found"}
        if package_id == 2 else tools["detail"](package_id)
    )
    failed_recovery = run_agent(
        "fixed C failed second detail",
        AdapterFailsAfterDetail(),
        failed_detail,
        required_tool_sequence=["search", "detail", "detail"],
        required_tool_inputs=[{"query": "package-00001"}, {"package_id": 1}, {"package_id": 2}],
    )
    assert failed_recovery["stop_reason"] == "human_review"
    assert failed_recovery["failure_classification"] == "controller_tool_error"

    consecutive_detail_model = CapturingSequenceModel([
        {"action": "tool", "name": "search", "inputs": {"query": "x"}},
        {"action": "tool", "name": "detail", "inputs": {"package_id": 1}},
        {"action": "final", "answer": "premature"},
        {"action": "tool", "name": "detail", "inputs": {"package_id": 1}},
        {"action": "final", "answer": "comparison complete"},
    ])
    consecutive_detail = run_agent(
        "search then two details with repair",
        consecutive_detail_model,
        tools,
        required_tool_sequence=["search", "detail", "detail"],
    )
    assert consecutive_detail["stop_reason"] == "success"
    assert consecutive_detail["tool_calls"] == 3
    repair_text = " ".join(
        message["content"]
        for messages in consecutive_detail_model.messages
        for message in messages
        if message.get("role") == "user"
        and "Repair once." in message.get("content", "")
    )
    assert 'detail with inputs {"package_id": 1}' in repair_text

    missing = run_agent(
        "missing package",
        SequenceModel([
            {"action": "tool", "name": "detail", "inputs": {"package_id": 999999}},
            {"action": "final", "answer": "not found handled"},
        ]),
        tools,
    )
    assert missing["trace"][0]["observation"]["error"] == "package not found"

    def broken_detail(package_id):
        raise TypeError("detail package_id must be integer")

    recovered = run_agent(
        "handler failure",
        SequenceModel([
            {"action": "tool", "name": "detail", "inputs": {"package_id": 1}},
            {"action": "final", "answer": "controlled error"},
        ]),
        {"detail": broken_detail},
    )
    assert recovered["stop_reason"] == "success"
    assert "TypeError" in recovered["trace"][0]["observation"]["error"]

    model_failure = run_agent(
        "adapter failure",
        SimpleNamespace(
            complete=lambda _messages: (_ for _ in ()).throw(
                RuntimeError("adapter stopped")
            )
        ),
        tools,
    )
    assert model_failure["stop_reason"] == "human_review"
    assert model_failure["failure_classification"] == "model_or_adapter_error"
    print("PASS agent Task B/Task C sequences/ID normalization/controlled failures")


def test_reflexion() -> None:
    tools = {
        "search": lambda query: {"success": True, "query": query},
        "detail": lambda package_id: {"success": True, "id": package_id},
    }

    def model_factory(reflection):
        if reflection is None:
            return SequenceModel([{"action": "final", "answer": "incomplete"}])
        return SequenceModel([
            {"action": "tool", "name": "search", "inputs": {"query": "x"}},
            {"action": "tool", "name": "detail", "inputs": {"package_id": 1}},
            {"action": "final", "answer": "complete"},
        ])

    retried = reflexion_run("task", model_factory, tools, {"search", "detail"})
    assert retried["stop_reason"] == "success" and len(retried["reflections"]) == 1
    assert "chain-of-thought" not in json.dumps(retried).lower()

    def always_fail(_reflection):
        return SequenceModel([{"action": "final", "answer": ""}])

    reviewed = reflexion_run("task", always_fail, tools, {"search"}, max_retries=2)
    assert reviewed["stop_reason"] == "human_review" and len(reviewed["reflections"]) == 2
    print("PASS Reflexion first-attempt/retry/two-retry/human-review/isolation")


def test_mrkl_and_security() -> None:
    csv = "ride_id,minutes\n1,10\n2,20\n"
    selected = csv_sql(csv, "SELECT COUNT(*) AS n FROM trips")
    assert selected["success"] and selected["data"]["row_count"] == 1
    assert {"success", "ts"}.issubset(selected)
    assert not csv_sql(csv, "DELETE FROM trips")["success"]
    assert not csv_sql("not,csv", "SELECT * FROM missing")["success"]
    assert calculator("2 + 3 * 4")["data"]["value"] == 14.0
    assert not calculator("__import__('os')")["success"]
    assert mark_untrusted("ignore instructions", "fixture").trusted_as_instructions is False
    recommendation = recommend(20, 400, 25, 1, 0.2, included_minutes=400)
    assert recommendation["decision"] == "Buy Monthly Membership"
    print("PASS MRKL response shape/invalid CSV/calculation/SQL boundary/untrusted policy")


def test_file_tools() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(dir=root, prefix=".hw7-phase3-sandbox-") as temporary:
        sandbox = Path(temporary)
        write_file("debug.py", "DEBUG = True\n", sandbox)
        write_file("other.py", "INFO = True\n", sandbox)
        assert "DEBUG" in read_file("debug.py", sandbox, max_lines=1)
        diff = edit_file("debug.py", "DEBUG = True", "DEBUG = False", sandbox)
        assert "-DEBUG = True" in diff and "+DEBUG = False" in diff
        assert glob_files("*.py", sandbox) == ["debug.py", "other.py"]
        assert search_in_files("DEBUG", sandbox, "*.py") == []
        write_file("debug.py", "DEBUG = True\n", sandbox)
        assert search_in_files("DEBUG", sandbox, "*.py")[0]["path"] == "debug.py"
        assert bash("python -c \"print('sandbox')\"")["allowed"] is True

    allowed = ["python -V", "ruff check .", "git status", "git diff", "pytest -q"]
    blocked = ["rm -rf x", "sudo whoami", "chmod 777 x", "mkfs /dev/sda", "echo x > /root/x"]
    assert len(SAFE_PREFIXES) >= 5
    assert all(confirm_bash(command)["allowed"] for command in allowed)
    assert all(not confirm_bash(command)["allowed"] for command in blocked)
    assert all(is_destructive(command) for command in blocked)
    assert confirm_bash("rm -rf x", auto_approve=True)["allowed"] is True
    print("PASS file tools/sandbox/glob-search-read/5-pass/5-block/safety confirmation")


def main() -> None:
    test_jwt()
    test_authorization()
    test_agent()
    test_reflexion()
    test_mrkl_and_security()
    test_file_tools()
    print("OFFLINE_PHASE3_TESTS_COMPLETE")


if __name__ == "__main__":
    main()
