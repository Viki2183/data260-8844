"""Pure-function MRKL tools for the HW7 public bike-share exercise."""

from __future__ import annotations

import ast
import csv
import hashlib
import io
import re
import sqlite3
import urllib.request
from datetime import datetime, timezone
from typing import Any


def _result(
    success: bool,
    data: Any = None,
    error: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {"success": success}
    if data is not None:
        value["data"] = data
    if error:
        value["error"] = error
    if source:
        value["source"] = source
    value["ts"] = datetime.now(timezone.utc).isoformat()
    return value


def csv_sql(csv_text: str, sql: str) -> dict[str, Any]:
    """Run one read-only SELECT over uploaded CSV content."""
    non_select = r";|\b(insert|update|delete|drop|alter|create|replace)\b"
    if not re.match(r"^\s*select\b", sql, re.IGNORECASE) or re.search(
        non_select, sql, re.IGNORECASE
    ):
        return _result(False, error="csv_sql accepts one read-only SELECT")
    try:
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        db = sqlite3.connect(":memory:")
        columns = list(rows[0]) if rows else []
        db.execute("CREATE TABLE trips (" + ", ".join(f'\"{c}\" TEXT' for c in columns) + ")")
        placeholders = ",".join("?" for _ in columns)
        values = [[row.get(column) for column in columns] for row in rows]
        db.executemany("INSERT INTO trips VALUES (" + placeholders + ")", values)
        cursor = db.execute(sql)
        fields = [item[0] for item in cursor.description]
        output = [dict(zip(fields, row)) for row in cursor.fetchall()]
        db.close()
        return _result(
            True,
            {"rows": output, "row_count": len(output), "source": "uploaded.csv"},
            source="uploaded.csv",
        )
    except Exception as exc:
        return _result(False, error=f"read-only query failed: {type(exc).__name__}")


def policy_retriever(url: str, query: str, k: int = 3) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            raw = response.read()
        text = re.sub(r"<[^>]+>", " ", raw.decode("utf-8", "replace"))
        text = re.sub(r"\s+", " ", text).strip()
        terms = [t.lower() for t in re.findall(r"[a-z0-9]+", query)]
        sentences = re.split(r"(?<=[.!?])\s+", text)
        ranked = sorted(sentences, key=lambda s: sum(t in s.lower() for t in terms), reverse=True)
        passages = [
            {
                "text": sentence[:500],
                "source": url,
                "score": sum(t in sentence.lower() for t in terms),
            }
            for sentence in ranked[: max(1, k)]
        ]
        return _result(True, {"passages": passages}, source=url)
    except Exception as exc:
        return _result(False, error=f"pricing page unavailable: {type(exc).__name__}", source=url)


def calculator(expression: str, units: str | None = None) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9+\-*/().\s]+", expression):
        return _result(False, error="expression contains unsupported characters")
    try:
        tree = ast.parse(expression, mode="eval")
        allowed = (
            ast.Expression,
            ast.Constant,
            ast.BinOp,
            ast.UnaryOp,
            ast.Add,
            ast.Sub,
            ast.Mult,
            ast.Div,
            ast.USub,
            ast.UAdd,
            ast.Pow,
        )
        if any(not isinstance(node, allowed) for node in ast.walk(tree)):
            raise ValueError("unsupported expression")
        value = _calculate(tree.body)
        data = {"value": value}
        if units:
            data["units"] = units
        return _result(True, data)
    except Exception as exc:
        return _result(False, error=f"invalid arithmetic: {type(exc).__name__}")


def _calculate(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp):
        value = _calculate(node.operand)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.BinOp):
        left, right = _calculate(node.left), _calculate(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Pow):
            return left**right
    raise ValueError("unsupported expression")


def snapshot_metadata(text: str, source_url: str, accessed_at: str | None = None) -> dict[str, str]:
    return {
        "source_url": source_url,
        "accessed_at": accessed_at or datetime.now(timezone.utc).isoformat(),
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
    }
