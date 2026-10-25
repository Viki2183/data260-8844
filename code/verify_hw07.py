"""Offline HW7 smoke verifier; writes verification.json only when invoked."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from test_hw07_offline import run

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    checks = []
    try:
        passed = run()
        checks = [{"name": name, "passed": True} for name in passed]
        overall = True
    except Exception as exc:
        checks.append({"name": type(exc).__name__, "passed": False})
        overall = False
    payload = {
        "homework": 7,
        "sid4": 8844,
        "commit_hash": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip(),
        "model_configuration": {
            "model": "qwen3:8b",
            "temperature": 0.0,
            "mode": "offline smoke test",
        },
        "seed": 8844,
        "verify_seed": 268844,
        "checks": checks,
        "overall_pass": overall,
    }
    output = ROOT / "reports" / "hw07" / "verification.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
