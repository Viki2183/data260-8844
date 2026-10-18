"""Read-only final verification for DATA 260 Homework 6.

Running this script checks the repository, public GET endpoints, MongoDB
metadata, and HW6 evidence.  It never sends POST requests, calls a model, or
writes to MongoDB.  Its only output file is reports/hw06/verification.json.
"""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "reports" / "hw06" / "raw"
VERIFICATION_PATH = ROOT / "reports" / "hw06" / "verification.json"
BASE_URL = "http://127.0.0.1:8744"
EXPECTED_BRANCH = "hw6-development"
DATABASE_NAME = "s8844_doc"

REQUIRED_APPLICATION_FILES = [
    "code/web_application/mongo_database_hw6.py",
    "code/web_application/mongo_repositories_hw6.py",
    "code/web_application/mongo_setup_hw6.py",
    "code/web_application/schemas_hw6.py",
    "code/web_application/documents_hw6.py",
    "code/web_application/memory_schemas_hw6.py",
    "code/web_application/memory_repositories_hw6.py",
    "code/web_application/memory_setup_hw6.py",
    "code/web_application/embedding_service_hw6.py",
    "code/web_application/memory_logic_hw6.py",
    "code/web_application/memory_model_hw6.py",
    "code/web_application/memory_service_hw6.py",
    "code/web_application/memory_routes_hw6.py",
]

REQUIRED_EVIDENCE_FILES = [
    "document_crud_results.json",
    "chat_turn_01.json",
    "chat_turn_02.json",
    "chat_turn_03.json",
    "chat_turn_04.json",
    "chat_turn_04_server_completion.json",
    "chat_turn_05.json",
    "chat_turn_06.json",
    "chat_turn_07.json",
    "chat_turn_08.json",
    "memory_commands_results.json",
    "memory_commands_live.json",
    "short_term_comparison.csv",
    "short_term_comparison.jsonl",
    "compact_lifetime_step_01.json",
    "compact_lifetime_step_02.json",
    "compact_lifetime_step_03.json",
]

EXPECTED_INDEXES = {
    "documents": {
        "created_at_desc",
        "severity_asc",
        "status_asc",
        "document_date_desc",
    },
    "messages": {
        "messages_user_session_created_desc",
        "messages_user_created_desc",
        "messages_role_asc",
    },
    "summaries": {
        "summaries_user_scope_created_desc",
        "summaries_user_session_created_desc",
    },
    "episodes": {
        "episodes_user_created_desc",
        "episodes_user_importance_desc",
    },
}


@dataclass
class Check:
    """One human-readable PASS, FAIL, or WARNING verification result."""

    name: str
    status: str
    details: Any


def check(results: list[Check], name: str, passed: bool, details: Any) -> None:
    """Append a strict check result without stopping independent checks."""

    results.append(Check(name, "PASS" if passed else "FAIL", details))


def warning(results: list[Check], name: str, details: Any) -> None:
    """Record an observation that needs attention but is not a failed check."""

    results.append(Check(name, "WARNING", details))


def run_git(*arguments: str) -> str:
    """Run a read-only Git command and return text without changing the repo."""

    completed = subprocess.run(
        ["git", "-c", "safe.directory=C:/Projects/data260-8844", *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip()


def get_json(path: str) -> tuple[int | None, Any, str | None]:
    """Perform one read-only HTTP GET and preserve unavailable results honestly."""

    try:
        with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        return exc.code, None, f"HTTPError: {exc.reason}"
    except Exception as exc:  # network failures are reported, not hidden
        return None, None, f"{type(exc).__name__}: {exc}"


def load_json(path: Path) -> Any | None:
    """Load an evidence file for inspection without altering it."""

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def contains_text(value: Any, phrase: str) -> bool:
    """Search nested evidence values without assuming one fixed JSON shape."""

    if isinstance(value, str):
        return phrase.lower() in value.lower()
    if isinstance(value, dict):
        return any(contains_text(item, phrase) for item in value.values())
    if isinstance(value, list):
        return any(contains_text(item, phrase) for item in value)
    return False


def evidence_statuses(value: Any) -> list[Any]:
    """Collect nested status values for honest evidence-content checks."""

    found: list[Any] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"http_status", "status"}:
                found.append(item)
            found.extend(evidence_statuses(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(evidence_statuses(item))
    return found


def verify_git(results: list[Check], warnings: list[str]) -> dict[str, Any]:
    """Verify branch, commit, tags, and report the existing worktree status."""

    branch = run_git("branch", "--show-current")
    commit = run_git("rev-parse", "HEAD")
    status_lines = run_git("status", "--short").splitlines()
    tags = set(run_git("tag", "--list").splitlines())
    check(results, "git.branch", branch == EXPECTED_BRANCH, branch)
    check(results, "git.tags", {f"hw{i}" for i in range(1, 6)} <= tags, sorted(tags))
    warning(warnings, "git.working_tree", {"status": "reported", "entries": status_lines})
    return {"branch": branch, "commit": commit, "working_tree": status_lines, "tags": sorted(tags)}


def verify_files(results: list[Check]) -> dict[str, Any]:
    """Check required source, documentation, evidence, and directory paths."""

    required = ["MEMORY.md", "AGENT.md", "requirements.txt", *REQUIRED_APPLICATION_FILES, "reports/hw06/README.md", "reports/hw06/memory_probes.yaml"]
    for relative in required:
        check(results, f"file:{relative}", (ROOT / relative).is_file(), relative)
    for relative in ["reports/hw06/raw", "reports/hw06/screenshots"]:
        check(results, f"directory:{relative}", (ROOT / relative).is_dir(), relative)
    missing = [name for name in REQUIRED_EVIDENCE_FILES if not (RAW / name).is_file()]
    check(results, "evidence.required_files", not missing, {"missing": missing})
    return {"required_evidence": REQUIRED_EVIDENCE_FILES, "missing": missing}


def verify_http(results: list[Check]) -> dict[str, Any]:
    """Check only safe GET endpoints and OpenAPI route declarations."""

    health_status, health_body, health_error = get_json("/health")
    openapi_status, openapi, openapi_error = get_json("/openapi.json")
    check(results, "http.health", health_status == 200, {"status": health_status, "body": health_body, "error": health_error})
    check(results, "http.openapi", openapi_status == 200, {"status": openapi_status, "error": openapi_error})
    paths = openapi.get("paths", {}) if isinstance(openapi, dict) else {}
    route_expectations = {
        "/api/documents": {"post", "get"},
        "/api/documents/{document_id}": {"get", "put", "delete"},
        "/api/chat": {"post"},
        "/api/memory/{user_id}": {"get"},
        "/api/aggregate/{user_id}": {"get"},
    }
    for path, methods in route_expectations.items():
        actual = {method.lower() for method in paths.get(path, {})}
        check(results, f"http.route:{path}", methods <= actual, {"expected": sorted(methods), "actual": sorted(actual)})
    return {"health": {"status": health_status, "body": health_body}, "openapi_status": openapi_status, "paths": {path: sorted({m.lower() for m in paths.get(path, {})}) for path in route_expectations}}


def verify_mongodb(results: list[Check]) -> dict[str, Any]:
    """Inspect MongoDB collections, validators, indexes, and evidence counts read-only."""

    client = MongoClient("mongodb://127.0.0.1:27017", serverSelectionTimeoutMS=3000)
    try:
        client.admin.command("ping")
        db = client[DATABASE_NAME]
        collections = set(db.list_collection_names())
        for name in EXPECTED_INDEXES:
            check(results, f"mongo.collection:{name}", name in collections, name)
        validator_summary: dict[str, Any] = {}
        index_summary: dict[str, Any] = {}
        for name, expected_indexes in EXPECTED_INDEXES.items():
            if name not in collections:
                continue
            options = db[name].options()
            validator = options.get("validator", {})
            check(results, f"mongo.validator:{name}", "$jsonSchema" in validator, sorted(validator))
            actual_indexes = {item["name"] for item in db[name].list_indexes()}
            check(results, f"mongo.indexes:{name}", expected_indexes <= actual_indexes, sorted(actual_indexes))
            validator_summary[name] = {"validationLevel": options.get("validationLevel"), "validationAction": options.get("validationAction"), "has_jsonSchema": "$jsonSchema" in validator}
            index_summary[name] = sorted(actual_indexes)
        counts = {name: db[name].count_documents({}) for name in EXPECTED_INDEXES}
        check(results, "mongo.documents_count", counts.get("documents", 0) >= 1, counts.get("documents"))
        check(results, "mongo.messages_count", counts.get("messages", 0) >= 1, counts.get("messages"))
        session_summary_count = db.summaries.count_documents({"scope": "session"})
        lifetime_count = db.summaries.count_documents({"scope": "user", "session_id": None})
        check(results, "mongo.session_summaries", session_summary_count >= 1, session_summary_count)
        check(results, "mongo.lifetime_summaries", lifetime_count >= 1, lifetime_count)
        check(results, "mongo.episodic_facts", counts.get("episodes", 0) >= 1, counts.get("episodes"))
        return {"database": DATABASE_NAME, "collections": sorted(collections), "counts": counts, "validators": validator_summary, "indexes": index_summary, "session_summary_count": session_summary_count, "lifetime_summary_count": lifetime_count}
    finally:
        client.close()


def verify_evidence(results: list[Check], warnings: list[str]) -> dict[str, Any]:
    """Check recorded evidence content without treating missing measurements as success."""

    loaded = {name: load_json(RAW / name) for name in REQUIRED_EVIDENCE_FILES if name.endswith(".json")}
    crud = loaded.get("document_crud_results.json")
    # CRUD evidence records its HTTP outcomes under actual_status_code inside
    # the tests list.  Read that real schema and require every required case.
    crud_tests = crud.get("tests", []) if isinstance(crud, dict) else []
    crud_statuses = [item.get("actual_status_code") for item in crud_tests if isinstance(item, dict)]
    required_crud_statuses = {201, 200, 204, 400, 404, 422}
    check(
        results,
        "evidence.crud_cases",
        isinstance(crud, dict) and required_crud_statuses <= set(crud_statuses),
        {"recorded_actual_status_codes": crud_statuses, "required": sorted(required_crud_statuses)},
    )
    session4 = [loaded.get(name) for name in ["chat_turn_04_server_completion.json", "chat_turn_05.json"]]
    check(results, "evidence.episodic_retrieval", any(item is not None and contains_text(item, "distributed systems") for item in session4), "session-4 evidence")
    live = loaded.get("memory_commands_live.json")
    check(results, "evidence.live_commands_200", live is not None and all(value == 200 for value in evidence_statuses(live) if isinstance(value, int)), evidence_statuses(live))
    windows = set()
    jsonl_path = RAW / "short_term_comparison.jsonl"
    if jsonl_path.is_file():
        try:
            windows = {json.loads(line)["short_term_n"] for line in jsonl_path.read_text(encoding="utf-8").splitlines() if line.strip()}
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            windows = set()
    check(results, "evidence.short_term_windows", windows == {4, 12, 30}, sorted(windows))
    lifetime = loaded.get("compact_lifetime_step_03.json")
    lifetime_pass = isinstance(lifetime, dict) and lifetime.get("counts_before", {}).get("summaries") == 5 and lifetime.get("counts_after", {}).get("lifetime_summaries") == 1
    check(results, "evidence.lifetime_threshold", lifetime_pass, lifetime.get("requirement_result") if isinstance(lifetime, dict) else None)
    stale = loaded.get("memory_commands_results.json")
    warning(warnings, "evidence.stale_process", "The stale-process command artifact is preserved and non-authoritative.")
    live_path = RAW / "memory_commands_live.json"
    stale_path = RAW / "memory_commands_results.json"
    stale_process_text = stale.get("server_process_used", "") if isinstance(stale, dict) else ""
    identifies_old_process = "21012" in str(stale_process_text) or "old" in str(stale_process_text).lower()
    stale_check_details = {
        "stale_file_exists": stale_path.is_file(),
        "server_process_used": stale_process_text,
        "identifies_old_process": identifies_old_process,
        "live_file_exists": live_path.is_file(),
        "separate_paths": stale_path.resolve() != live_path.resolve(),
    }
    check(
        results,
        "evidence.stale_label",
        isinstance(stale, dict)
        and stale_path.is_file()
        and identifies_old_process
        and live_path.is_file()
        and stale_path.resolve() != live_path.resolve(),
        stale_check_details,
    )
    warning(warnings, "evidence.measurements", "Unavailable measurements remain unavailable; the verifier does not convert them into success.")
    return {"crud_statuses": crud_statuses, "short_term_windows": sorted(windows), "lifetime_threshold": lifetime_pass}


def run_verification() -> dict[str, Any]:
    """Collect all independent checks and return the report structure."""

    results: list[Check] = []
    warnings: list[Check] = []
    # The warning list uses the same Check shape so the final JSON is uniform.
    git_info = verify_git(results, [])
    files = verify_files(results)
    http = verify_http(results)
    mongo = verify_mongodb(results)
    evidence = verify_evidence(results, [])
    warning_messages = [item.details for item in warnings]
    failures = [item for item in results if item.status == "FAIL"]
    return {
        "homework": "DATA260 HW6",
        "student": "Vrishin KunnathamParambath",
        "sid4": "8844",
        "branch_expected": EXPECTED_BRANCH,
        "port": 8744,
        "mongo_database": DATABASE_NAME,
        "model": "qwen3:8b",
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "seed": 8844,
        "verify_seed": 268844,
        "hardware": "Intel Core i7-10750H, approximately 16 GB RAM",
        "git": git_info,
        "route_checks": http,
        "crud_checks": {"evidence_file": "reports/hw06/raw/document_crud_results.json"},
        "memory_checks": mongo,
        "short_term_experiment_checks": evidence,
        "command_checks": {"live_evidence": "reports/hw06/raw/memory_commands_live.json", "stale_evidence_non_authoritative": True},
        "lifetime_summary_checks": evidence.get("lifetime_threshold"),
        "report_file_checks": files,
        "checks": [{"name": item.name, "status": item.status, "details": item.details} for item in results],
        "warnings": warning_messages,
        "overall": "FAIL" if failures else "PASS",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    """Run checks, write verification.json, validate it, and print a concise summary."""

    report = run_verification()
    VERIFICATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    VERIFICATION_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    json.loads(VERIFICATION_PATH.read_text(encoding="utf-8"))
    passed = sum(item["status"] == "PASS" for item in report["checks"])
    failed = sum(item["status"] == "FAIL" for item in report["checks"])
    print(f"HW6 verification: {report['overall']} (PASS={passed}, FAIL={failed}, WARNING={len(report['warnings'])})")
    print(f"Report written: {VERIFICATION_PATH}")


if __name__ == "__main__":
    main()
