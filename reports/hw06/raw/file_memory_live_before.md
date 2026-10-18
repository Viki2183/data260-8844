# DATA260 Homework 6 Memory Policy

This document describes the planned memory model for DATA 260 Homework 6. It is documentation only: the slash-command behavior is not implemented by this step.

## Project context

- Homework: DATA260 HW6
- Student: Vrishin KunnathamParambath
- SID4: 8844
- Local model: Ollama `qwen3:8b`
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`

The purpose of this design is to let the existing FastAPI application remember useful conversation context without treating every old message as equally important. Each memory layer has a different job, and the boundaries make the system easier to explain, test, and keep within a predictable prompt size.

## Four kinds of memory

### Short-term memory

Short-term memory contains the most recent conversation messages for the active user and session. The configured window is `SHORT_TERM_N=12`. Recent messages are useful for immediate continuity, but the window is deliberately bounded so prompts do not grow without limit.

### Session summaries

A session summary is a compact description of an individual conversation. The configured trigger is `SUMMARIZE_EVERY_USER_MSGS=5`, so the fifth user message in a session triggers a session-summary attempt. The summary preserves preferences, decisions, goals, and unresolved items from older conversation turns.

### Lifetime summaries

A lifetime summary represents durable information across sessions for one user. The current policy creates a lifetime summary after every third generated session summary, subject to the service configuration. It is intentionally less frequent than session summarization because it should contain stable, reusable information rather than every temporary detail.

### Episodic facts

Episodic facts are short, durable statements extracted from user messages. Each fact has an importance score and an embedding, allowing semantically relevant memories to be retrieved even when the wording of a later question is different. Facts are candidates for long-term recall, not a replacement for the original conversation record.

## MongoDB collections

The memory system uses three MongoDB collections in the HW6 database:

- `messages` stores user and assistant messages, including their user ID, session ID, role, content, creation time, and available usage metadata.
- `summaries` stores session-scoped and user-scoped lifetime summaries. The `scope` field distinguishes a summary of one session from a summary intended to persist across sessions.
- `episodes` stores extracted durable facts, importance scores, embeddings, user/session references, and creation times. These records support similarity-based episodic retrieval.

The collections are separate because raw conversation history, compressed summaries, and semantic facts have different retention and retrieval behavior. Keeping them separate also makes indexes and verification queries easier to understand.

## Configured memory values

- `SHORT_TERM_N=12`: include at most twelve recent messages in the short-term window.
- `SUMMARIZE_EVERY_USER_MSGS=5`: attempt a session summary after every fifth user message.
- `EPISODIC_TOP_K=3`: retrieve at most three episode candidates for the prompt.

These values are bounded configuration choices rather than promises that every request will contain exactly that many records. For example, a new session can have fewer than twelve messages, and retrieval may return fewer than three relevant facts.

## Embeddings and retrieval

The embedding model is `sentence-transformers/all-MiniLM-L6-v2`. It produces 384-dimensional normalized vectors. Normalization makes cosine similarity a stable way to compare a new message with stored episodic facts: facts with more similar meaning receive higher similarity scores and can be placed nearer the top of the retrieved set.

The local response model is Ollama `qwen3:8b`. Embeddings are used for episodic retrieval, while the Ollama model uses the assembled system instructions, summaries, recent messages, and retrieved facts to generate an answer.

## Memory commands

The planned commands are:

- `/memory`: display the current memory state for a user and, when requested, a session. It should show bounded recent messages, available summaries, and retrieved episodic facts without exposing internal credentials.
- `/compact`: consolidate older messages into summaries and durable facts. It should be bounded, explicit, and safe to run for one user scope at a time.
- `/dream`: produce a non-destructive preview of possible consolidation. It should explain what could be summarized or remembered without changing MongoDB records.
- `/help`: explain the available commands, their arguments, their scope, and their safety limits.

These commands are documented here before their API behavior is implemented. Each command must validate its user scope, use bounded retrieval limits, and avoid printing passwords, API keys, database credentials, or raw MongoDB connection strings.

## Eviction and compression policy

The first protection is the short-term window: older messages fall out of the active prompt once they are outside the configured recent-message bound. Important information should remain available through a session summary or an episodic fact rather than by allowing the prompt to grow indefinitely.

Compression should preserve meaning, not merely truncate text. Session summaries should retain goals, preferences, decisions, and unresolved items. Episodic extraction should keep only concise, durable facts with an importance score. Lifetime summaries should be created less often and should combine stable information from multiple session summaries.

The original `messages` records remain historical evidence for the application and its experiments. Eviction from the prompt does not authorize deletion from MongoDB. Any future cleanup policy must be explicit, user-scoped, bounded, and separately verified.

## Evidence and safety rules

Historical HW1-HW5 code, reports, screenshots, logs, notebooks, raw outputs, and tags must not be overwritten. New HW6 evidence belongs in its own `reports/hw06` structure.

Secrets and database credentials must never be printed. Diagnostic output should identify a safe error category without revealing passwords, API keys, complete connection strings, or unrelated environment values.

This policy is a design reference for explaining the memory system to an instructor. It does not claim that the slash commands are implemented or that a future command run has succeeded.
