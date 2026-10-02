import json
import os
import sys
from typing import Any

import pymysql
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP


load_dotenv("code/web_application/.env")

mcp = FastMCP("s8844 Domain Server")


def result(ok: bool, data: Any = None, error: str | None = None) -> str:
    return json.dumps(
        {
            "ok": ok,
            "data": data,
            "error": error,
        },
        default=str,
    )


def connection():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        cursorclass=pymysql.cursors.DictCursor,
    )


@mcp.tool()
def search(query: str, limit: int = 10) -> str:
    """Search packages by name, ecosystem, or package code."""
    if not query.strip():
        return result(False, error="query is required")

    if limit < 1 or limit > 50:
        return result(False, error="limit must be between 1 and 50")

    try:
        with connection() as db:
            with db.cursor() as cursor:
                pattern = f"%{query.strip()}%"
                cursor.execute(
                    """
                    SELECT id, name, ecosystem, package_code,
                           created_at, updated_at
                    FROM packages
                    WHERE name LIKE %s
                       OR ecosystem LIKE %s
                       OR package_code LIKE %s
                    ORDER BY id
                    LIMIT %s
                    """,
                    (pattern, pattern, pattern, limit),
                )
                rows = cursor.fetchall()

        return result(True, data=rows)

    except Exception as exc:
        print(f"search error: {exc}", file=sys.stderr)
        return result(False, error="storage operation failed")


@mcp.tool()
def detail(package_id: int) -> str:
    """Return one package and its vulnerability reports."""
    if package_id < 1:
        return result(False, error="package_id must be positive")

    try:
        with connection() as db:
            with db.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, name, ecosystem, package_code,
                           created_at, updated_at
                    FROM packages
                    WHERE id = %s
                    """,
                    (package_id,),
                )
                package = cursor.fetchone()

                if package is None:
                    return result(False, error="package not found")

                cursor.execute(
                    """
                    SELECT id, vulnerability_id, severity,
                           affected_versions_count, submission_date
                    FROM vulnerability_reports
                    WHERE package_id = %s
                    ORDER BY id
                    """,
                    (package_id,),
                )
                package["reports"] = cursor.fetchall()

        return result(True, data=package)

    except Exception as exc:
        print(f"detail error: {exc}", file=sys.stderr)
        return result(False, error="storage operation failed")


@mcp.tool()
def aggregate(severity: str | None = None) -> str:
    """Count vulnerability reports by severity."""
    allowed = {"Critical", "High", "Medium", "Low"}

    if severity is not None and severity not in allowed:
        return result(
            False,
            error="severity must be Critical, High, Medium, or Low",
        )

    try:
        with connection() as db:
            with db.cursor() as cursor:
                if severity is None:
                    cursor.execute(
                        """
                        SELECT severity, COUNT(*) AS report_count
                        FROM vulnerability_reports
                        GROUP BY severity
                        ORDER BY severity
                        """
                    )
                else:
                    cursor.execute(
                        """
                        SELECT severity, COUNT(*) AS report_count
                        FROM vulnerability_reports
                        WHERE severity = %s
                        GROUP BY severity
                        """,
                        (severity,),
                    )

                rows = cursor.fetchall()

        return result(True, data=rows)

    except Exception as exc:
        print(f"aggregate error: {exc}", file=sys.stderr)
        return result(False, error="storage operation failed")


if __name__ == "__main__":
    mcp.run(transport="stdio")