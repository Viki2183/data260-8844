"""Offline-reviewable, non-destructive HW7 users-table migration definition.

The deployed table must still be inspected before applying any ALTER statements.
This definition intentionally does not guess how existing rows should be
backfilled when the deployed schema is unknown.
"""

ALLOWED_ROLES = ("reader", "writer", "moderator")

HW7_USER_MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INT NOT NULL AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    username VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'reader',
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_username (username),
    UNIQUE KEY uq_users_email (email),
    CONSTRAINT ck_users_role CHECK (role IN ('reader', 'writer', 'moderator'))
) ENGINE=InnoDB
""".strip()


def migration_sql() -> str:
    """Return the non-destructive migration definition without executing it."""
    return HW7_USER_MIGRATION_SQL


def migration_requires_preflight() -> tuple[str, ...]:
    """Describe checks required before altering an existing deployed table."""
    return (
        "Confirm users exists and inspect its columns and constraints.",
        "Confirm existing rows have usable unique username and email values.",
        "Do not invent a username backfill when existing data is ambiguous.",
        "Stop on incompatible data instead of deleting or rewriting rows.",
    )
