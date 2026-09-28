from datetime import datetime, timedelta
import random
import sys
from pathlib import Path

WEB_APP_DIR = Path(__file__).resolve().parent / 'web_application'
sys.path.insert(0, str(WEB_APP_DIR))

from database import Base, engine, db_session_basede26
from models import (
    VulnerabilityReferenceDB,
    VulnerabilityReportDB,
)


SEED = 8844
REPORT_COUNT = 5000
REFERENCE_COUNT = 200


def main() -> None:
    """Create deterministic HW4 benchmark data."""
    random_generator = random.Random(SEED)

    Base.metadata.create_all(bind=engine)
    db = db_session_basede26()

    try:
        # Clear only benchmark-domain data.
        db.query(VulnerabilityReferenceDB).delete(
            synchronize_session=False,
        )
        db.query(VulnerabilityReportDB).delete(
            synchronize_session=False,
        )
        db.commit()

        severities = [
            "Critical",
            "High",
            "Medium",
            "Low",
        ]

        reports = []

        for index in range(1, REPORT_COUNT + 1):
            reports.append(
                VulnerabilityReportDB(
                    package_name=f"package-{index:05d}",
                    vulnerability_id=f"CVE-8844-{index:05d}",
                    submitter_email=f"seed-{index}@example.com",
                    vulnerability_description=(
                        "Deterministic benchmark vulnerability "
                        f"description for record {index}."
                    ),
                    severity=random_generator.choice(severities),
                    terms_accepted=True,
                    submission_date=(
                        datetime(2026, 1, 1)
                        + timedelta(minutes=index)
                    ),
                )
            )

        # Flush assigns database IDs before related rows are created.
        db.add_all(reports)
        db.flush()

        references = []

        for index in range(REFERENCE_COUNT):
            report = reports[index]

            references.append(
                VulnerabilityReferenceDB(
                    report_id=report.id,
                    reference_url=(
                        "https://example.invalid/advisory/"
                        f"{report.vulnerability_id}"
                    ),
                    reference_type=random_generator.choice(
                        ["advisory", "fix", "source"]
                    ),
                )
            )

        db.add_all(references)
        db.commit()

        print(f"Seeded reports: {len(reports)}")
        print(f"Seeded references: {len(references)}")
        print(f"Seed: {SEED}")

    finally:
        db.close()


if __name__ == "__main__":
    main()

