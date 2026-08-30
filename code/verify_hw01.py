import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

REQUIRED_FILES = [
    "code/web_application/index.html",
    "code/web_application/app.js",
    "code/Dockerfile",
    "code/agents_demo.py",
    "code/run_nondeterminism.py",
    "code/calculate_metrics.py",
    "code/hw1_client.py",
    "code/verify_hw01.py",
    "code/__init__.py",
    "AGENT.md",
    "README.md",
    "requirements.txt",
    "src/__init__.py",
    "src/model_client.py",
    "reports/hw01/cases/nondeterminism_input.json",
    "reports/hw01/raw/nondeterminism_results.json",
    "reports/hw01/raw/nondeterminism_results.csv",
    "reports/hw01/raw/nondeterminism_metrics.json",
    "reports/hw01/raw/client_conversation.json",
    "reports/hw01/RUN_LOG.txt",
    "reports/hw01/METRICS.md",
    "reports/hw01/AI_USE.md",
]


def add_check(
    checks: list[dict],
    name: str,
    passed: bool,
    details: str,
) -> None:
    checks.append({
        "name": name,
        "passed": passed,
        "details": details,
    })


def main() -> None:
    checks: list[dict] = []

    missing_files = [
        filename
        for filename in REQUIRED_FILES
        if not (ROOT / filename).exists()
    ]

    add_check(
        checks,
        "required_files",
        not missing_files,
        (
            "All required files are present."
            if not missing_files
            else f"Missing: {missing_files}"
        ),
    )

    html = (ROOT / "code/web_application/index.html").read_text(
        encoding="utf-8"
    )

    html_requirements = [
        "<h1>",
        "autofocus",
        'type="email"',
        "<textarea",
        'type="checkbox"',
        "I agree to the terms and conditions.",
        '<script src="app.js"></script>',
    ]

    missing_html = [
        item
        for item in html_requirements
        if item not in html
    ]

    add_check(
        checks,
        "html_requirements",
        not missing_html,
        (
            "HTML requirements are present."
            if not missing_html
            else f"Missing HTML elements: {missing_html}"
        ),
    )

    javascript = (
    ROOT / "code/web_application/app.js"
).read_text(
        encoding="utf-8"
    )

    js_requirements = [
        "=>",
        "JSON.stringify",
        "JSON.parse",
        "submissionDate",
        "...parsedObject",
        "submissionCounter",
        "description.length <= 25",
        "termsAccepted",
    ]

    missing_js = [
        item
        for item in js_requirements
        if item not in javascript
    ]

    add_check(
        checks,
        "javascript_requirements",
        not missing_js,
        (
            "JavaScript requirements are present."
            if not missing_js
            else f"Missing JavaScript items: {missing_js}"
        ),
    )

    results_path = (
        ROOT
        / "reports/hw01/raw/nondeterminism_results.json"
    )

    results = json.loads(
        results_path.read_text(encoding="utf-8")
    )

    temperature_07 = [
        result
        for result in results
        if float(result["temperature"]) == 0.7
    ]

    temperature_00 = [
        result
        for result in results
        if float(result["temperature"]) == 0.0
    ]

    add_check(
        checks,
        "nondeterminism_runs",
        (
            len(results) == 40
            and len(temperature_07) == 20
            and len(temperature_00) == 20
        ),
        (
            f"Total={len(results)}, "
            f"temperature_0.7={len(temperature_07)}, "
            f"temperature_0.0={len(temperature_00)}"
        ),
    )

    valid_agent_results = all(
        len(result.get("tags", [])) == 3
        and len(
            result.get("summary", "").split()
        ) <= 25
        for result in results
    )

    add_check(
        checks,
        "agent_output_schema",
        valid_agent_results,
        (
            "All runs contain three tags and summaries "
            "of at most 25 words."
        ),
    )

    conversation_path = (
        ROOT
        / "reports/hw01/raw/client_conversation.json"
    )

    conversation = json.loads(
        conversation_path.read_text(encoding="utf-8")
    )

    snapshots = conversation.get(
        "stats_snapshots",
        []
    )

    snapshot_turns = [
        snapshot.get("after_turn")
        for snapshot in snapshots
    ]

    add_check(
        checks,
        "client_stats_snapshots",
        3 in snapshot_turns and 5 in snapshot_turns,
        f"Recorded /stats after turns: {snapshot_turns}",
    )

    syntax_command = [
        sys.executable,
        "-m",
        "py_compile",
        "code/agents_demo.py",
        "code/run_nondeterminism.py",
        "code/calculate_metrics.py",
        "code/hw1_client.py",
        "code/verify_hw01.py",
        "src/model_client.py",
    ]

    syntax_result = subprocess.run(
        syntax_command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    add_check(
        checks,
        "python_syntax",
        syntax_result.returncode == 0,
        (
            "All Python files compiled successfully."
            if syntax_result.returncode == 0
            else syntax_result.stderr
        ),
    )

    docker_result = subprocess.run(
        [
            "docker",
            "image",
            "inspect",
            "data260-8844-hw1",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    add_check(
        checks,
        "docker_image",
        docker_result.returncode == 0,
        (
            "Docker image data260-8844-hw1 exists."
            if docker_result.returncode == 0
            else "Docker image was not found."
        ),
    )

    all_passed = all(
        check["passed"]
        for check in checks
    )

    verification = {
        "student": "Vrishin Dharmesh Kunnatham Parambath",
        "sid4": 8844,
        "port_base": 8744,
        "prefix": "s8844",
        "verify_seed": 268844,
        "all_passed": all_passed,
        "checks": checks,
    }

    output_path = (
        ROOT / "reports/hw01/verification.json"
    )

    output_path.write_text(
        json.dumps(verification, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(verification, indent=2))
    print(f"\nCreated {output_path}")

    if not all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()