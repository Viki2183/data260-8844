# DATA 260 Homework 3 Reproducibility Instructions

## Configuration

- Student: Vrishin Dharmesh Kunnatham Parambath
- SID4: 8844
- PORT_BASE: 8744
- PREFIX: s8844
- SEED: 8844
- VERIFY_SEED: 268844
- DOMAIN_ID: 4
- Domain: Open-source package vulnerabilities
- Python: 3.14.0
- Embedding model: sentence-transformers/all-MiniLM-L6-v2
- Device: CPU

## Environment

From the repository root, use the project virtual environment:

`.\.venv\Scripts\python.exe`

The Hugging Face cache is redirected to the writable repository folder:

`.\.hf_cache`

PowerShell environment variables:

`$env:HF_HOME = (Resolve-Path .\.hf_cache).Path`

`$env:HF_HUB_DISABLE_XET = "1"`

`$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"`

`$env:HF_HUB_DISABLE_TELEMETRY = "1"`

## Authentication application

Start the FastAPI application:

`cd code\web_application`

`python -m uvicorn main:app --host 127.0.0.1 --port 8744`

Open `http://127.0.0.1:8744/`.

Demo credentials:

- Username: `admin`
- Password: `password`

## Corpus and manifest

The questions were committed before retrieval results were generated.

Create the selected corpus with:

`.\.venv\Scripts\python.exe .\code\hw3_rag\select_corpus.py`

Create the corpus manifest with:

`.\.venv\Scripts\python.exe .\code\hw3_rag\build_manifest.py`

## Retrieval experiment

Run all three chunking techniques:

`.\.venv\Scripts\python.exe .\code\hw3_rag\run_retrieval.py`

The experiment generates raw results in `reports/hw03/raw/`.

## Verification

Run the self-check:

`.\.venv\Scripts\python.exe .\code\hw3_rag\verify_hw03.py`

The verification should finish with:

`Overall verification: True`

## Main output files

- `reports/hw03/questions.yaml`
- `reports/hw03/SOURCES.md`
- `reports/hw03/CORPUS_MANIFEST.json`
- `reports/hw03/METRICS.md`
- `reports/hw03/RUN_LOG.txt`
- `reports/hw03/verification.json`
- `reports/hw03/raw/retrieval_results.jsonl`
- `reports/hw03/raw/retrieval_results.csv`
- `reports/hw03/raw/metrics.json`
- `reports/hw03/raw/wrong_retrieval_candidates.json`