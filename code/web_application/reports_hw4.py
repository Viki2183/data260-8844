from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

try:
    from . import crud_hw4, models, schemas
    from .auth_hw4 import get_current_user
    from .database import get_db
except ImportError:
    import crud_hw4
    import models
    import schemas
    from auth_hw4 import get_current_user
    from database import get_db


router = APIRouter(
    prefix="/api/vulnerability-reports",
    tags=["vulnerability reports"],
)


@router.get(
    "",
    response_model=list[schemas.VulnerabilityReportOut],
)
def list_vulnerability_reports(
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _user: models.UserDB = Depends(get_current_user),
):
    """List reports for authenticated users."""
    return crud_hw4.list_reports(db, search)


@router.get(
    "/{report_id}",
    response_model=schemas.VulnerabilityReportOut,
)
def get_vulnerability_report(
    report_id: int,
    db: Session = Depends(get_db),
    _user: models.UserDB = Depends(get_current_user),
):
    """Return one report by ID."""
    report = crud_hw4.get_report(db, report_id)

    if report is None:
        raise HTTPException(
            status_code=404,
            detail="Vulnerability report not found.",
        )

    return report


@router.post(
    "",
    response_model=schemas.VulnerabilityReportOut,
    status_code=status.HTTP_201_CREATED,
)
def create_vulnerability_report(
    payload: schemas.VulnerabilityReportCreate,
    db: Session = Depends(get_db),
    _user: models.UserDB = Depends(get_current_user),
):
    """Create one report for an authenticated user."""
    return crud_hw4.create_report(db, payload)


@router.put(
    "/{report_id}",
    response_model=schemas.VulnerabilityReportOut,
)
def update_vulnerability_report(
    report_id: int,
    payload: schemas.VulnerabilityReportUpdate,
    db: Session = Depends(get_db),
    _user: models.UserDB = Depends(get_current_user),
):
    """Update one report for an authenticated user."""
    report = crud_hw4.update_report(db, report_id, payload)

    if report is None:
        raise HTTPException(
            status_code=404,
            detail="Vulnerability report not found.",
        )

    return report


@router.delete(
    "/{report_id}",
    response_model=schemas.VulnerabilityReportOut,
)
def delete_vulnerability_report(
    report_id: int,
    db: Session = Depends(get_db),
    _user: models.UserDB = Depends(get_current_user),
):
    """Delete one report for an authenticated user."""
    report = crud_hw4.delete_report(db, report_id)

    if report is None:
        raise HTTPException(
            status_code=404,
            detail="Vulnerability report not found.",
        )

    return report
