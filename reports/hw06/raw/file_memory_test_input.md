# DATA260 HW6 File Memory Test Input

Last modified: 2026-10-17T00:00:00Z

## Preferences
- Preference: explanation style is concise.
- Preference: explanation style is concise.
- Preference: explanation style is detailed.
- Preference: study topic is distributed systems.
- Preference: study topic is distributed systems.
- Preference: comments should explain why code exists.
- Preference: comments should explain why code exists.

## Goals
- Goal: keep the project modular and testable.
- Goal: keep the project modular and testable.
- Goal: preserve historical HW1-HW5 evidence.
- Goal: preserve historical HW1-HW5 evidence.
- Goal: measure latency and token usage.
- Goal: measure latency and token usage.
- Goal: document the API clearly.
- Goal: document the API clearly.

## Ordinary project memory
- Note 01: the vulnerability-reporting domain remains part of the application.
- Note 02: MySQL remains responsible for existing relational data.
- Note 03: MongoDB stores HW6 memory collections separately.
- Note 04: messages preserve raw conversation evidence.
- Note 05: summaries compress older conversation context.
- Note 06: episodes store durable facts and embeddings.
- Note 07: short-term context is bounded.
- Note 08: session summaries are user-scoped.
- Note 09: lifetime summaries are less frequent.
- Note 10: commands must not expose credentials.
- Note 11: /dream is non-destructive.
- Note 12: /compact preserves raw messages.
- Note 13: /memory returns bounded state.
- Note 14: /help explains safe commands.
- Note 15: local Ollama inference can be slow on CPU.
- Note 16: project-local model caches improve reproducibility.
- Note 17: verification uses fixed seeds.
- Note 18: API evidence is stored under reports/hw06.
- Note 19: raw evidence is not overwritten.
- Note 20: screenshots belong in the HW6 screenshot directory.
- Note 21: report metrics distinguish measured values from estimates.
- Note 22: unavailable recorder values remain unavailable.
- Note 23: fake tests do not contact external services.
- Note 24: MongoDB comparisons use supplied facts only.
- Note 25: the final report should explain limitations.
- Note 26: the final report should preserve failed attempts honestly.
- Note 27: the final verification is read-only.
- Note 28: the student remains responsible for explaining the code.
- Note 29: the branch is hw6-development.
- Note 30: the project uses SID4 8844.
- Note 31: the fixed seed is 8844.
- Note 32: the verification seed is 268844.
- Note 33: the embedding model has 384 dimensions.
- Note 34: normalized vectors support cosine similarity.
- Note 35: episodic retrieval is bounded by top-k.
- Note 36: all memory operations should be user-scoped.
- Note 37: commands should be explicit and bounded.
- Note 38: historical tags must remain unchanged.
- Note 39: no destructive Git commands are permitted.
- Note 40: no database writes occur during read-only verification.
- Note 41: future cleanup must be separately approved.
- Note 42: report packaging is checked independently.
- Note 43: raw messages are evidence, not disposable cache.
- Note 44: summaries should retain goals and preferences.
- Note 45: contradictions need human review.
- Note 46: duplicate facts should not multiply indefinitely.
- Note 47: file memory remains separate from MongoDB memory.
- Note 48: deterministic output makes tests repeatable.
- Note 49: consolidation should be bounded.
- Note 50: this fixture contains no secrets.
- Note 51: this fixture is for offline testing only.
