"""Apply the HW9 view_count column after a manual schema preflight."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from hw09.migration import migration_sql


def main() -> None:
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import URL

    url = URL.create(
        "mysql+pymysql",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=int(os.environ["DB_PORT"]),
        database=os.environ["DB_NAME"],
    )
    engine = create_engine(url, future=True)
    with engine.begin() as connection:
        columns = connection.execute(
            text("SHOW COLUMNS FROM vulnerability_reports LIKE 'view_count'")
        )
        if columns.first() is None:
            connection.execute(text(migration_sql()))
            print("Added vulnerability_reports.view_count")
        else:
            print("vulnerability_reports.view_count already exists")


if __name__ == "__main__":
    main()
