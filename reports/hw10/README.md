# DATA260 Homework 10 Phase 2 Preparation

This directory contains only HW10 preparation artifacts. Existing HW1–HW9
reports are not changed.

The 20 candidate cases use existing open-source-package-vulnerability questions
from `reports/hw09/cases/cache_cases.yaml`. Candidate Writer drafts replay the
unchanged deterministic transformation in
`code/hw08_agent_pipeline.py:transform_stage`:

`Draft based on Plan: answer {question}`

The repository contains one directly observed HW8 Planner → Writer → Reviewer
journey, but not 20 persisted Writer-message records. Therefore these are
explicitly marked as offline reconstructed candidates in `provenance.json`.
They must not be described as live Kafka observations.

`human_labels.csv` is a pending candidate file. Labels are not frozen, and no
label may be treated as authoritative until the student manually confirms the
20 rows.

`correlation_id` is the sole trace identifier. It is not accompanied by a
second request ID.
