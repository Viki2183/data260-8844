# DATA260 Homework 9

- Student: Vrishin KunnathamParambath
- SID4: 8844
- Repository: https://github.com/Viki2183/data260-8844
- Tagged tree: https://github.com/Viki2183/data260-8844/tree/hw9
- Working branch: `hw6-development`
- Canonical report: `KunnathamParambath_HW9.pdf`

HW9 extends the existing vulnerability-report application and HW8 Kafka system
with a Redis view counter, Redis Stack semantic cache, report-scoped version
invalidation, threshold economics, and four deterministic self-improving-agent
variants. Existing HW8 topics and workers remain unchanged.

## Submission contents

- `KunnathamParambath_HW9.pdf` and `report.pdf`: submission PDFs
- `report.md`: report source
- `verification.md`: exact reproducible commands and observed results
- `AI_USE.md`: AI-use disclosure
- `METRICS.md`: measured results
- `RUN_LOG.txt`: concise execution log
- `verification.json`: machine-readable verification summary
- `cases/`: fixed cache cases and Part 4 datasets
- `raw/`: unmodified structured evidence
- `screenshots/`: original and readability-cropped terminal captures

## Implementation locations

- `code/hw09/`: HW9 source package
- `code/test_hw09_core.py` and `code/test_hw09_agents.py`: HW9 tests
- `code/run_hw09_*.py`: live and deterministic verification runners
- `docker-compose.hw09.yml`: Redis Stack overlay for the existing HW8 Compose stack

## Core verification commands

```powershell
python -m compileall -q code/hw09 code/test_hw09_core.py code/test_hw09_agents.py
$env:PYTHONPATH = (Join-Path (Get-Location) 'code')
python -m unittest code.test_hw08_offline
docker compose -p data260-hw8 -f docker-compose.hw08.yml -f docker-compose.hw09.yml config
git diff --check
```

The dependency-complete application container reported 12/12 HW9 tests passing.
The host reported 40/40 HW8 offline tests passing. Ruff was not installed, so no
Ruff result is claimed.
