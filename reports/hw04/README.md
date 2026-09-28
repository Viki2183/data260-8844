# DATA 260 Homework 4

Student: Vrishin Dharmesh Kunnatham Parambath

SID4: 8844  
PORT_BASE: 8744  
PREFIX: s8844  
SEED: 8844  
VERIFY_SEED: 268844  
DOMAIN_ID: 4  
Domain: Open-source package vulnerabilities  
Model: qwen3:8b  
Device: CPU  

## Completed Work

- FastAPI authentication and protected sessions
- React login and CRUD interface
- MySQL vulnerability report database
- 5,000 seeded vulnerability reports
- 200 seeded vulnerability references
- Naive and fixed N+1 benchmark
- Before/after EXPLAIN index comparison
- RAG experiment using HW3 documents
- 500-token chunks with 50-token overlap
- No-RAG, Basic-RAG, and Context-RAG comparison
- Top-k sweep using k=1, k=3, and k=5

## Start Backend

```powershell
Set-Location -LiteralPath "C:\Projects\data260-8844\code\web_application"

& "..\..\.venv\Scripts\python.exe" -m uvicorn main:app `
    --host 127.0.0.1 `
    --port 8744