# Consolidated file memory
Generated at: 2026-10-18T05:30:53.070798+00:00

## Retained facts
### Design Goals
- Design Goals: Modular, testable, easy-to-understand system
### Embedding model
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`
### Focus Areas
- Focus Areas: Reliability, clear documentation
### General
- `/memory` reads MongoDB memory and file-based `MEMORY.md` metadata for the scoped user and session. | `/compact` consolidates file memory when the 40-line or 24-hour rule is triggered and preserves raw MongoDB messages. | `/dream` adds verified, non-sensitive durable facts to `MEMORY.md`; duplicate facts are skipped and contradictions remain in `Needs review`. | `/help` explains all available memory commands and their safety limits. | No contradictions detected.
### Generated at
- Generated at: 2026-10-18T05:11:15.933558+00:00 | Generated at: 2026-10-18T05:10:50.372212+00:00 | Generated at: 2026-10-18T04:44:36.182601+00:00 | Generated at: 2026-10-18T04:30:25.453393+00:00 | Generated at: 2026-10-17T11:08:49.372517+00:00 | Generated at: 2026-10-17T11:08:49.268412+00:00
### Homework
- Homework: DATA260 HW6
### Local model
- Local model: Ollama `qwen3:8b`
### Preferred Study Topic
- Preferred Study Topic: Distributed systems (scalability, fault tolerance, concurrency)
### SID4
- SID4: 8844
### Student
- Student: Vrishin KunnathamParambath
### The embedding model is `sentence-transformers/all-MiniLM-L6-v2`. It produces 384-dimensional normalized vectors. Normalization makes cosine similarity a stable way to compare a new message with stored episodic facts
- The embedding model is `sentence-transformers/all-MiniLM-L6-v2`. It produces 384-dimensional normalized vectors. Normalization makes cosine similarity a stable way to compare a new message with stored episodic facts: facts with more similar meaning receive higher similarity scores and can be placed nearer the top of the retrieved set.
### The first protection is the short-term window
- The first protection is the short-term window: older messages fall out of the active prompt once they are outside the configured recent-message bound. Important information should remain available through a session summary or an episodic fact rather than by allowing the prompt to grow indefinitely.
### The local response model is Ollama `qwen3
- The local response model is Ollama `qwen3:8b`. Embeddings are used for episodic retrieval, while the Ollama model uses the assembled system instructions, summaries, recent messages, and retrieved facts to generate an answer.
### The memory design lets the application retain useful context in separate bounded layers. Commands are implemented through the HW6 memory service
- The memory design lets the application retain useful context in separate bounded layers. Commands are implemented through the HW6 memory service: `/memory` reads MongoDB and file metadata, `/compact` consolidates file memory while preserving raw messages, and `/dream` writes only verified non-sensitive facts with duplicate and contradiction handling.
### The memory system uses three MongoDB collections in the HW6 database
- The memory system uses three MongoDB collections in the HW6 database:
### `EPISODIC_TOP_K=3`
- `EPISODIC_TOP_K=3`: retrieve at most three episode candidates for the prompt.
### `SHORT_TERM_N=12`
- `SHORT_TERM_N=12`: include at most twelve recent messages in the short-term window.
### `SUMMARIZE_EVERY_USER_MSGS=5`
- `SUMMARIZE_EVERY_USER_MSGS=5`: attempt a session summary after every fifth user message.

## Needs review
- No contradictions detected.
