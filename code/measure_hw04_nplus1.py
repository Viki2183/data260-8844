import csv
import json
import math
import time
from pathlib import Path

import requests

BASE_URL = "http://127.0.0.1:8744"
OUTPUT_DIR = Path("reports/hw04/raw")
RAW_FILE = OUTPUT_DIR / "nplus1_requests.csv"
SUMMARY_FILE = OUTPUT_DIR / "nplus1_summary.json"

versions = ["naive", "fixed"]
page_sizes = [10, 50, 200]
repeats = 30
rows = []


def percentile(values, percent):
    ordered = sorted(values)
    position = math.ceil(percent / 100 * len(ordered)) - 1
    return ordered[max(position, 0)]


session = requests.Session()

login = session.post(
    f"{BASE_URL}/api/auth/login",
    json={"email": "admin@example.com", "password": "password"},
    timeout=30,
)
login.raise_for_status()

for version in versions:
    for page_size in page_sizes:
        for repetition in range(1, repeats + 1):
            start = time.perf_counter()

            response = session.get(
                f"{BASE_URL}/api/benchmark/{version}",
                params={"page_size": page_size},
                timeout=60,
            )

            latency_ms = (time.perf_counter() - start) * 1000
            response.raise_for_status()

            body = response.json()

            rows.append(
                {
                    "version": version,
                    "page_size": page_size,
                    "repetition": repetition,
                    "status_code": response.status_code,
                    "sql_statements": int(
                        response.headers["X-SQL-Statements"]
                    ),
                    "returned_rows": body["count"],
                    "latency_ms": round(latency_ms, 3),
                }
            )

            print(
                version,
                page_size,
                repetition,
                rows[-1]["sql_statements"],
                rows[-1]["latency_ms"],
            )

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with RAW_FILE.open("w", newline="", encoding="utf-8") as file:
    writer = csv.DictWriter(file, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

summary = {}

for version in versions:
    summary[version] = {}

    for page_size in page_sizes:
        selected = [
            row
            for row in rows
            if row["version"] == version
            and row["page_size"] == page_size
        ]

        latencies = [row["latency_ms"] for row in selected]
        sql_counts = [row["sql_statements"] for row in selected]

        summary[version][str(page_size)] = {
            "requests": len(selected),
            "sql_statements": {
                "min": min(sql_counts),
                "max": max(sql_counts),
                "mean": round(sum(sql_counts) / len(sql_counts), 3),
            },
            "latency_ms": {
                "p50": round(percentile(latencies, 50), 3),
                "p95": round(percentile(latencies, 95), 3),
                "p99": round(percentile(latencies, 99), 3),
            },
        }

SUMMARY_FILE.write_text(
    json.dumps(summary, indent=2),
    encoding="utf-8",
)

print(f"Raw requests written to: {RAW_FILE}")
print(f"Summary written to: {SUMMARY_FILE}")
print(f"Total requests: {len(rows)}")
