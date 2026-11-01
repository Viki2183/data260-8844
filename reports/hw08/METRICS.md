# DATA260 HW8 Metrics

Measured Phase 4A live entity smoke:

- Kafka health: healthy.
- Entity worker: running.
- Host bootstrap: localhost:29092.
- Docker bootstrap: hw08-kafka:9092.
- Entity topics: 2 created/present; requests measured at 2 partitions and responses at 1 partition.
- CREATE_ENTITY: 1 request, successful response, UUID generated.
- GET_ENTITY: 1 request, successful response, entity matched CREATE.
- Correlation preservation: CREATE and GET both passed.
- Automatic request retries: 0.
- Planner/Writer/Reviewer, duplicate-delivery, consumer-death, poison-message, and ordering experiments: not run.

Measured Phase 4B agent journey:

- Kafka health: healthy; Planner, Writer 1, Writer 2, and Reviewer: running.
- Journey count: 1 input message; automatic retries: 0.
- Correlation ID: `hw8-8844-agent-journey-001`, preserved through all stages.
- Input: `s8844_inbox`, partition 0, offset 0.
- Planner output: `s8844_tasks`, partition 0, offset 0.
- Writer output: `s8844_drafts`, partition 0, offset 0.
- Reviewer output: `s8844_final`, partition 0, offset 0.
- Final deterministic status: `approved`.
- Ollama, MySQL, and JMeter: not used; failure, duplicate, consumer-death, poison-message, and ordering experiments: not run.

Measured Phase 5A duplicate-delivery experiment:

- Kafka health: healthy; entity worker: running.
- Original request: `s8844_entity_requests`, partition 0, offset 0.
- Intentional replay: `s8844_entity_requests`, partition 0, offset 1.
- Original response: `s8844_entity_responses`, partition 0, offset 0, success true.
- Replay response: `s8844_entity_responses`, partition 0, offset 1, success true, `duplicate: true`.
- Correlation ID preserved: `hw8-8844-duplicate-001`.
- Original and replay UUID: `150109d0-99fa-42d9-92e9-ca74c7f01c91` (same).
- Entity-store count: baseline 0, after original 1, after replay 1; derived because no runtime count endpoint exists.
- Automatic retries: 0. Consumer-death, poison-message, and ordering experiments: not run.

Measured Phase 5B consumer-death experiment:

- Services: Kafka, Writer 1, Writer 2; harness did not join `s8844-writer`.
- Readiness method: `aiokafka`; group `s8844-writer` was STABLE with both task partitions assigned.
- Published exactly one task: `s8844_tasks`, partition 0, offset 0.
- Correlation ID: `hw8-8844-consumer-death-001`, preserved through all events.
- Writer 1: receipt observed, pre-commit crash observed, container exit code 42.
- Writer 2: same `s8844_tasks` partition 0 offset 0 redelivered; output published to `s8844_drafts` partition 0 offset 0; input offset committed as 1.
- Producer/application retries: 0; producer resend count: 0; one `send_and_wait` call.
- Result: passed. Poison-message and ordering experiments: not run.

Measured Phase 5C poison/dead-letter experiment:

- Kafka health: healthy; `s8844-writer`: STABLE; Writer 1 and Writer 2 active.
- Exact topics used: `s8844_tasks`, `s8844_dead_letter`.
- One poison task: `s8844_tasks`, partition 1, offset 0; correlation ID `hw8-8844-poison-001`.
- Bounded failures: attempts 1, 2, and 3; classification `intentional_poison_fixture`.
- DLT publication: `s8844_dead_letter`, partition 0, offset 0.
- Source commit: `s8844_tasks` partition 1 committed offset 1 after DLT publication.
- Producer/application retries: 0; producer resends: 0.
- Later-valid-message check: unavailable; the harness did not include that check.
- Result: passed. Ordering experiment: not run.

Measured Phase 5D ordering experiment:

- Configuration: `VERIFY_SEED=268844`; `s8844_tasks`; exactly two partitions; two active Writers in `s8844-writer`; crash injection disabled.
- Unkeyed run: 20/20 messages; no Kafka key; partitions observed 0 and 1; Writers observed `writer-1` and `writer-2`.
- Unkeyed per-partition sequence by offset: partition 0 = `[0,3,4,6,7,9,10,11,12,15,17,18,19]`; partition 1 = `[1,2,5,8,13,14,16]`.
- Keyed run: 20/20 messages; deterministic key `entity-268844`; all messages assigned to partition 0; Writer observed `writer-1`.
- Keyed sequence by offset: partition 0 = `[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19]`.
- Correlation IDs: `ordering-268844-00` through `ordering-268844-19`; all preserved.
- Processing order and produced/processed timestamps were recorded for every message. No retries or resends occurred.
- Interpretation: measured ordering was preserved within each partition. No global ordering was assumed across partitions; Kafka guarantees partition-local ordering, not global ordering across partitions.
- Result: both ordering runs passed.

Corrected live evidence metrics:

- FastAPI service: captured startup at `http://127.0.0.1:8744`; entity worker
  readiness line captured; Docker snapshot contained Kafka, entity worker, and
  FastAPI service.
- `homework_demo.py`: one valid CREATE, one valid GET, one validation failure,
  one missing-entity failure, and one unknown-operation failure; all five
  request/response correlation IDs matched; automatic retries were 0.
- Agent live2: one input; `s8844_inbox` p0/o0 -> `s8844_tasks` p1/o0 ->
  `s8844_drafts` p1/o0 -> `s8844_final` p1/o0; final status `approved`.
- Poison live2: attempts 1, 2, and 3; DLT publication before source commit;
  later valid message reached `s8844_drafts`; `blocked_by_poison=false`;
  producer retries/resends were 0.
- Consumer-death live2: Writer 1 receipt and pre-commit crash; termination
  observed before recreation; same p0/o0 redelivered to Writer 2; output and
  commit observed; Writer 1 restart readiness observed; producer retries and
  resends were 0.
- Historical before-fix runs were not captured and are not represented as
  measured results.

