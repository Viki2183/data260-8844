from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
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
    prefix="/api/packages",
    tags=["packages"],
)


@router.post(
    "",
    response_model=schemas.PackageOut,
    status_code=status.HTTP_201_CREATED,
)
def create_package(
    payload: schemas.PackageCreate,
    db: Session = Depends(get_db),
    _user: models.UserDB = Depends(get_current_user),
):
    """Create a package for vulnerability reports."""
    try:
        return crud_hw4.create_package(db, payload)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A package with this name and code already exists.",
        )


@router.get(
    "",
    response_model=list[schemas.PackageOut],
)
def list_packages(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: models.UserDB = Depends(get_current_user),
):
    """Return packages using offset-based pagination."""
    return crud_hw4.list_packages(
        db,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{package_id}/reports",
    response_model=list[schemas.VulnerabilityReportOut],
)
def list_package_reports(
    package_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: models.UserDB = Depends(get_current_user),
):
    """Return vulnerability reports associated with one package."""
    package = crud_hw4.get_package(db, package_id)

    if package is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found.",
        )

    return crud_hw4.list_reports_by_package(
        db,
        package_id=package_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{package_id}",
    response_model=schemas.PackageOut,
)
def get_package(
    package_id: int,
    db: Session = Depends(get_db),
    _user: models.UserDB = Depends(get_current_user),
):
    """Return one package by ID."""
    package = crud_hw4.get_package(db, package_id)

    if package is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found.",
        )

    return package


@router.put(
    "/{package_id}",
    response_model=schemas.PackageOut,
)
def update_package(
    package_id: int,
    payload: schemas.PackageUpdate,
    db: Session = Depends(get_db),
    _user: models.UserDB = Depends(get_current_user),
):
    """Update one package by ID."""
    try:
        package = crud_hw4.update_package(
            db,
            package_id,
            payload,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A package with this name and code already exists.",
        )

    if package is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found.",
        )

    return package


@router.delete(
    "/{package_id}",
    response_model=schemas.PackageOut,
)
def delete_package(
    package_id: int,
    db: Session = Depends(get_db),
    _user: models.UserDB = Depends(get_current_user),
):
    """Delete a package when no reports reference it."""
    try:
        package = crud_hw4.delete_package(db, package_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )

    if package is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Package not found.",
        )

    return package