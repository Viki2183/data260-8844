from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

class PackageBase(BaseModel):
    """Shared validation fields for package records."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )

    ecosystem: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    package_code: str = Field(
        ...,
        alias="packageCode",
        min_length=3,
        max_length=255,
        pattern=r"^s8844-[A-Za-z0-9][A-Za-z0-9._-]*$",
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )

    @field_validator("name", "ecosystem", "package_code")
    @classmethod
    def reject_blank_package_text(cls, value: str) -> str:
        """Reject package fields containing only whitespace."""
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("This field cannot be blank.")

        return cleaned


class PackageCreate(PackageBase):
    """Payload for creating a package."""


class PackageUpdate(PackageBase):
    """Payload for updating a package."""


class PackageOut(PackageBase):
    """Package response returned by the API."""

    id: int
    created_at: datetime = Field(
        alias="createdAt",
    )
    updated_at: datetime = Field(
        alias="updatedAt",
    )

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class VulnerabilityReportBase(BaseModel):
    """Shared fields for creating and updating vulnerability reports."""

    package_name: str = Field(
        ...,
        alias="packageName",
        min_length=1,
    )

    package_id: int = Field(
        ...,
        alias="packageId",
        gt=0,
    )

    vulnerability_id: str = Field(
        ...,
        alias="vulnerabilityId",
        min_length=1,
    )

    submitter_email: EmailStr = Field(
        ...,
        alias="submitterEmail",
    )

    vulnerability_description: str = Field(
        ...,
        alias="vulnerabilityDescription",
        min_length=26,
    )

    severity: str = Field(
        ...,
        pattern="^(Critical|High|Medium|Low)$",
    )

    affected_versions_count: int = Field(
        default=0,
        alias="affectedVersionsCount",
        ge=0,
    )

    terms_accepted: bool = Field(
        ...,
        alias="termsAccepted",
    )

    model_config = ConfigDict(
        populate_by_name=True,
    )

    @field_validator(
        "package_name",
        "vulnerability_id",
        "vulnerability_description",
    )
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        """Reject strings containing only whitespace."""
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("This field cannot be blank.")

        return cleaned

    @field_validator("terms_accepted")
    @classmethod
    def require_terms_acceptance(cls, value: bool) -> bool:
        """Require the user to accept the terms."""
        if not value:
            raise ValueError("Terms must be accepted.")

        return value


class VulnerabilityReportCreate(VulnerabilityReportBase):
    """Payload for POST requests."""


class VulnerabilityReportUpdate(VulnerabilityReportBase):
    """Payload for PUT requests."""


class VulnerabilityReferenceOut(BaseModel):
    """Related data returned by the N+1 list endpoints."""

    id: int
    report_id: int
    reference_url: str
    reference_type: str


class VulnerabilityReportOut(VulnerabilityReportBase):
    """Normal vulnerability report response."""

    id: int

    
    submission_date: datetime = Field(
        alias="submissionDate",
    )

    created_at: datetime = Field(
        alias="createdAt",
    )

    updated_at: datetime = Field(
        alias="updatedAt",
    )
    
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class VulnerabilityReportWithReferences(VulnerabilityReportOut):
    """Report response containing related references."""

    references: list[VulnerabilityReferenceOut] = Field(
        default_factory=list,
    )


class UserCreate(BaseModel):
    """Payload for creating a local demonstration user."""

    name: str = Field(..., min_length=1)
    email: EmailStr
    password: str = Field(..., min_length=8)


class UserOut(BaseModel):
    """Safe user response that never exposes password_hash."""

    id: int
    name: str
    email: EmailStr

    model_config = ConfigDict(
        from_attributes=True,
    )


class LoginRequest(BaseModel):
    """Email/password login payload."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class LoginResponse(BaseModel):
    """Successful login response."""

    message: str
    user: UserOut


class MeResponse(BaseModel):
    """Current-session response."""

    logged_in: bool
    user: UserOut
