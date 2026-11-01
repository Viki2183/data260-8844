"""Pure validation for the assigned open-source vulnerability-report entity."""

from __future__ import annotations

import re
from typing import Any, Mapping

SEVERITIES = frozenset({"Critical", "High", "Medium", "Low"})
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_vulnerability_report(data: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in (
        "packageName",
        "vulnerabilityId",
        "submitterEmail",
        "vulnerabilityDescription",
    ):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be non-empty text")

    email = data.get("submitterEmail")
    if isinstance(email, str) and email.strip() and not EMAIL_RE.match(email.strip()):
        errors.append("submitterEmail must be a valid email")

    description = data.get("vulnerabilityDescription")
    if isinstance(description, str) and len(description.strip()) < 26:
        errors.append("vulnerabilityDescription must contain at least 26 characters")

    if data.get("severity") not in SEVERITIES:
        errors.append("severity must be Critical, High, Medium, or Low")
    if data.get("termsAccepted") is not True:
        errors.append("termsAccepted must be true")

    versions = data.get("affectedVersionsCount", 0)
    if isinstance(versions, bool) or not isinstance(versions, int) or versions < 0:
        errors.append("affectedVersionsCount must be a non-negative integer")
    return errors

