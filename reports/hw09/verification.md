# HW9 Verification

**Date:** November 8, 2026<br>
**Branch:** `hw6-development`<br>
**Repository:** `C:\Projects\data260-8844`

## Provenance boundary

The fixed case file was selectively committed before the compliant sweep. No unrelated file was staged:

```powershell
git -c safe.directory=C:/Projects/data260-8844 diff --cached --name-only
git -c safe.directory=C:/Projects/data260-8844 commit -m "Freeze HW9 cache cases before final sweep"
git -c safe.directory=C:/Projects/data260-8844 show -s --format="%H%n%aI%n%s" HEAD
```

Observed commit: `a67fda24dcfd4c92851c380464da9be180dc4898`, `2026-11-08T00:51:10-08:00`. Metadata and SHA-256: `cases/cache_cases_provenance.json`.

## Services and Redis vector index

```powershell
Start-Process -FilePath "C:\Program Files\Docker\Docker\Docker Desktop.exe" -WindowStyle Hidden
docker compose -p data260-hw8 -f docker-compose.hw08.yml -f docker-compose.hw09.yml config --services
docker compose -p data260-hw8 -f docker-compose.hw08.yml -f docker-compose.hw09.yml up -d --no-build hw08-kafka hw08-entity-worker hw08-api hw08-planner hw08-writer-1 hw08-writer-2 hw08-reviewer hw09-redis
docker exec data260-hw8-hw09-redis-1 redis-cli MODULE LIST
docker exec data260-hw8-hw09-redis-1 redis-cli FT._LIST
docker compose -p data260-hw8 -f docker-compose.hw08.yml -f docker-compose.hw09.yml ps
```

Observed: Docker `29.7.2`; Kafka and Redis healthy; RediSearch version `2.10.20`; MySQL80 running. Planner/Reviewer initially raced Kafka after restart and were restarted only after Kafka became healthy.

Live vector proof:

```powershell
docker run --rm --network data260-hw8_default -e HW9_REDIS_HOST=hw09-redis -e HW9_REDIS_PORT=6379 -e PYTHONPATH=/app/code -v "C:\Projects\data260-8844:/app" -w /app data260-hw8-hw08-api sh -lc "pip install -q redis==6.4.0 && python code/run_hw09_vector_check.py"
```

Observed: index exists; 2 entries inserted; KNN similarity `1.0`; orthogonal similarity `0.0` rejected. Evidence: `raw/vector_index_live_final.json`.

## View-count migration and reversible 25-access run

```powershell
docker exec data260-hw9-app python /app/code/migrate_hw09_view_count.py
docker exec -e PYTHONPATH=/app:/app/code:/app/code/web_application data260-hw9-app python /app/code/run_hw09_counter_live.py
```

Observed: column already existed; accesses 1–25 completed; MySQL synchronized at 10 and 20; original value restored and scoped key deleted. Evidence: `raw/counter_live_final.json`.

## Authenticated endpoint commands

The following is the recorded pattern for the historical reader/writer/moderator endpoint run; token values were generated at runtime and were not stored.

```powershell
$token = docker exec data260-hw9-app python -c "from auth_hw7 import create_access_token; print(create_access_token('vikki1','reader'))"
$headers = @{ Authorization = "Bearer $token" }
$body = @{ question = 'Which package versions are affected?'; correlation_id = 'live-first-8844' } | ConvertTo-Json -Compress
Invoke-RestMethod -Uri http://127.0.0.1:8745/api/agent/ask -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 180
```

For writer and moderator, the recorded run used `create_access_token('vikki2','writer')` and `create_access_token('vikki3','moderator')`. The paraphrase was `What versions of the package are impacted?`; the different request used `X-Correlation-ID=live-header-correlation-8844` and `Which maintainer published the patched release?`.

Observed: unauthenticated 401; all roles 200; first miss `36,177.985 ms`; duplicate hit `24.930 ms`, similarity `1.0`; paraphrase hit `72.601 ms`, similarity `0.93005`; different miss similarity `0.489112`. Every current warm response contains all seven contract fields. Evidence: `raw/endpoint_live.json` and `raw/warm_cache_10_query_final.json`.

Application logging now emits `HW9 semantic cache hit similarity=<score>` for hits and `HW9 semantic cache miss similarity=<score>` for misses; cache hits still return before Kafka execution.

## Warm-up and 10-query run

```powershell
$body = @{model='qwen3:8b'; prompt='Reply only: ready'; stream=$false; keep_alive='10m'; options=@{num_predict=1}} | ConvertTo-Json -Depth 4
Invoke-RestMethod -Uri http://127.0.0.1:11434/api/generate -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 60
docker exec -e PYTHONPATH=/app:/app/code:/app/code/web_application data260-hw9-app python /app/code/run_hw09_warm_cache.py
```

The first 180-second warm attempt timed out while loading, but `ollama ps` showed `qwen3:8b` loaded; the one-token request then completed. One endpoint warm-up (`26,040.415 ms`) was excluded. Observed timed run: 10 total, 6 cached, 4 misses, 60% hit rate, cached mean `21.844 ms`, non-cached mean `3,075.926 ms`.

## Timeout, Kafka outage, and recovery

Recorded reviewer-timeout sequence:

```powershell
docker compose -p data260-hw8 -f docker-compose.hw08.yml -f docker-compose.hw09.yml stop hw08-reviewer
$token = docker exec data260-hw9-app python -c "from auth_hw7 import create_access_token; print(create_access_token('vikki1','reader'))"
$headers = @{ Authorization = "Bearer $token" }
$body = @{ question = 'Timeout probe unique 8844: explain a nonexistent package sentinel.'; correlation_id = 'live-timeout-8844' } | ConvertTo-Json -Compress
try {
    Invoke-WebRequest -Uri http://127.0.0.1:8745/api/agent/ask -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 30 | Out-Null
} catch {
    if ($_.Exception.Response) { "timeout_status=$([int]$_.Exception.Response.StatusCode)" }
}
docker compose -p data260-hw8 -f docker-compose.hw08.yml -f docker-compose.hw09.yml start hw08-reviewer
```

Observed HTTP 504 after the configured three-second timeout. Recorded Kafka outage/recovery sequence:

```powershell
docker compose -p data260-hw8 -f docker-compose.hw08.yml -f docker-compose.hw09.yml stop hw08-kafka
$token = docker exec data260-hw9-app python -c "from auth_hw7 import create_access_token; print(create_access_token('vikki1','reader'))"
$headers = @{ Authorization = "Bearer $token" }
$body = @{ question = 'Unavailable Kafka probe unique 8844.'; correlation_id = 'live-kafka-unavailable-8844' } | ConvertTo-Json -Compress
try {
    Invoke-WebRequest -Uri http://127.0.0.1:8745/api/agent/ask -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 30 | Out-Null
} catch {
    if ($_.Exception.Response) { "kafka_unavailable_status=$([int]$_.Exception.Response.StatusCode)" }
}
docker compose -p data260-hw8 -f docker-compose.hw08.yml -f docker-compose.hw09.yml start hw08-kafka
docker inspect data260-hw8-hw08-kafka-1 --format "{{.State.Health.Status}}"
docker compose -p data260-hw8 -f docker-compose.hw08.yml -f docker-compose.hw09.yml restart hw08-entity-worker hw08-planner hw08-writer-1 hw08-writer-2 hw08-reviewer
```

Observed HTTP 503 during outage and healthy Kafka after recovery. Complete historical results are in `raw/endpoint_live.json`.

## Threshold sweep after provenance commit

```powershell
docker exec -e PYTHONPATH=/app:/app/code:/app/code/web_application data260-hw9-app python -m hw09.measure_cache_cases --cases /app/reports/hw09/cases/cache_cases.yaml --output /app/reports/hw09/raw/cache_thresholds_compliant.json
```

Observed costs: 45, 48, 50, 48, 45. At 0.95: 15 hits, 25 misses, 4 false hits, 37.5% hit rate, 10% false-hit rate, `17.927 ms` mean search latency. Evidence: `raw/cache_thresholds_compliant.json` and `raw/false_hit_compliant.json`.

## Reversible content-change stale demo

```powershell
docker exec -e PYTHONPATH=/app:/app/code:/app/code/web_application data260-hw9-app python /app/code/run_hw09_stale_demo.py
```

Observed report 5005: Critical → Low; pre-invalidation query returned stale Critical hit; version 3 → 4 rejected the old entry; regenerated answer used Low; database restored to Critical. The script restores inside `finally`. Evidence: `raw/stale_answer_content_final.json`.

## Lesson validation and variants

```powershell
python code/run_hw09_lesson_demo.py
python code/run_hw09_validation.py
python code/run_hw09_agent_variants.py
```

Observed validation: target failure improved; other failures stayed unchanged; all previously correct cases stayed correct; unrelated unsupported regressions remained zero; the alpha lesson was retained. A controlled harmful candidate was rejected because it worsened failures, broke a previously correct case, and added an unsupported unrelated answer. The revision evidence records `revision_generated_by=AnsweringAgent.answer`; the evaluator supplied feedback but its correction string was not copied into the response. Final variants: Baseline 7/10, Evaluator Repair 10/10, Lesson Memory 8/10, Validated Improvement 8/10. Evidence: `raw/lesson_reuse_final.json`, `raw/validation_before_after_final.json`, `raw/revision_sequence_final.json`, `raw/agent_variants_final.json`, and `raw/agent_variant_summary_final.json`.

## Final checks

```powershell
python -m compileall -q code/hw09 code/test_hw09_core.py code/test_hw09_agents.py code/run_hw09_agent_variants.py code/run_hw09_lesson_demo.py code/run_hw09_validation.py
docker run --rm -v "C:\Projects\data260-8844:/app" -w /app -e PYTHONPATH=/app/code data260-hw8-hw08-api python -m unittest code.test_hw09_core code.test_hw09_agents
docker compose -p data260-hw8 -f docker-compose.hw08.yml -f docker-compose.hw09.yml config
git -c safe.directory=C:/Projects/data260-8844 diff --check
git -c safe.directory=C:/Projects/data260-8844 status --short --branch
```

The dependency-complete container reported 12/12 HW9 unit tests passing, including a direct assertion that attempt two remains `REVISE` without feedback and becomes `PASS` with evaluator feedback. Host Python 3.14 compilation succeeded, but the host-only unit command is blocked because that interpreter does not have SQLAlchemy; no host-test success is claimed. Ruff is not installed, so no Ruff success is claimed. The original `.venv` references a removed Python 3.12 executable. Six genuine terminal captures with the student name and SID4 are stored as `screenshots/04_part1_counter_terminal.png` through `screenshots/09_part4_lesson_validation_terminal.png`; their `_cropped.png` derivatives remove only unused space and preserve source pixels exactly. The report uses the readable crops, explicit Letter margins and 14/12/11 pt CSS sizing, and browser headers/footers disabled.
