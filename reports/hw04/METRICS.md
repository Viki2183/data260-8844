# DATA 260 Homework 4 Metrics

Student: Vrishin Dharmesh Kunnatham Parambath  
SID4: 8844  
Domain: Open-source package vulnerabilities  
Seed: 8844  
Database: MySQL 8.0  
Device: CPU  

## N+1 benchmark

Each configuration used 30 requests at page sizes 10, 50, and 200.

| Version | Page size | Requests | SQL statements | p50 latency (ms) | p95 latency (ms) | p99 latency (ms) |
|---|---:|---:|---:|---:|---:|---:|
| Naive | 10 | 30 | 13 | 17.938 | 22.520 | 22.853 |
| Naive | 50 | 30 | 53 | 55.535 | 61.310 | 64.368 |
| Naive | 200 | 30 | 203 | 183.201 | 239.929 | 284.395 |
| Fixed | 10 | 30 | 4 | 9.648 | 11.447 | 11.977 |
| Fixed | 50 | 30 | 4 | 13.567 | 17.384 | 18.002 |
| Fixed | 200 | 30 | 4 | 21.786 | 26.535 | 45.902 |

The naive implementation increases its SQL statement count with page size because it performs one related-record query per report. The fixed implementation keeps the SQL statement count constant by loading the related records in one combined query.

## Index EXPLAIN comparison

Before the index:

- Access type: `ALL`
- Key: `NULL`
- Estimated rows: `4885`
- Extra: `Using where`

After creating `idx_vulnerability_reports_package_name`:

- Access type: `ref`
- Key: `idx_vulnerability_reports_package_name`
- Estimated rows: `1`
- Extra: `NULL`

The index changed the package-name lookup from a full table scan to an indexed lookup.

## RAG experiment

The corpus contained 69 vulnerability documents and produced 850 chunks using a 500-token chunk size and 50-token overlap.

The experiment produced:

- 18 configuration-comparison rows
- 3 top-k sweep rows
- Six questions
- No-RAG, Basic-RAG, and Context-RAG configurations
- Top-k sweep values of 1, 3, and 5

Observed behavior:

- Q1 and Q2 were answered correctly by Basic-RAG and Context-RAG.
- Q3 demonstrated a retrieval limitation because the Pydantic AI source was not retrieved with the top-three chunks.
- Q4 was ambiguous and caused inconsistent behavior across configurations.
- Q5 and Q6 were correctly refused by Context-RAG.
- No-RAG produced unsupported answers for Q5 and Q6.
- Increasing k introduced irrelevant documents for Q1. At k=1, only the Poetry source was retrieved; at k=3 and k=5, unrelated sources appeared.

The answer-correctness field in the raw evaluation table is a heuristic keyword-overlap check and should be interpreted together with the saved answers and retrieved chunks.
