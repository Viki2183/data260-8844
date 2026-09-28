from datetime import datetime, timedelta
import secrets

import bcrypt
from sqlalchemy.orm import Session

try:
    from . import models, schemas
except ImportError:
    import models
    import schemas


SESSION_TTL_SECONDS = 900


def hash_password(password: str) -> str:
    """Create a salted bcrypt password hash."""
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Compare a plaintext password with its stored bcrypt hash."""
    return bcrypt.checkpw(
        password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )


def create_user(
    db: Session,
    payload: schemas.UserCreate,
) -> models.UserDB:
    """Create one user with a hashed password."""
    user = models.UserDB(
        name=payload.name.strip(),
        email=str(payload.email).lower(),
        password_hash=hash_password(payload.password),
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_email(
    db: Session,
    email: str,
) -> models.UserDB | None:
    """Find a user by normalized email address."""
    return (
        db.query(models.UserDB)
        .filter(models.UserDB.email == email.lower())
        .first()
    )


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> models.UserDB | None:
    """Return the user only when the password is valid."""
    user = get_user_by_email(db, email)

    if user is None:
        return None

    if not verify_password(password, user.password_hash):
        return None

    return user


def create_session(
    db: Session,
    user_id: int,
) -> models.SessionDB:
    """Create an opaque token stored only in the sessions table."""
    now = datetime.utcnow()
    expires = now + timedelta(seconds=SESSION_TTL_SECONDS)

    session = models.SessionDB(
        id=secrets.token_urlsafe(48),
        user_id=user_id,
        created_at=now,
        expires_at=expires,
    )

    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_active_session(
    db: Session,
    token: str | None,
) -> models.SessionDB | None:
    """Return a non-expired server-side session."""
    if not token:
        return None

    session = (
        db.query(models.SessionDB)
        .filter(models.SessionDB.id == token)
        .first()
    )

    if session is None:
        return None

    if session.expires_at <= datetime.utcnow():
        db.delete(session)
        db.commit()
        return None

    return session


def delete_session(
    db: Session,
    token: str | None,
) -> None:
    """Delete a session during logout."""
    if not token:
        return

    session = (
        db.query(models.SessionDB)
        .filter(models.SessionDB.id == token)
        .first()
    )

    if session is not None:
        db.delete(session)
        db.commit()


def create_report(
    db: Session,
    payload: schemas.VulnerabilityReportCreate,
) -> models.VulnerabilityReportDB:
    """Persist one vulnerability report."""
    report = models.VulnerabilityReportDB(
        package_name=payload.package_name,
        vulnerability_id=payload.vulnerability_id,
        submitter_email=str(payload.submitter_email),
        vulnerability_description=payload.vulnerability_description,
        severity=payload.severity,
        terms_accepted=payload.terms_accepted,
        submission_date=datetime.utcnow(),
    )

    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def list_reports(
    db: Session,
    search: str | None = None,
) -> list[models.VulnerabilityReportDB]:
    """Return reports, optionally filtered by package or advisory ID."""
    query = db.query(models.VulnerabilityReportDB)

    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(
            (models.VulnerabilityReportDB.package_name.ilike(pattern))
            | (
                models.VulnerabilityReportDB.vulnerability_id.ilike(
                    pattern
                )
            )
        )

    return query.order_by(
        models.VulnerabilityReportDB.id.asc()
    ).all()


def get_report(
    db: Session,
    report_id: int,
) -> models.VulnerabilityReportDB | None:
    """Find one vulnerability report by ID."""
    return (
        db.query(models.VulnerabilityReportDB)
        .filter(models.VulnerabilityReportDB.id == report_id)
        .first()
    )


def update_report(
    db: Session,
    report_id: int,
    payload: schemas.VulnerabilityReportUpdate,
) -> models.VulnerabilityReportDB | None:
    """Update an existing vulnerability report."""
    report = get_report(db, report_id)

    if report is None:
        return None

    report.package_name = payload.package_name
    report.vulnerability_id = payload.vulnerability_id
    report.submitter_email = str(payload.submitter_email)
    report.vulnerability_description = payload.vulnerability_description
    report.severity = payload.severity
    report.terms_accepted = payload.terms_accepted

    db.commit()
    db.refresh(report)
    return report


def delete_report(
    db: Session,
    report_id: int,
) -> models.VulnerabilityReportDB | None:
    """Delete one vulnerability report and its related references."""
    report = get_report(db, report_id)

    if report is None:
        return None

    # Delete child reference rows first because the existing
    # foreign key does not currently use ON DELETE CASCADE.
    db.query(models.VulnerabilityReferenceDB).filter(
        models.VulnerabilityReferenceDB.report_id == report_id
    ).delete(synchronize_session=False)

    db.delete(report)
    db.commit()

    return report
