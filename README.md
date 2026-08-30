# DATA 260 Homework 1

## Student Configuration

- Name: Vrishin KP
- SID4: 8844
- PORT_BASE: 8744
- PREFIX: s8844
- SEED: 8844
- VERIFY_SEED: 268844
- DOMAIN_ID: 4
- Assigned domain: Open-source package vulnerabilities
- Local model: qwen3:8b
- Python version: 3.12
- Container server: Nginx on Alpine Linux

## Project Overview

This project contains a domain-specific vulnerability-submission form, a Docker deployment, a local multi-agent Ollama pipeline, a nondeterminism experiment, and a reusable model client with token accounting.

The assigned entity is an open-source package vulnerability report.

## Project Structure

```text
data260-8844/
├── DOMAIN_SCHEMA.md
├── index.html
├── app.js
├── Dockerfile
├── agents_demo.py
├── run_nondeterminism.py
├── calculate_metrics.py
├── hw1_client.py
├── AGENT.md
├── requirements.txt
├── README.md
├── src/
│   ├── __init__.py
│   └── model_client.py
└── reports/
    └── hw01/
        ├── cases/
        │   └── nondeterminism_input.json
        ├── raw/
        │   ├── nondeterminism_results.json
        │   ├── nondeterminism_results.csv
        │   ├── nondeterminism_metrics.json
        │   └── client_conversation.json
        ├── RUN_LOG.txt
        ├── METRICS.md
        ├── AI_USE.md
        ├── verification.json
        └── report.pdf