from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator


# Keep all shared web application files in the HW1 application folder.
WEB_ROOT = Path(__file__).resolve().parent

app = FastAPI(
    title="Open-Source Package Vulnerability API",
    version="2.0.0",
)


Severity = Literal["Critical", "High", "Medium", "Low"]


class VulnerabilityReportInput(BaseModel):
    """Fields submitted when creating or updating a vulnerability report."""

    packageName: str = Field(..., min_length=1)
    vulnerabilityId: str = Field(..., min_length=1)
    submitterEmail: str = Field(..., min_length=1)
    vulnerabilityDescription: str = Field(..., min_length=26)
    severity: Severity
    termsAccepted: bool

    @field_validator(
        "packageName",
        "vulnerabilityId",
        "submitterEmail",
        "vulnerabilityDescription",
    )
    @classmethod
    def required_text_must_not_be_blank(cls, value: str) -> str:
        """Reject values that contain only spaces."""
        cleaned_value = value.strip()

        if not cleaned_value:
            raise ValueError("This field cannot be blank.")

        return cleaned_value

    @field_validator("submitterEmail")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        """Apply a simple email-format check without extra dependencies."""
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("submitterEmail must be a valid email address.")

        return value

    @field_validator("termsAccepted")
    @classmethod
    def terms_must_be_accepted(cls, value: bool) -> bool:
        """Require agreement before accepting a report."""
        if not value:
            raise ValueError("Terms must be accepted.")

        return value


class VulnerabilityReport(VulnerabilityReportInput):
    """Stored vulnerability report returned by the API."""

    id: int
    submissionDate: datetime


# Keep sample records in memory while the FastAPI process is running.
reports: list[VulnerabilityReport] = [
    VulnerabilityReport(
        id=1,
        packageName="requests",
        vulnerabilityId="CVE-2024-35195",
        submitterEmail="security@example.com",
        vulnerabilityDescription=(
            "A package vulnerability may allow an attacker to bypass "
            "certificate verification in affected configurations."
        ),
        severity="High",
        termsAccepted=True,
        submissionDate=datetime.now(timezone.utc),
    ),
    VulnerabilityReport(
        id=2,
        packageName="urllib3",
        vulnerabilityId="CVE-2023-43804",
        submitterEmail="security@example.com",
        vulnerabilityDescription=(
            "An issue in the package can expose applications to unsafe "
            "redirect handling when processing untrusted requests."
        ),
        severity="Medium",
        termsAccepted=True,
        submissionDate=datetime.now(timezone.utc),
    ),
]


@app.get("/", include_in_schema=False)
async def read_home() -> FileResponse:
    """Serve the shared HW2 web application."""
    return FileResponse(WEB_ROOT / "index.html")


@app.get("/styles.css", include_in_schema=False)
async def read_stylesheet() -> FileResponse:
    """Serve the shared stylesheet."""
    return FileResponse(WEB_ROOT / "styles.css")


@app.get("/app.js", include_in_schema=False)
async def read_javascript() -> FileResponse:
    """Serve the shared frontend JavaScript."""
    return FileResponse(WEB_ROOT / "app.js")


@app.get(
    "/api/vulnerability-reports",
    response_model=list[VulnerabilityReport],
)
async def list_vulnerability_reports(
    search: str | None = Query(default=None),
) -> list[VulnerabilityReport]:
    """Return all reports or only reports matching either domain field."""
    if not search or not search.strip():
        return reports

    search_text = search.strip().lower()

    return [
        report
        for report in reports
        if (
            search_text in report.packageName.lower()
            or search_text in report.vulnerabilityId.lower()
        )
    ]


@app.get(
    "/api/vulnerability-reports/{report_id}",
    response_model=VulnerabilityReport,
)
async def get_vulnerability_report(report_id: int) -> VulnerabilityReport:
    """Return one vulnerability report by ID."""
    report = next((item for item in reports if item.id == report_id), None)

    if report is None:
        raise HTTPException(
            status_code=404,
            detail="Vulnerability report not found.",
        )

    return report


@app.post(
    "/api/vulnerability-reports",
    response_model=VulnerabilityReport,
    status_code=201,
)
async def create_vulnerability_report(
    report_data: VulnerabilityReportInput,
) -> VulnerabilityReport:
    """Validate and add a new vulnerability report."""
    new_id = max((report.id for report in reports), default=0) + 1

    new_report = VulnerabilityReport(
        id=new_id,
        submissionDate=datetime.now(timezone.utc),
        **report_data.model_dump(),
    )

    reports.append(new_report)
    return new_report


@app.put(
    "/api/vulnerability-reports/{report_id}",
    response_model=VulnerabilityReport,
)
async def update_vulnerability_report(
    report_id: int,
    report_data: VulnerabilityReportInput,
) -> VulnerabilityReport:
    """Validate and replace an existing vulnerability report."""
    report_index = next(
        (
            index
            for index, report in enumerate(reports)
            if report.id == report_id
        ),
        None,
    )

    if report_index is None:
        raise HTTPException(
            status_code=404,
            detail="Vulnerability report not found.",
        )

    updated_report = VulnerabilityReport(
        id=report_id,
        submissionDate=reports[report_index].submissionDate,
        **report_data.model_dump(),
    )

    reports[report_index] = updated_report
    return updated_report


@app.delete(
    "/api/vulnerability-reports/{report_id}",
    status_code=204,
)
async def delete_vulnerability_report(report_id: int) -> Response:
    """Delete one vulnerability report by ID."""
    report_index = next(
        (
            index
            for index, report in enumerate(reports)
            if report.id == report_id
        ),
        None,
    )

    if report_index is None:
        raise HTTPException(
            status_code=404,
            detail="Vulnerability report not found.",
        )

    reports.pop(report_index)
    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
    app,
    host="127.0.0.1",
    port=8744,
    reload=False,
)