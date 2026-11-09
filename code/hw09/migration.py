"""Reviewable HW9 schema migration for existing MySQL deployments."""

HW09_VIEW_COUNT_SQL = """
ALTER TABLE vulnerability_reports
    ADD COLUMN view_count INT NOT NULL DEFAULT 0
""".strip()


def migration_sql() -> str:
    return HW09_VIEW_COUNT_SQL
