"""Smoke tests for DATA 260 Homework 2."""

import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPOSITORY_ROOT / "reports" / "hw02"
VERIFICATION_PATH = REPORTS_DIR / "verification.json"

PORT_BASE = 8744
MODEL = "qwen3:8b"
SEED = 8844
VERIFY_SEED = 268844


def utc_timestamp() -> str:
    """Return the current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def get_commit_hash() -> str:
    """Read the current Git commit hash."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout.strip()


def check_api() -> dict:
    """Check that the FastAPI container responds on PORT_BASE."""
    url = (
        f"http://127.0.0.1:{PORT_BASE}"
        "/api/vulnerability-reports"
    )

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))

        passed = (
            response.status == 200
            and isinstance(body, list)
            and len(body) >= 2
        )

        return {
            "name": "FastAPI API response",
            "passed": passed,
            "details": (
                f"HTTP {response.status}; "
                f"received {len(body)} reports"
            ),
        }

    except Exception as error:
        return {
            "name": "FastAPI API response",
            "passed": False,
            "details": str(error),
        }


def check_graph() -> dict:
    """Check that the LangGraph script finishes within a timeout."""
    command = [
        sys.executable,
        str(REPOSITORY_ROOT / "code" / "hw2_graph.py"),
        "--title",
        "Smoke Test Vulnerability",
        "--content",
        (
            "A security issue may allow unauthorized users "
            "to access protected resources."
        ),
        "--email",
        "security@example.com",
        "--model",
        MODEL,
        "--temperature",
        "0.0",
        "--max-turns",
        "3",
        "--strict",
    ]

    try:
        result = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )

        output = result.stdout + result.stderr
        passed = (
            result.returncode == 0
            and "GRAPH RESULT" in output
        )

        return {
            "name": "LangGraph smoke test",
            "passed": passed,
            "details": (
                f"Return code {result.returncode}; "
                "GRAPH RESULT found"
                if passed
                else "Graph did not finish with GRAPH RESULT"
            ),
        }

    except subprocess.TimeoutExpired:
        return {
            "name": "LangGraph smoke test",
            "passed": False,
            "details": "Graph exceeded the 600-second timeout.",
        }

    except Exception as error:
        return {
            "name": "LangGraph smoke test",
            "passed": False,
            "details": str(error),
        }


def check_required_files() -> dict:
    """Check that the required HW2 files exist."""
    required_files = [
        REPOSITORY_ROOT / "code" / "hw2_graph.py",
        REPOSITORY_ROOT / "code" / "run_hw02_experiments.py",
        REPOSITORY_ROOT / "code" / "verify_hw02.py",
        REPOSITORY_ROOT / "code" / "web_application" / "main.py",
        REPOSITORY_ROOT / "code" / "web_application" / "index.html",
        REPOSITORY_ROOT / "code" / "web_application" / "app.js",
        REPOSITORY_ROOT / "code" / "web_application" / "styles.css",
        REPORTS_DIR / "cases" / "schema_input.json",
        REPORTS_DIR / "cases" / "adversarial_input.json",
        REPORTS_DIR / "raw" / "experiment_summary.json",
        REPORTS_DIR / "METRICS.md",
        REPORTS_DIR / "AI_USE.md",
        REPORTS_DIR / "RUN_LOG.txt",
    ]

    missing_files = [
        str(path.relative_to(REPOSITORY_ROOT))
        for path in required_files
        if not path.exists()
    ]

    return {
        "name": "Required HW2 files",
        "passed": not missing_files,
        "details": (
            "All required files exist."
            if not missing_files
            else f"Missing files: {missing_files}"
        ),
    }


def main() -> None:
    """Run all HW2 smoke tests and write verification.json."""
    checks = [
        check_required_files(),
        check_api(),
        check_graph(),
    ]

    verification = {
        "homework": "DATA 260 Homework 2",
        "sid4": 8844,
        "port_base": PORT_BASE,
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "model": MODEL,
        "timestamp_utc": utc_timestamp(),
        "commit_hash": get_commit_hash(),
        "checks": checks,
        "all_passed": all(
            check["passed"] for check in checks
        ),
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with VERIFICATION_PATH.open("w", encoding="utf-8") as file:
        json.dump(verification, file, indent=2)

    print(json.dumps(verification, indent=2))

    if not verification["all_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()