from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

try:
    from .database import Base
except ImportError:
    from database import Base


class VulnerabilityReportDB(Base):
    """Primary HW4 domain entity stored in MySQL."""

    __tablename__ = "vulnerability_reports"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    package_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    vulnerability_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    submitter_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    vulnerability_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    terms_accepted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    submission_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )


class VulnerabilityReferenceDB(Base):
    """Related test data used by the HW4 N+1 experiment."""

    __tablename__ = "vulnerability_references"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    report_id: Mapped[int] = mapped_column(
        ForeignKey("vulnerability_reports.id"),
        nullable=False,
    )

    reference_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    reference_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )


class UserDB(Base):
    """Application users authenticated by email and password."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )


class SessionDB(Base):
    """Server-side sessions referenced by opaque browser tokens."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )
