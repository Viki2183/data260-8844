# DATA 260 HW1 Domain Schema

## Personal Configuration

- SID4: 8844
- PORT_BASE: 8744
- PREFIX: s8844
- SEED: 8844
- VERIFY_SEED: 268844
- DOMAIN_ID: 4
- Assigned Domain: Open-source package vulnerabilities

## Entity

Vulnerability Report

## Fields

- packageName
  - Primary field
  - Required text
  - Name of the affected open-source package

- vulnerabilityId
  - Secondary field
  - Required text
  - CVE or security advisory identifier

- submitterEmail
  - Required email
  - Email address of the report submitter

- vulnerabilityDescription
  - Required textarea
  - Description of the vulnerability
  - Must contain more than 25 characters

- severity
  - Required category
  - One of the four values listed below

- termsAccepted
  - Required boolean
  - Indicates acceptance of the terms and conditions

## Severity Categories

- Critical
- High
- Medium
- Low

## Generated Field

- submissionDate
  - Current date and time added after successful validation