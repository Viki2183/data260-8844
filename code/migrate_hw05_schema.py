"""
One-time HW5 database migration.

This script extends the existing HW4 MySQL schema without deleting
the existing vulnerability reports.
"""

from pathlib import Path
import sys

from sqlalchemy import text

# Make the existing web_application package importable when this
# script is run from the repository root.
WEB_APP_DIR = Path(__file__).resolve().parent / "web_application"
sys.path.insert(0, str(WEB_APP_DIR))

from database import engine  # noqa: E402


def column_exists(connection, table_name: str, column_name: str) -> bool:
    """Check whether a column already exists before adding it."""
    query = text(
        """
        SELECT COUNT(*) AS column_count
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
          AND table_name = :table_name
          AND column_name = :column_name
        """
    )

    count = connection.execute(
        query,
        {
            "table_name": table_name,
            "column_name": column_name,
        },
    ).scalar_one()

    return count > 0


def foreign_key_exists(
    connection,
    table_name: str,
    constraint_name: str,
) -> bool:
    """Check whether the HW5 foreign key already exists."""
    query = text(
        """
        SELECT COUNT(*) AS constraint_count
        FROM information_schema.table_constraints
        WHERE constraint_schema = DATABASE()
          AND table_name = :table_name
          AND constraint_name = :constraint_name
          AND constraint_type = 'FOREIGN KEY'
        """
    )

    count = connection.execute(
        query,
        {
            "table_name": table_name,
            "constraint_name": constraint_name,
        },
    ).scalar_one()

    return count > 0


def main() -> None:
    """Create and populate the HW5 package relationship."""
    with engine.begin() as connection:
        print("Creating packages table if it does not exist...")

        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS packages (
                    id INT NOT NULL AUTO_INCREMENT,
                    name VARCHAR(255) NOT NULL,
                    ecosystem VARCHAR(100) NOT NULL,
                    package_code VARCHAR(255) NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    PRIMARY KEY (id),
                    UNIQUE KEY uq_packages_package_code (package_code),
                    UNIQUE KEY uq_packages_name_ecosystem (name, ecosystem)
                ) ENGINE=InnoDB
                """
            )
        )

        new_columns = {
            "package_id": """
                ALTER TABLE vulnerability_reports
                ADD COLUMN package_id INT NULL
            """,
            "affected_versions_count": """
                ALTER TABLE vulnerability_reports
                ADD COLUMN affected_versions_count INT NOT NULL DEFAULT 0
            """,
            "created_at": """
                ALTER TABLE vulnerability_reports
                ADD COLUMN created_at DATETIME NULL
            """,
            "updated_at": """
                ALTER TABLE vulnerability_reports
                ADD COLUMN updated_at DATETIME NULL
            """,
        }

        for column_name, alter_statement in new_columns.items():
            if not column_exists(
                connection,
                "vulnerability_reports",
                column_name,
            ):
                print(f"Adding column: {column_name}")
                connection.execute(text(alter_statement))
            else:
                print(f"Column already exists: {column_name}")

        print("Creating package records from existing reports...")

        connection.execute(
            text(
                """
                INSERT IGNORE INTO packages (
                    name,
                    ecosystem,
                    package_code,
                    created_at,
                    updated_at
                )
                SELECT
                    package_name,
                    'PyPI',
                    CONCAT('s8844-', package_name),
                    MIN(submission_date),
                    MAX(submission_date)
                FROM vulnerability_reports
                GROUP BY package_name
                """
            )
        )

        print("Linking vulnerability reports to packages...")

        connection.execute(
            text(
                """
                UPDATE vulnerability_reports AS reports
                INNER JOIN packages
                    ON packages.name = reports.package_name
                   AND packages.ecosystem = 'PyPI'
                SET
                    reports.package_id = packages.id,
                    reports.created_at = COALESCE(
                        reports.created_at,
                        reports.submission_date
                    ),
                    reports.updated_at = COALESCE(
                        reports.updated_at,
                        reports.submission_date
                    )
                WHERE reports.package_id IS NULL
                """
            )
        )

        unlinked_count = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM vulnerability_reports
                WHERE package_id IS NULL
                """
            )
        ).scalar_one()

        if unlinked_count != 0:
            raise RuntimeError(
                f"{unlinked_count} reports were not linked to a package."
            )

        connection.execute(
            text(
                """
                ALTER TABLE vulnerability_reports
                MODIFY COLUMN package_id INT NOT NULL
                """
            )
        )

        constraint_name = "fk_reports_package"

        if not foreign_key_exists(
            connection,
            "vulnerability_reports",
            constraint_name,
        ):
            print("Adding package foreign-key constraint...")

            connection.execute(
                text(
                    f"""
                    ALTER TABLE vulnerability_reports
                    ADD CONSTRAINT {constraint_name}
                    FOREIGN KEY (package_id)
                    REFERENCES packages(id)
                    ON DELETE RESTRICT
                    """
                )
            )
        else:
            print("Foreign-key constraint already exists.")

    print("HW5 database migration completed successfully.")


if __name__ == "__main__":
    main()