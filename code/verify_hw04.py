from __future__ import annotations

import csv
import json
import os
import subprocess
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "reports" / "hw04"
RAW_DIR = REPORT_DIR / "raw"
BASE_URL = "http://127.0.0.1:8744"

required_files = [
    REPORT_DIR / "README.md",
    REPORT_DIR / "questions.yaml",
    REPORT_DIR / "METRICS.md",
    REPORT_DIR / "RUN_LOG.txt",
    REPORT_DIR / "AI_USE.md",
    REPORT_DIR / "report.pdf",
    RAW_DIR / "nplus1_requests.csv",
    RAW_DIR / "nplus1_summary.json",
    RAW_DIR / "index_explain_before.txt",
    RAW_DIR / "index_explain_after.txt",
    RAW_DIR / "retrieved_chunks.json",
    RAW_DIR / "rag_comparison.json",
    RAW_DIR / "k_sweep.json",
    RAW_DIR / "evaluation_table.csv",
    RAW_DIR / "k_sweep.csv",
]

checks = {}

for path in required_files:
    checks[f"exists:{path.relative_to(ROOT)}"] = path.exists()

metadata = {
    "assignment": "DATA 260 Homework 4",
    "sid4": "8844",
    "seed": 8844,
    "verify_seed": 268844,
    "port": 8744,
    "model": "qwen3:8b",
    "domain": "Open-source package vulnerabilities",
}

try:
    commit_hash = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
    ).strip()
except Exception:
    commit_hash = "unavailable"

try:
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"],
        cwd=ROOT,
        text=True,
    ).strip()
except Exception:
    branch = "unavailable"

metadata["commit_hash"] = commit_hash
metadata["branch"] = branch

with (RAW_DIR / "nplus1_requests.csv").open(
    newline="",
    encoding="utf-8-sig",
) as file:
    nplus_rows = list(csv.DictReader(file))

checks["nplus1_request_count_is_180"] = len(nplus_rows) == 180

comparison = json.loads(
    (RAW_DIR / "rag_comparison.json").read_text(encoding="utf-8")
)

checks["rag_comparison_count_is_18"] = len(comparison) == 18

sweep = json.loads(
    (RAW_DIR / "k_sweep.json").read_text(encoding="utf-8")
)

checks["k_sweep_count_is_3"] = len(sweep) == 3

question_ids = {
    row.get("question_id")
    for row in comparison
}

checks["six_question_ids_present"] = question_ids == {
    "q1", "q2", "q3", "q4", "q5", "q6"
}

refusal_phrase = (
    "I cannot answer this question from the provided documents"
)

checks["q5_q6_context_refusals_present"] = all(
    refusal_phrase in row.get("answer", "")
    for row in comparison
    if row.get("configuration") == "Context-RAG"
    and row.get("question_id") in {"q5", "q6"}
)

def get_json(opener, url, payload=None):
    data = None

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )

    with opener.open(request, timeout=15) as response:
        return response.status, json.loads(
            response.read().decode("utf-8")
        )

# Health check
try:
    status, body = get_json(
        urllib.request.build_opener(),
        f"{BASE_URL}/health",
    )
    checks["api_health_returns_200"] = status == 200
    checks["api_health_status_is_ok"] = body.get("status") == "ok"
except Exception:
    checks["api_health_returns_200"] = False
    checks["api_health_status_is_ok"] = False

# Confirm protected access rejects unauthenticated requests
try:
    urllib.request.urlopen(
        f"{BASE_URL}/api/vulnerability-reports",
        timeout=15,
    )
    checks["unauthenticated_reports_request_returns_401"] = False
except urllib.error.HTTPError as error:
    checks["unauthenticated_reports_request_returns_401"] = (
        error.code == 401
    )
except Exception:
    checks["unauthenticated_reports_request_returns_401"] = False

# Login and test both benchmark routes
cookie_jar = CookieJar()
authenticated_opener = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(cookie_jar)
)

admin_email = os.environ.get(
    "HW4_ADMIN_EMAIL",
    "admin@example.com",
)
admin_password = os.environ.get(
    "HW4_ADMIN_PASSWORD",
    "password",
)

try:
    login_status, login_body = get_json(
        authenticated_opener,
        f"{BASE_URL}/api/auth/login",
        {
            "email": admin_email,
            "password": admin_password,
        },
    )

    checks["login_returns_200"] = login_status == 200
    checks["login_returns_user"] = "user" in login_body

    for version in ("naive", "fixed"):
        for page_size in (10, 200):
            try:
                status, body = get_json(
                    authenticated_opener,
                    f"{BASE_URL}/api/benchmark/{version}"
                    f"?page_size={page_size}",
                )

                key = f"{version}_{page_size}"

                checks[f"{key}_returns_200"] = status == 200
                checks[f"{key}_returns_expected_version"] = (
                    body.get("version") == version
                )
                checks[f"{key}_returns_expected_count"] = (
                    body.get("count") == page_size
                    and len(body.get("items", [])) == page_size
                )
            except Exception:
                key = f"{version}_{page_size}"
                checks[f"{key}_returns_200"] = False
                checks[f"{key}_returns_expected_version"] = False
                checks[f"{key}_returns_expected_count"] = False

except Exception:
    checks["login_returns_200"] = False
    checks["login_returns_user"] = False

overall = all(checks.values())

result = {
    "metadata": metadata,
    "checks": checks,
    "overall_verification": overall,
}

(REPORT_DIR / "verification.json").write_text(
    json.dumps(result, indent=2),
    encoding="utf-8",
)

for name, passed in checks.items():
    print(f"{name}: {passed}")

print(f"Overall verification: {overall}")

if not overall:
    raise SystemExit(1)
