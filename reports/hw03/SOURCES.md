# HW3 Corpus Sources

## Assigned domain

DOMAIN_ID 4: Open-source package vulnerabilities.

## Primary source

- Organization: Open Source Vulnerability Database (OSV.dev)
- Data documentation: https://google.github.io/osv.dev/data/
- Downloaded source: https://storage.googleapis.com/osv-vulnerabilities/PyPI/all.zip
- Description: Official PyPI ecosystem vulnerability records in OSV JSON format.
- Access date: 2026-09-19
- Local source archive: `data/hw03_corpus/pypi_osv_all.zip`

## Local corpus construction

The source archive was extracted into `data/hw03_corpus/pypi_records/`.

A deterministic selection script selected records containing:

- A non-empty summary
- At least 800 characters of vulnerability details
- Affected package information

The selected records were copied into `data/hw03_corpus/selected_pypi/`.

The selected corpus contains 69 JSON records and 507,649 bytes of content.

The full source archive and full extracted dump are retained locally but excluded from Git because they are unnecessary for the reproducible graded experiment.