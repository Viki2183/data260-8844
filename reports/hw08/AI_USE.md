# DATA260 HW8 AI Use Statement

Student: Vrishin KunnathamParambath | SID4: 8844

Repository: https://github.com/Viki2183/data260-8844  
Collaborators with repository access: `Sbnikitha` and `supriyaselvanganesan`  
Final tagged tree: https://github.com/Viki2183/data260-8844/tree/hw8  
HW8 artifact commit: `bda1110c82293aac22d16951f35cff5b368f825a`  
HW8 tagged packaging commit: `6dcadc68b88d5c8473978c52e7953ddb7020ea81` (`hw8` tag). The hashes differ because packaging contains the final report/PDF metadata.

## (1) What I used AI for versus what I did myself

I used AI/Codex for repository inspection, assignment reading, HW8-only code
implementation support, offline test design, controlled local Kafka commands,
evidence organization, screenshot preparation, and report/PDF preparation. I
selected the test data and scope, approved live operations, reviewed source
changes, inspected the raw evidence, and made the final submission decisions
myself.

## (2) One incorrect output and one independent verification

The Kafka poison evidence initially omitted the required post-DLT check that a
later valid task was processed. I independently verified the corrected live2
DLT run and the separate fix-disabled unbounded-loop run. I also checked the
live Docker logs, Kafka topic metadata, JSONL/CSV evidence, offline tests, and
the final verification output.

## (3) How I detected the problem

Comparing the poison harness output with the Writer log showed that the
later-valid message needed an explicit observation after DLT publication. The
fix-disabled environment flag also had to be set before container creation so
the unbounded-loop behavior was measured correctly.

## (4) What I changed and why it works now

I ran the bounded DLT path with the later-valid check, captured the Writer and
topic logs, and kept the before-fix loop in a separate evidence file. I added
the isolated FastAPI service and
`homework_demo.py` live evidence, structured full-stage agent logs, the
post-DLT later-valid check, and normalized consumer-death evidence that records
the real Writer crash, Kafka redelivery, output, commit, and restart. I also
captured separate fix-disabled duplicate, consumer-death, and poison runs so
the comparison table uses measured before/after behavior. The verifier now
validates the corrected live2 evidence paths and records the configuration and
packaging metadata.

No hidden chain-of-thought is stored or reported.
