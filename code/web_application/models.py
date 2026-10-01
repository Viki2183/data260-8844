from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from .database import Base
except ImportError:
    from database import Base


class PackageDB(Base):
    """Related package entity for HW5 vulnerability reports."""

    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # The package's display name, such as package-00001.
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # The package ecosystem, such as PyPI.
    ecosystem: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # A stable unique identifier for the package.
    package_code: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    # A package can be associated with multiple vulnerability reports.
    reports: Mapped[list["VulnerabilityReportDB"]] = relationship(
        back_populates="package",
        passive_deletes=True,
    )


class VulnerabilityReportDB(Base):
    """Primary HW5 domain entity stored in MySQL."""

    __tablename__ = "vulnerability_reports"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Kept for compatibility with the existing HW4 frontend and data.
    package_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    # New normalized relationship required by HW5.
    package_id: Mapped[int] = mapped_column(
        ForeignKey(
            "packages.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
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

    # HW5 numeric field with a sensible default.
    affected_versions_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    # Existing HW4 timestamp.
    submission_date: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    # HW5 timestamps.
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    package: Mapped[PackageDB] = relationship(
        back_populates="reports",
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