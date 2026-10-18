# DATA260 HW6 55-line file-memory fixture
Last modified: 2026-10-17T00:00:00Z

## Preferences
- Preference: explanation style is concise.
- Preference: explanation style is concise.
- Preference: explanation style is detailed.
- Preference: study topic is distributed systems.
- Preference: study topic is distributed systems.
- Preference: comments should explain why code exists.

## Goals
- Goal: keep the project modular and testable.
- Goal: keep the project modular and testable.
- Goal: prioritize fast responses.
- Goal: prioritize careful correctness.
- Goal: preserve historical HW1-HW5 evidence.
- Goal: preserve historical HW1-HW5 evidence.
- Goal: record measured latency honestly.

## Project constraints
- Constraint: do not expose credentials.
- Constraint: do not expose credentials.
- Constraint: use a local model for reproducible tests.
- Constraint: use a hosted model for every test.
- Constraint: preserve raw messages.
- Constraint: keep short-term memory bounded.
- Constraint: compare measured and estimated tokens separately.

## Ordinary memory
- Note 01: the vulnerability-reporting domain remains part of the application.
- Note 02: MySQL remains responsible for existing relational data.
- Note 03: MongoDB stores HW6 memory collections separately.
- Note 04: messages preserve raw conversation evidence.
- Note 05: summaries compress older conversation context.
- Note 06: episodes store durable facts and embeddings.
- Note 07: session summaries are user-scoped.
- Note 08: lifetime summaries are less frequent.
- Note 09: commands are bounded and user-scoped.
- Note 10: file memory is separate from MongoDB memory.
- Note 11: fixed seeds make offline tests repeatable.
- Note 12: raw evidence must not be overwritten.
- Note 13: screenshots require human review.
- Note 14: local CPU inference can be slow.
- Note 15: the embedding model has 384 dimensions.
- Note 16: episodic retrieval uses bounded top-k results.
- Note 17: summaries retain older project goals.
- Note 18: contradictions require human review.
- Note 19: duplicate facts should not multiply indefinitely.
- Note 20: this fixture contains no secrets.
- Note 21: this fixture is for offline testing only.
- Note 22: report metrics distinguish observations from estimates.
- Note 23: failed attempts remain visible in the evidence.
- Note 24: user scoping prevents memory leakage.
- Note 25: review history keeps consolidation auditable.
