from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

try:
    from . import models
    from .auth_hw4 import get_current_user
    from .database import get_db
except ImportError:
    import models
    from auth_hw4 import get_current_user
    from database import get_db


router = APIRouter(
    prefix="/api/benchmark",
    tags=["N+1 benchmark"],
)


def report_to_dict(report, references):
    """Convert a report and related rows into JSON-safe data."""
    return {
        "id": report.id,
        "packageName": report.package_name,
        "vulnerabilityId": report.vulnerability_id,
        "submitterEmail": report.submitter_email,
        "vulnerabilityDescription": (
            report.vulnerability_description
        ),
        "severity": report.severity,
        "termsAccepted": report.terms_accepted,
        "submissionDate": report.submission_date,
        "references": [
            {
                "id": reference.id,
                "report_id": reference.report_id,
                "reference_url": reference.reference_url,
                "reference_type": reference.reference_type,
            }
            for reference in references
        ],
    }


@router.get("/naive")
def naive_list(
    page_size: int = Query(
        default=10,
        ge=1,
        le=200,
    ),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Intentionally issue one related query per report."""
    reports = (
        db.query(models.VulnerabilityReportDB)
        .order_by(models.VulnerabilityReportDB.id.asc())
        .limit(page_size)
        .all()
    )

    items = []

    for report in reports:
        # This query inside the loop creates the N+1 pattern.
        references = (
            db.query(models.VulnerabilityReferenceDB)
            .filter(
                models.VulnerabilityReferenceDB.report_id
                == report.id
            )
            .all()
        )

        items.append(report_to_dict(report, references))

    return {
        "version": "naive",
        "page_size": page_size,
        "count": len(items),
        "items": items,
    }


@router.get("/fixed")
def fixed_list(
    page_size: int = Query(
        default=10,
        ge=1,
        le=200,
    ),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Fetch the page and all related rows in two SQL queries."""
    reports = (
        db.query(models.VulnerabilityReportDB)
        .order_by(models.VulnerabilityReportDB.id.asc())
        .limit(page_size)
        .all()
    )

    report_ids = [report.id for report in reports]

    references = (
        db.query(models.VulnerabilityReferenceDB)
        .filter(
            models.VulnerabilityReferenceDB.report_id.in_(report_ids)
        )
        .all()
        if report_ids
        else []
    )

    references_by_report = {}

    for reference in references:
        references_by_report.setdefault(
            reference.report_id,
            [],
        ).append(reference)

    items = [
        report_to_dict(
            report,
            references_by_report.get(report.id, []),
        )
        for report in reports
    ]

    return {
        "version": "fixed",
        "page_size": page_size,
        "count": len(items),
        "items": items,
    }
