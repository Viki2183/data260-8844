# DATA260 Homework 8

Student: Vrishin KunnathamParambath  
SID4: 8844  
Domain: open-source package vulnerabilities  
Repository: https://github.com/Viki2183/data260-8844  
Working branch: `hw6-development`  
Historical HW7 tag: `hw7`, commit `238163e119dd9fc83c945f287e109d6e2d024fec`  
Assigned domain: Open-source package vulnerabilities  
Collaborators with repository access: `Sbnikitha` and `supriyaselvanganesan`.  
HW8 artifact commit: `bda1110c82293aac22d16951f35cff5b368f825a`. The final `hw8` tag is created on the packaging metadata commit after this artifact commit.

This report uses the official HW8 requirements and the preserved HW8 source,
raw evidence, screenshots, run log, metrics, and verification files. Existing
HW1-HW7 code, reports, evidence, timestamps, branches, tags, and history are
preserved.

## Configuration and hardware

Kafka image: `apache/kafka:3.9.2`.  
Compose project: `data260-hw8`.  
`PORT_BASE=8744` (`8000 + (8844 mod 900)`).  
`PREFIX=s8844`.  
Host bootstrap: `localhost:29092`.  
Docker bootstrap: `hw08-kafka:9092`.  
Database configuration: `s8844_rel`; MySQL was not used in the HW8 experiments.  
Model configuration: `qwen3:8b` at `127.0.0.1:11434`; deterministic HW8 agent
behavior was model-free and Ollama was not used.  
`SEED=8844`.  
`VERIFY_SEED=268844`.  
`DOMAIN_ID=4` (`8844 mod 8`); domain: Open-source package vulnerabilities.  
Hardware/runtime: Windows host, Docker Desktop, Linux x86_64 containers,
12 CPUs, WSL2.

## AI use and verification boundary

I used AI/Codex for repository inspection, reading the official assignment,
HW8-only implementation support, offline testing, controlled local Kafka
testing, raw-evidence organization, screenshot preparation, and report/PDF
preparation. I selected the test data, approved the execution scope, reviewed
the source and measured evidence, and retained responsibility for submission
decisions.

One unsuitable result was the first hand-built PDF: it opened as a blank
document. I detected that problem by opening the PDF and checking its rendered
pages, then replaced the renderer with Chrome headless output and verified the
resulting searchable PDF. I also independently checked the live JSONL, service
logs, topic metadata, offline tests, verification output, screenshots, and PDF
links. No hidden chain-of-thought is stored or reported.

The corrected implementation uses a real isolated FastAPI service, a live
`homework_demo.py` host client, structured worker/pipeline logs, a post-DLT
later-valid-message check, and a normalized consumer-death evidence file. The
changes work because the report and verifier now point to the corrected live2
evidence rather than the stale pre-correction paths. Historical before-fix
runs were not captured, so no before-fix measurement is invented.

## Part 1 - Kafka entity request/response

### Implementation

The API/client publishes canonical envelopes to exactly
`s8844_entity_requests`. The entity worker consumes requests, validates the
vulnerability-report payload, uses a worker-local Python dictionary, generates
UUIDs for `CREATE_ENTITY`, and publishes responses to exactly
`s8844_entity_responses`.

`CREATE_ENTITY` and `GET_ENTITY` preserve `correlation_id`. The client waits
only for the matching response. The worker uses manual processing behavior and
does not add automatic request retries.

### Entity validation

The pure validator requires non-empty `packageName`, `vulnerabilityId`,
`submitterEmail`, and `vulnerabilityDescription`; valid email syntax; a
description of at least 26 characters; severity in `Critical`, `High`,
`Medium`, or `Low`; `termsAccepted=true`; and a non-negative integer
`affectedVersionsCount`.

### Live status evidence

Source: `raw/part1_create_get.jsonl`, `raw/part1_homework_demo_live2.jsonl`,
`raw/part1_service_logs.log`, `raw/part1_docker_ps.txt`,
`raw/part1_topic_commands.log`, and `raw/environment.json`.

| Check | Recorded result |
|---|---|
| Kafka health | healthy |
| Entity worker | running |
| Entity topics | exact required topics present |
| CREATE_ENTITY | successful; UUID generated |
| GET_ENTITY | successful; returned entity matched CREATE |
| Correlation IDs | preserved |
| Automatic request retries | 0 |

Measured corrected-demo CREATE correlation: `hw8-8844-live2-create-001`.  
Measured corrected-demo GET correlation: `hw8-8844-live2-get-001`.  
Generated UUID: `4e9d8b15-a4de-415c-82f0-e5f67123d12d`.

The corrected live demo generated UUID
`4e9d8b15-a4de-415c-82f0-e5f67123d12d` and returned these entity fields:
`packageName=requests`, `vulnerabilityId=CVE-2026-0001`,
`submitterEmail=student@example.com`, `severity=High`,
`affectedVersionsCount=2`, `termsAccepted=true`, and the recorded
vulnerability description. The demo also recorded validation failure,
unknown entity, and unknown operation responses, each echoing its
`correlation_id`.

### Message envelope

Requests contain `message_type`, `correlation_id`, `operation`, `reply_to`,
`data`, `attempt`, `timestamp`, and `metadata`; GET requests also carry
`entity_id`. Responses preserve `correlation_id`, `operation`, `attempt`,
`data`, `entity_id` when applicable, `success`, and safe error metadata.

The actual live request/response schemas and values are in
`raw/part1_homework_demo_live2.jsonl`; worker receive/reply/commit, API
publish/receipt, the worker readiness line, and the FastAPI startup line are in
`raw/part1_service_logs.log`. The Docker service snapshot is in
`raw/part1_docker_ps.txt`, and the topic creation/partition commands are in
`raw/part1_topic_commands.log`.

The correlation flow is: `homework_demo.py` -> FastAPI on port 8744 ->
`s8844_entity_requests` -> entity worker dictionary/UUID operation ->
`s8844_entity_responses` -> matching FastAPI response. The same envelope
fields—`correlation_id`, `reply_to`, `operation`, and `data`—are visible on
both sides of each request/response pair.

## Part 2 - Planner, Writer, and Reviewer pipeline

### Process and topic separation

Planner, Writer, and Reviewer are separate processes:

| Process | Input topic | Output topic |
|---|---|---|
| Planner | `s8844_inbox` | `s8844_tasks` |
| Writer | `s8844_tasks` | `s8844_drafts` |
| Reviewer | `s8844_drafts` | `s8844_final` |

### Live status evidence

Source: `raw/part2_agent_journey.jsonl`, `raw/part2_agent_flow.log`,
`raw/part2_agent_demo_live2.jsonl`, `raw/part2_agent_pipeline_logs.log`, and
`raw/part2_topic_commands.log`.

The live corrected run is also recorded in `raw/part2_agent_demo_live2.jsonl`,
`raw/part2_agent_pipeline_logs.log`, and `raw/part2_topic_commands.log`.

One deterministic message with correlation ID
`hw8-8844-agent-journey-001` traversed:

`s8844_inbox -> s8844_tasks -> s8844_drafts -> s8844_final`

The corrected live sender published one input with correlation ID
`hw8-8844-agent-live2-001` to `s8844_inbox` partition 0 offset 0. The observed
journey then used `s8844_tasks` partition 1 offset 0, `s8844_drafts` partition 1
offset 0, and `s8844_final` partition 1 offset 0. The final JSON message had
`status=approved` and an `answer` field. Ollama, MySQL, and JMeter were not used.

Kafka provides durable topic boundaries, consumer-group coordination, offsets,
and independent process failure domains.

The Planner code transforms the input into a plan, the Writer transforms the
plan into a draft, and the Reviewer transforms the draft into an answer with
`status=approved`. Each stage logs receipt, output publication, and offset
commit. This gives the instructor a complete observable journey rather than
only a final answer. Kafka also lets each process restart independently,
assigns partitions through consumer groups, and makes the handoff boundaries
inspectable through topic/partition/offset metadata.

## Part 3 - Failure handling and idempotency

### Duplicate delivery

Source: `raw/part3_duplicate_delivery.jsonl`.

The exact logical CREATE message was intentionally replayed once. The original
and replay returned UUID `150109d0-99fa-42d9-92e9-ca74c7f01c91`. The replay was
marked `duplicate=true`, and the derived entity-store count remained
`0 -> 1 -> 1`. The count is derived because no runtime store-count endpoint
exists. Correlation ID `hw8-8844-duplicate-001` was preserved.

### Consumer death and redelivery

Source: `raw/part3_consumer_death_live2.jsonl`,
`raw/part3_consumer_death_live2_writer_logs.log`,
`raw/part3_consumer_death_live2_restart.log`, and
`raw/part3_consumer_death_live2_harness.jsonl`.

The non-competing harness did not join `s8844-writer`. Writer 1 received the
task and crashed at the documented pre-commit point. The container termination
was observed before it was recreated; the exit code was not captured before
recreation and is therefore not claimed here. The offset was not committed.
Kafka redelivered the same topic, partition, and offset to Writer 2. Writer 2
published to `s8844_drafts` and committed the input offset after successful
output. The restart log shows Writer 1 becoming ready again. Readiness used
`aiokafka`; producer and application retry/resend counts were zero.

### Poison messages and dead letter

Source: `raw/part3_poison_dead_letter_live2.jsonl`,
`raw/part3_poison_writer_logs_live2.log`, and
`raw/part3_poison_topic_live2.log`.

One intentional poison fixture produced bounded failures at attempts 1, 2,
and 3. The final attempt published the original message plus safe failure
metadata to exactly `s8844_dead_letter`. The source offset was committed only
after DLT publication succeeded. The source topic, source partition and
offset, DLT partition and offset, correlation ID, attempts, and error
classification were recorded.

The corrected harness also published one later valid task after the DLT commit.
It reached `s8844_drafts` and recorded `blocked_by_poison=false`, so the later
message was not blocked. This is a separate corrected live2 result; the older
poison record remains preserved unchanged.

### Code excerpts

Idempotency uses the message type, correlation ID, operation, and entity ID:

```python
def idempotency_key(message):
    data = message.get("data")
    data_entity_id = data.get("entity_id") if isinstance(data, Mapping) else None
    return (str(message.get("message_type", "")),
            str(message.get("correlation_id", "")),
            str(message.get("operation", "")),
            str(message.get("entity_id") or data_entity_id or ""))
```

The entity worker publishes the response and then commits the source record:

```python
metadata = await producer.send_and_wait(response_topic, serialize_message(response))
await consumer.commit()
```

Poison handling uses an explicit fixture marker, attempts 1 through 3, and
publishes the DLT record before committing:

```python
failures = poison_attempt_records(message, error_type=error_type, max_attempts=3)
dead_letter = dead_letter_message(message, error_type=error_type, ...)
await producer.send_and_wait(DEAD_LETTER_TOPIC, serialize_message(dead_letter))
await consumer.commit()
```

The ordering key is the deterministic entity key `entity-268844`; unkeyed
messages pass `None` as the Kafka key.

### Before/after failure table

| Case | Before HW8 mechanism | After HW8 mechanism | Evidence |
|---|---|---|---|
| Duplicate delivery | Repeated delivery could create a second entity. | Same idempotency identity returns the cached response; UUID and count remain unchanged. | `part3_duplicate_delivery.jsonl` |
| Consumer death | No historical before-fix run was captured; no measured before-fix claim is made. | Uncommitted work is redelivered; surviving Writer commits after output. | `part3_consumer_death_live2.jsonl` and restart/writer logs |
| Poison message | No historical before-fix run was captured; no measured before-fix claim is made. | Bounded attempts end in `s8844_dead_letter`; source commits after DLT publication and a later valid message is processed. | `part3_poison_dead_letter_live2.jsonl` and writer log |
| Ordering | In-process order was local to the execution path. | Kafka order is measured per partition; keyed related work is colocated. | Four ordering JSONL/CSV files |

## Part 4 - Deterministic ordering experiment

Source files:

- `raw/part3_ordering_unkeyed.jsonl`
- `raw/part3_ordering_unkeyed.csv`
- `raw/part3_ordering_keyed.jsonl`
- `raw/part3_ordering_keyed.csv`

The experiment used `VERIFY_SEED=268844`, exactly 20 related messages per run,
exactly two partitions, and two Writer consumers in the same
`s8844-writer` group. Every record included sequence, correlation ID, key,
topic, partition, offset, Writer, produced/processed timestamps, and processing
order. No retry or resend occurred.

| Run | Measured result |
|---|---|
| Unkeyed | 20/20; no Kafka key; partitions 0 and 1; both Writers observed. p0 sequence by offset `[0,3,4,6,7,9,10,11,12,15,17,18,19]`; p1 `[1,2,5,8,13,14,16]`. |
| Entity-keyed | 20/20; key `entity-268844`; all messages on partition 0; Writer 1 observed; sequence and offset order were both 0 through 19. |

The measured result demonstrates partition-local ordering. Kafka guarantees
ordering within a partition, not global ordering across partitions. No global
ordering claim is made.

## Part 5 - Two Kafka benefits and two new responsibilities

| Item | Explanation |
|---|---|
| Benefit 1 - independent scaling | Planner, Writer, and Reviewer are separate consumers and can scale or restart independently through Kafka consumer groups. |
| Benefit 2 - decoupled failure | A Writer crash before commit does not lose the task; Kafka redelivers it to the surviving Writer. Topic boundaries also isolate the entity API, planner, writer, and reviewer. |
| Responsibility 1 - idempotency and DLT | The application must detect duplicate delivery, bound poison attempts, publish `s8844_dead_letter`, and commit only after successful output/DLT publication. |
| Responsibility 2 - ordering and operations | The application must choose keys, understand partition-local rather than global ordering, manage listeners/topics/groups, and verify readiness/cleanup. |

## Part 6 - Verification and screenshot evidence

`verification.json` records homework number, SID4, the packaging commit hash,
model/configuration, `PORT_BASE`, `PREFIX`, `DOMAIN_ID`, `SEED`,
`VERIFY_SEED`, named checks, and pass/fail values. It records
`offline_overall_pass=true`, successful entity smoke,
successful Planner/Writer/Reviewer journey, duplicate delivery, consumer death,
poison/DLT, and both ordering runs. The final overall result is `true`.

| Screenshot | Requirement demonstrated |
|---|---|
| `01_docker_kafka_health.png` | Docker/Kafka health and listeners |
| `02_entity_create_get.png` | Entity CREATE/GET success |
| `03_entity_correlation_flow.png` | Correlation ID preservation |
| `04_entity_complete_sequence.png` | CREATE -> UUID -> GET sequence |
| `05_agent_journey.png` | Planner -> Writer -> Reviewer journey |
| `06_agent_final.png` | Final agent result |
| `07_duplicate_delivery.png` | Duplicate idempotency and unchanged UUID/count |
| `08_consumer_death.png` | Crash, redelivery, output, and commit |
| `09_poison_dead_letter.png` | Attempts, DLT publication, and source commit |
| `10_ordering_unkeyed.png` | Unkeyed ordering run |
| `11_ordering_keyed.png` | Entity-keyed ordering run |
| `12_verification_summary.png` | Verification summary |
| `13_live_docker_ps.png` | Captured Docker/Kafka/API service status |
| `14_live_homework_demo.png` | Captured `homework_demo.py` run and error cases |
| `15_live_part1_flow.png` | Captured FastAPI/entity-worker flow and readiness logs |
| `16_live_agent_pipeline.png` | Captured Planner/Writer/Reviewer stage logs |
| `17_live_poison_later_valid.png` | Captured poison attempts, DLT, commit, and later-valid output |
| `18_live_consumer_death_restart.png` | Captured crash, redelivery, output, commit, and restart |

Every screenshot displayed in the report is labeled:
`Student: Vrishin KunnathamParambath | SID4: 8844`.

## Tests, limitations, and preservation

Offline validation and HW8 verification passed. The corrected controlled live
results are preserved in HW8 raw evidence. Historical before-fix runs were not
captured, so the failure table labels those rows as a comparison boundary and
does not present hypothetical behavior as measured data. No hidden
chain-of-thought, passwords, hashes, JWTs, API keys, tokens, or `.env` values
are included.

All HW1-HW7 files, reports, evidence, timestamps, branches, tags, commits, and
history remain preserved. No historical evidence was overwritten.

## Git packaging and submission status

Current branch: `hw6-development`.  
Existing HW7 tag: `hw7`.  
Existing HW7 tagged commit: `238163e119dd9fc83c945f287e109d6e2d024fec`.  
HW8 artifact commit: `bda1110c82293aac22d16951f35cff5b368f825a`.  
HW8 tag: `hw8`, created on the final packaging metadata commit.  
GitHub push: performed after local verification.
