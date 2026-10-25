"""Offline safety checks for the HW7 migration definition."""

from __future__ import annotations

from web_application.hw7_migration import migration_requires_preflight, migration_sql


def main() -> None:
    sql = migration_sql().upper()

    assert "CREATE TABLE IF NOT EXISTS USERS" in sql
    assert "PASSWORD_HASH VARCHAR(255) NOT NULL" in sql
    assert "UNIQUE KEY UQ_USERS_USERNAME" in sql
    assert "UNIQUE KEY UQ_USERS_EMAIL" in sql
    assert "CHECK (ROLE IN ('READER', 'WRITER', 'MODERATOR'))" in sql
    assert "DROP TABLE" not in sql
    assert "DELETE FROM" not in sql
    assert "TRUNCATE" not in sql
    assert "PLAINTEXT" not in sql

    requirements = migration_requires_preflight()
    assert requirements
    assert any("backfill" in item.lower() for item in requirements)
    assert any("incompatible" in item.lower() for item in requirements)

    print("PASS offline migration safety definition")
    print("HW7_MIGRATION_OFFLINE_PASS")


if __name__ == "__main__":
    main()
