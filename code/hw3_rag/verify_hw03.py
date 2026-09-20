import json
from datetime import datetime, timezone
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPOSITORY_ROOT / "reports" / "hw03"
RAW_DIR = REPORT_DIR / "raw"
CORPUS_DIR = (
    REPOSITORY_ROOT
    / "data"
    / "hw03_corpus"
    / "selected_pypi"
)

VERIFICATION_PATH = REPORT_DIR / "verification.json"


def check_file(path: Path) -> tuple[bool, str]:
    """Check that a file exists and is not empty."""
    exists = path.exists() and path.is_file()
    non_empty = exists and path.stat().st_size > 0

    return (
        exists and non_empty,
        f"{path.relative_to(REPOSITORY_ROOT)} exists and is non-empty",
    )


def main() -> None:
    """Run basic HW3 integrity checks."""
    checks = []

    required_files = [
        REPORT_DIR / "SOURCES.md",
        REPORT_DIR / "CORPUS_MANIFEST.json",
        REPORT_DIR / "questions.yaml",
        REPORT_DIR / "METRICS.md",
        REPORT_DIR / "RUN_LOG.txt",
        REPORT_DIR / "screenshots" / "secure_cookie_header.png",
        REPORT_DIR / "screenshots" / "idle_timeout_redirect.png",
        RAW_DIR / "retrieval_results.jsonl",
        RAW_DIR / "retrieval_results.csv",
        RAW_DIR / "query_embeddings.jsonl",
        RAW_DIR / "chunking_stats.json",
        RAW_DIR / "metrics.json",
        RAW_DIR / "wrong_retrieval_candidates.json",
        REPOSITORY_ROOT
        / "code"
        / "web_application"
        / "main.py",
        REPOSITORY_ROOT
        / "code"
        / "web_application"
        / "routers"
        / "auth.py",
        REPOSITORY_ROOT
        / "code"
        / "web_application"
        / "templates"
        / "index.html",
        REPOSITORY_ROOT
        / "code"
        / "web_application"
        / "templates"
        / "login.html",
        REPOSITORY_ROOT
        / "code"
        / "web_application"
        / "templates"
        / "dashboard.html",
    ]

    for path in required_files:
        passed, message = check_file(path)
        checks.append(
            {
                "name": f"file:{path.name}",
                "passed": passed,
                "details": message,
            }
        )

    with (
        REPORT_DIR / "questions.yaml"
    ).open("r", encoding="utf-8") as file:
        questions_data = yaml.safe_load(file)

    questions = questions_data.get("questions", [])

    checks.append(
        {
            "name": "questions_count",
            "passed": len(questions) >= 5,
            "details": f"Found {len(questions)} questions.",
        }
    )

    with (
        REPORT_DIR / "CORPUS_MANIFEST.json"
    ).open("r", encoding="utf-8") as file:
        manifest = json.load(file)

    checks.append(
        {
            "name": "corpus_size",
            "passed": manifest["selected_total_bytes"] >= 200_000,
            "details": (
                f"Corpus contains "
                f"{manifest['selected_total_bytes']} bytes."
            ),
        }
    )

    checks.append(
        {
            "name": "corpus_document_count",
            "passed": manifest["selected_document_count"] >= 5,
            "details": (
                f"Manifest contains "
                f"{manifest['selected_document_count']} documents."
            ),
        }
    )

    result_lines = (
        RAW_DIR / "retrieval_results.jsonl"
    ).read_text(encoding="utf-8").splitlines()

    checks.append(
        {
            "name": "retrieval_row_count",
            "passed": len(result_lines) == 75,
            "details": (
                f"Found {len(result_lines)} retrieval rows; "
                "expected 75."
            ),
        }
    )

    with (
        RAW_DIR / "metrics.json"
    ).open("r", encoding="utf-8") as file:
        metrics = json.load(file)

    technique_names = {
        item["technique"]
        for item in metrics
    }

    expected_techniques = {
        "Token",
        "Semantic",
        "Sentence-window",
    }

    checks.append(
        {
            "name": "three_techniques",
            "passed": technique_names == expected_techniques,
            "details": (
                f"Found techniques: "
                f"{sorted(technique_names)}"
            ),
        }
    )

    with (
        RAW_DIR / "wrong_retrieval_candidates.json"
    ).open("r", encoding="utf-8") as file:
        wrong_candidates = json.load(file)

    checks.append(
        {
            "name": "incorrect_retrieval_evidence",
            "passed": len(wrong_candidates) >= 1,
            "details": (
                f"Found {len(wrong_candidates)} "
                "incorrect top-1 candidates."
            ),
        }
    )

    selected_documents = list(
        CORPUS_DIR.glob("*.json")
    )

    selected_documents = [
        path
        for path in selected_documents
        if path.name != "selection_summary.json"
    ]

    checks.append(
        {
            "name": "selected_corpus_files",
            "passed": len(selected_documents) == 69,
            "details": (
                f"Found {len(selected_documents)} "
                "selected JSON documents."
            ),
        }
    )

    passed = all(
        check["passed"]
        for check in checks
    )

    verification = {
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "passed": passed,
        "checks": checks,
    }

    with VERIFICATION_PATH.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            verification,
            file,
            indent=2,
        )

    for check in checks:
        status = "PASS" if check["passed"] else "FAIL"
        print(f"[{status}] {check['name']}: {check['details']}")

    print(f"\nOverall verification: {passed}")
    print(f"Output: {VERIFICATION_PATH}")

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()