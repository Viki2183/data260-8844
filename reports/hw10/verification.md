# HW10 Verification

**Date:** November 15, 2026<br>
**Repository:** `C:\\Projects\\data260-8844`<br>
**Branch:** `hw6-development`<br>
**Student:** Vrishin KunnathamParambath<br>
**SID4:** 8844

## Scope and protection boundary

HW1–HW9 files were not modified. The frozen files `reports/hw10/eval_cases.json` and `reports/hw10/human_labels.csv` were not modified. `requirements.txt`, `pyproject.toml`, existing HW8 workers/topics/envelopes/retry/commit/idempotency/DLT behavior, and existing HW9 cache/endpoint behavior were not modified. No files were staged, committed, or pushed during Phase 6.

## Report-convention inspection

Read-only inspection covered `reports/hw01` through `reports/hw09`, including available `report.md`, `REPORT_SOURCE.md`, `report.html`, `verification.md`, `verification.json`, `AI_USE.md`, `METRICS.md`, `RUN_LOG.txt`, raw evidence, screenshot directories, and PDFs. Observed conventions included:

- Letter-page HTML/CSS styling with 14 pt headings, 12 pt subheadings, and 11 pt body text.
- Relative evidence links such as `raw/...` and `screenshots/...`.
- Numbered or descriptive screenshot captions, usually centered/italicized in HW9.
- Separate report, verification, AI-use, metrics, and run-log artifacts.
- Explicit distinction between live, historical, offline, unavailable, and blocked evidence.
- PNG screenshots in prior screenshot directories; no HW1–HW9 images were reused.

## HW10 reformatting and PDF validation

The HW10 report source and generated HTML now follow the established HW6–HW9 visual conventions: Letter page size, approximately 0.62-inch margins, Arial body text, a centered cover with student metadata, dark-blue section headings with thin rules, blue-gray table headers and borders, light-gray code blocks with a blue left rule, and centered italic figure captions. The five genuine HW10 screenshots remain the only HW10 figures; no historical screenshot was copied.

The regenerated `report.pdf` is a valid 11-page PDF, below the 35-page limit. A page-by-page visual reinspection of this regenerated PDF was attempted, but Edge launched with an application error and the browser access host was unavailable. Therefore, no unsupported visual no-clipping or no-overlap claim is made for this regenerated PDF. Structural PDF checks passed: `%PDF-1.4` header, 11 page objects, 11 content markers, 5 embedded image markers, and `%%EOF`. The earlier 9-page PDF had been visually inspected before this documentation update; that inspection does not substitute for visual inspection of the regenerated 11-page PDF.

All five screenshot paths are present and referenced with captions:

| Figure | Path | Caption status |
|---|---|---|
| 1 | `screenshots/hw10_summary.png` | Present; Summary page caption |
| 2 | `screenshots/hw10_evaluation.png` | Present; Evaluation page caption |
| 3 | `screenshots/hw10_trace_cache_hit.png` | Present; cache-hit Trace Lookup caption |
| 4 | `screenshots/hw10_trace_cache_miss.png` | Present; cache-miss Trace Lookup caption |
| 5 | `screenshots/hw10_trace_failed.png` | Present; controlled-failure Trace Lookup caption |

Standalone PDF-page PNG export was checked as a tooling item. No `pdftoppm`, `pdfinfo`, `mutool`, ImageMagick, Ghostscript, or equivalent PDF rasterizer is installed in the available environments; the available Python environments also lack PyMuPDF, pypdf, pdf2image, and equivalent PDF-rendering modules. Therefore, the pages were rendered and visually inspected in Edge, but no additional page-render PNG artifacts were created in the repository.

## Commands executed

The following read-only inspection and validation commands were run from `C:\\Projects\\data260-8844` or against that repository:

```powershell
Get-ChildItem -Force
Get-ChildItem -Path . -Filter AGENTS.md -Recurse -File
Get-ChildItem -Path . -Filter AGENT.md -Recurse -File
Get-Content AGENT.md
Get-ChildItem reports -Directory
Get-ChildItem reports/hw01 through reports/hw10 -Recurse -File
Get-Content reports/hw01/... through reports/hw09/...
rg -n "^(#|##|###)|figure-caption|!\\[|screenshots/|Raw|Evidence|Verification|live|offline|blocked|unavailable" reports
Get-Command pandoc,weasyprint,wkhtmltopdf,chromium,chrome,msedge,pdftoppm,pdfinfo,mutool
python -c "import importlib.util; ..."
Get-Content reports/hw10/raw/judge_validation.json
Get-Content reports/hw10/raw/latency_summary.json
Get-Content reports/hw10/raw/phase5_health.json
Get-Content reports/hw10/raw/traces/trace_index.json
```

Phase 5 service and evidence commands recorded in the prior verification boundary included:

```powershell
docker compose -f docker-compose.hw08.yml config --services
docker compose -f docker-compose.hw09.yml config --services
docker compose -f docker-compose.hw08.yml up -d
docker compose -f docker-compose.hw09.yml up -d
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8745/health
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8510/_stcore/health
.\.venv-hw10\Scripts\python.exe -B code/hw10/test_dashboard.py
.\.venv-hw10\Scripts\python.exe -B code/hw10/run_phase5_live.py
```

The live runner used a read-only Kafka observer and the existing authenticated HW9 endpoint. It did not publish test messages directly, change offsets, commit offsets, clear Redis, or alter existing workers.

## Service health results

| Service/check | Result | Classification |
|---|---|---|
| MySQL `127.0.0.1:3306` | Reachable | Live |
| Redis `127.0.0.1:16379` | Ping successful | Live |
| Kafka `127.0.0.1:29092` | Reachable; observer started read-only | Live |
| Ollama `127.0.0.1:11434` | Reachable; `qwen3:8b` available | Live |
| FastAPI `/health` on port 8745 | HTTP 200 | Live |
| Authenticated `/api/agent/ask` | Verified | Live |
| Streamlit health | HTTP 200 during prior startup check | Live startup check |

Raw health evidence: `raw/phase5_health.json`.

## Judge checks

- Frozen cases: 20.
- Trials: 3 repeatability trials of one judge, not 3 different judges.
- Cases per trial: 20.
- Successful evaluations: 60/60.
- Model: local Ollama `qwen3:8b`.
- Temperature: 0.
- Seed: 8844.
- Prompt version: `hw10-geval-v1`.
- MAD: 0.0.
- Changed scores: 0.
- Mean absolute change: 0.0.
- Maximum absolute change: 0.
- Repeatability: 100%.
- Spearman: `null`, status `undefined_constant_human_labels`; rank correlation cannot be estimated from constant human labels.
- Deployment readiness: not claimed.
- Judge reliability: not established; the judge should not be trusted for deployment gating from this evidence.

Evidence: `raw/judge_run_1.json`, `raw/judge_run_2.json`, `raw/judge_run_3.json`, and `raw/judge_validation.json`.

## Human-label checks

- Manual student confirmation occurred before label freeze and judge execution.
- Exactly 20 cases are present in the frozen case file and label file.
- Case IDs match and are unique.
- All scores are integer 1–5.
- All 20 scores equal 1.
- No pending labels remain.
- The reason is preserved in the label provenance/notes fields.
- All 20 cases are offline reconstructed Writer drafts.
- None of the 20 cases is a direct live Writer observation.
- Only one genuine raw Writer draft was available: `reports/hw08/raw/part2_agent_journey.jsonl`.
- No diverse v2 set was created because additional drafts would require fabrication or reconstruction.
- The separate live Writer observation is present in the live successful miss trace.

## Trace checks

Trace IDs use `correlation_id` directly; no second request identifier was introduced.

- Cache hit: `hw10-live-hit-b1d5e1ae95ad`.
- Successful cache miss: `hw10-live-miss-e56b8558868c`.
- Controlled failure: `hw10-live-failed-120deeaa2ee1`.
- Successful miss order: `cache_lookup → inbox → planner → tasks → writer → drafts → reviewer → final`.
- Failed stage: validation/report lookup.
- Failed result: safe HTTP 404 for a nonexistent report.
- Trace index: `raw/traces/trace_index.json`.
- Additional live end-to-end trace: `hw10-live-e2e-eval-fdc655292734`.
- Additional trace evidence: `raw/end_to_end/live_evaluation_trace.json`.
- The additional trace contains the captured question, Planner plan, Writer draft, Reviewer/final answer, Kafka topic/partition/offset metadata, explicit stage boundaries, and an evaluator span.
- Stage timing provenance is explicit: Kafka-derived boundaries are labeled derived; the evaluator span is instrumented with UTC timestamps and monotonic duration.
- The evaluator span status is `completed_with_errors`; no score was fabricated after the Ollama process/CUDA failure and three bounded timeouts.
- The live pipeline trace succeeded through the evaluator stage, but judge execution did not complete successfully.

## Latency checks

- Total requests: 50.
- Confirmed cache misses: 50.
- Accidental hits: 0.
- Failed requests: 0.
- Included requests: 50.
- Excluded requests: 0.
- Total p50: 3109.722 ms.
- Total p95: 3179.057 ms.
- Cache lookup p50/p95: 30.663/66.376 ms.
- Planner p50/p95: 4.000/6.550 ms.
- Writer p50/p95: 3.000/8.100 ms.
- Reviewer p50/p95: 3.000/6.550 ms.
- Queue wait p50/p95: 3061.381/3081.447 ms.
- Evaluation timing: unavailable for the 50-request experiment because per-request evaluation was not executed. The separate single-trace evaluator span is not substituted into the latency distribution.
- Evaluation p50/p95: unavailable; no evaluation latency values were fabricated.

Percentiles use linear interpolation on sorted values at `(n-1) * p / 100`. Durations use `time.perf_counter_ns`; timestamps use UTC ISO-8601 `Z`. Queue wait is the residual after observable Planner, Writer, and Reviewer intervals. The dominant observable contributor is queue wait; further Kafka scheduling/worker profiling is required.

Evidence: `raw/latency_50_cache_misses.jsonl` and `raw/latency_summary.json`.

## Dashboard checks

- Dashboard import check: passed during Phase 4.
- Streamlit startup check: passed during Phase 4; local health endpoint returned `ok`.
- Offline dashboard tests: 8/8 passed.
- Trace ordering test: passed.
- Cache-hit/cache-miss display test: passed.
- Evaluation-page loading test: passed, including the live trace with unavailable evaluator scores.

## Part 2 live evaluator checks

- Live trace ID, also used as `correlation_id`: `hw10-live-e2e-eval-fdc655292734`.
- Live request status: HTTP 200, semantic-cache miss, complete observed path through `s8844_final`.
- Planner, Writer, and Reviewer/final payloads were captured from Kafka records; no worker or envelope was changed.
- GEval criteria attempted: Plan Quality, Writer Helpfulness, Final Answer Helpfulness, and Final-vs-Draft Improvement.
- Evaluation status: `completed_with_errors`.
- Model/settings: local Ollama `qwen3:8b`, endpoint `http://127.0.0.1:11434`, temperature 0, seed 8844, prompt version `hw10-live-geval-v1`, timeout 180 seconds.
- Plan Quality: blocked by recorded Ollama process/CUDA initialization error.
- Writer Helpfulness: bounded timeout; score unavailable.
- Final Answer Helpfulness: bounded timeout; score unavailable.
- Final-vs-Draft Improvement: score unavailable because the required scores were unavailable.
- Unavailable scores were not replaced with 0 or 1.
- Evidence: `raw/end_to_end/live_evaluation_trace.json`.
- No live evaluator score, reason, or improvement value was inferred from the Writer/final text.

## Screenshot capture and verification

An earlier capture attempt against the running local Streamlit dashboard was blocked because the browser access host and local browser URL could not be verified. A subsequent verified local capture succeeded for all five requested views. No historical HW1–HW9 screenshots were copied or reused.

| View | Screenshot path | Format | Dimensions | Caption/reference |
|---|---|---|---:|---|
| Summary | `screenshots/hw10_summary.png` | PNG | 2560×1440 | Figure 1 in `report.md` |
| Evaluation | `screenshots/hw10_evaluation.png` | PNG | 2560×1440 | Figure 2 in `report.md` |
| Cache-hit Trace Lookup | `screenshots/hw10_trace_cache_hit.png` | PNG | 2560×1440 | Figure 3 in `report.md` |
| Cache-miss Trace Lookup | `screenshots/hw10_trace_cache_miss.png` | PNG | 2560×1440 | Figure 4 in `report.md` |
| Failed Trace Lookup | `screenshots/hw10_trace_failed.png` | PNG | 2560×1440 | Figure 5 in `report.md` |

Image validation confirmed that all five files exist, decode successfully as PNG, and have the expected 2560×1440 dimensions. The screenshots are referenced with relative `screenshots/...` paths and each has a descriptive caption in `report.md`.

## Evidence classification

- **Live:** service health, authenticated endpoint, three Phase 5 traces, the new complete end-to-end trace, 50 confirmed semantic-cache misses, stage timings, and the local Ollama evaluation attempts.
- **Historical:** existing HW9 warm-cache evidence used by dashboard summary where identified by the dashboard.
- **Offline:** frozen case provenance, manual-label file validation, judge-statistics aggregation, dashboard tests, and report consistency checks.
- **Unavailable:** per-request evaluation timing and all four live single-trace GEval scores after recorded model errors/timeouts.
- **Blocked historical attempt:** the first Streamlit screenshot attempt because the browser URL could not be verified.
- **Blocked live evaluation:** all four live GEval criteria were attempted, but Ollama/CUDA initialization and judge timeouts prevented usable scores.
- **Blocked PDF visual inspection:** the regenerated 11-page PDF could not be re-inspected page-by-page because Edge launched with an application error and the browser access host was unavailable; structural checks passed.
- **Live dashboard capture:** five genuine HW10 PNG screenshots were subsequently captured and verified.

## Final Git status

The repository remains on `hw6-development`. Existing pre-Phase-6 modified and untracked files were preserved. HW10 report artifacts are new HW10 files only. No HW1–HW9 file, frozen evaluation input, dependency file, worker, compose file, or unrelated pre-existing file was intentionally modified. No files were staged, committed, or pushed.

The final status command used was:

```powershell
git -c safe.directory=C:/Projects/data260-8844 status --short --branch
```
