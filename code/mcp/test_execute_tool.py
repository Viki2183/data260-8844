import json

from execute_tool import execute_tool


def fake_search(query="", limit=10):
    if not query.strip():
        return json.dumps({
            "ok": False,
            "data": None,
            "error": "query is required",
        })

    return json.dumps({
        "ok": True,
        "data": [{"id": 1, "name": "fixture-package"}],
        "error": None,
    })


def fake_detail(package_id):
    if package_id < 1:
        return json.dumps({
            "ok": False,
            "data": None,
            "error": "package_id must be positive",
        })

    return json.dumps({
        "ok": True,
        "data": {"id": package_id, "name": "fixture-package"},
        "error": None,
    })


def fake_aggregate(severity=None):
    allowed = {"Critical", "High", "Medium", "Low"}

    if severity is not None and severity not in allowed:
        return json.dumps({
            "ok": False,
            "data": None,
            "error": "invalid severity",
        })

    return json.dumps({
        "ok": True,
        "data": [{"severity": "Medium", "report_count": 3}],
        "error": None,
    })


HANDLERS = {
    "search": fake_search,
    "detail": fake_detail,
    "aggregate": fake_aggregate,
}


def check(name, condition):
    if condition:
        print(f"PASS {name}")
        return True

    print(f"FAIL {name}")
    return False


def main():
    tests = [
        (
            "search valid",
            json.loads(
                execute_tool(
                    "search",
                    {"query": "fixture"},
                    HANDLERS,
                )
            )["ok"],
        ),
        (
            "search invalid",
            not json.loads(
                execute_tool(
                    "search",
                    {"query": ""},
                    HANDLERS,
                )
            )["ok"],
        ),
        (
            "detail valid",
            json.loads(
                execute_tool(
                    "detail",
                    {"package_id": 1},
                    HANDLERS,
                )
            )["ok"],
        ),
        (
            "detail invalid",
            not json.loads(
                execute_tool(
                    "detail",
                    {"package_id": 0},
                    HANDLERS,
                )
            )["ok"],
        ),
        (
            "aggregate valid",
            json.loads(
                execute_tool(
                    "aggregate",
                    {"severity": "Medium"},
                    HANDLERS,
                )
            )["ok"],
        ),
        (
            "aggregate invalid",
            not json.loads(
                execute_tool(
                    "aggregate",
                    {"severity": "Extreme"},
                    HANDLERS,
                )
            )["ok"],
        ),
        (
            "unknown tool rejected",
            not json.loads(
                execute_tool(
                    "missing_tool",
                    {},
                    HANDLERS,
                )
            )["ok"],
        ),
    ]

    passed = sum(check(name, result) for name, result in tests)

    print(f"\nSUMMARY: {passed}/{len(tests)} tests passed")

    if passed != len(tests):
        raise SystemExit(1)


if __name__ == "__main__":
    main()