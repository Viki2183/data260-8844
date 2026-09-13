# DATA 260 Homework 1

## Student Configuration

* Name: Vrishin Dharmesh Kunnatham Parambath
* SID4: 8844
* PORT_BASE: 8744
* PREFIX: s8844
* SEED: 8844
* VERIFY_SEED: 268844
* DOMAIN_ID: 4
* Assigned domain: Open-source package vulnerabilities
* Local model: qwen3:8b
* Python version: 3.12
* Container server: Python 3.12 with FastAPI and Uvicorn

## Project Overview

This project contains a domain-specific vulnerability-submission form, Docker deployment, local multi-agent Ollama pipeline, nondeterminism experiment, and reusable model client with token accounting.

Application code is stored in the shared `code/` and `src/` folders. Homework-specific evidence is stored under `reports/hw01/`.

## Project Structure

```text
data260-8844/
|-- code/
|   |-- __init__.py
|   |-- web_application/
|   |   |-- index.html
|   |   `-- app.js
|   |-- agents_demo.py
|   |-- run_nondeterminism.py
|   |-- calculate_metrics.py
|   |-- hw1_client.py
|   |-- verify_hw01.py
|   `-- Dockerfile
|-- src/
|   |-- __init__.py
|   `-- model_client.py
|-- reports/
|   `-- hw01/
|       |-- cases/
|       |   `-- nondeterminism_input.json
|       |-- raw/
|       |   |-- nondeterminism_results.json
|       |   |-- nondeterminism_results.csv
|       |   |-- nondeterminism_metrics.json
|       |   `-- client_conversation.json
|       |-- RUN_LOG.txt
|       |-- METRICS.md
|       |-- AI_USE.md
|       `-- verification.json
|-- AGENT.md
|-- DOMAIN_SCHEMA.md
|-- README.md
|-- requirements.txt
`-- .gitignore
```

## Prerequisites

* Python 3.11 or 3.12
* Docker Desktop
* Ollama
* `qwen3:8b`
* Git
* AWS CLI v2
* AWS account for ECR and ECS deployment

## Python Setup

Create and activate the virtual environment:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Install and verify the Ollama model:

```powershell
ollama pull qwen3:8b
ollama list
```

## Web Application

The form collects package name, vulnerability ID, submitter email, vulnerability description, severity, and terms acceptance.

JavaScript validates the description and terms checkbox. Successful submission demonstrates JSON conversion and parsing, object destructuring, the spread operator, a generated submission date, and a closure-based counter.

## Docker Build and Local Run

Build from the repository root:

```powershell
docker build -f code/Dockerfile -t data260-8844-hw1 .
```

Run:

```powershell
docker run -d -p 8744:80 --name data260-8844-container data260-8844-hw1
```

Open:

```text
http://localhost:8744
```

View logs:

```powershell
docker logs data260-8844-container
```

Stop and remove the container:

```powershell
docker stop data260-8844-container
docker rm data260-8844-container
```

## Agent Pipeline

Run from the repository root:

```powershell
python code\agents_demo.py --title "Critical Authentication Bypass in Requests Package" --content "An authentication bypass allows unauthorized remote users to access protected resources and retrieve sensitive application data." --email "vrishindharmesh.kunnathamparambath@sjsu.edu" --model "qwen3:8b" --temperature 0.0 --strict
```

The pipeline prints Planner, Reviewer, Finalizer, publish-package JSON, and token statistics.

## Nondeterminism Experiment

The fixed input is stored at:

```text
reports/hw01/cases/nondeterminism_input.json
```

Run or resume the 40-run experiment:

```powershell
python code\run_nondeterminism.py
```

Generate metrics:

```powershell
python code\calculate_metrics.py
```

The experiment includes 20 runs at temperature `0.7` and 20 runs at temperature `0.0`. Results are saved after each run so an interrupted experiment can resume.

## Interactive Model Client

Run:

```powershell
python code\hw1_client.py
```

Available commands:

```text
/stats
/exit
```

The client records conversation history and token statistics in:

```text
reports/hw01/raw/client_conversation.json
```

## Context and Token Accounting

Prior conversation context is resent because the model does not automatically remember separate API requests. A system prompt defines overall behavior and constraints, while user messages contain individual requests.

Input-token usage grows because each request includes prior conversation history. Growth is eventually limited by the model’s context window, available memory, processing time, and latency.

## Verification

Run the complete self-check:

```powershell
python code\verify_hw01.py
```

Run syntax checks independently:

```powershell
python -m py_compile code\agents_demo.py code\run_nondeterminism.py code\calculate_metrics.py code\hw1_client.py code\verify_hw01.py src\model_client.py
```

The self-check creates:

```text
reports/hw01/verification.json
```

## AWS Deployment

The Docker image will be pushed to Amazon ECR and deployed as one AWS ECS Fargate task.

Expected resource names:

* ECR repository: `s8844-hw1`
* ECS cluster: `s8844-hw1-cluster`
* Task definition: `s8844-hw1-task`
* ECS service: `s8844-hw1-service`
* Security group: `s8844-hw1-sg`
* Container port: `80`
* Desired tasks: `1`
* Public IP: enabled

AWS resources must be deleted after capturing the required public-IP evidence to prevent continuing charges.

## Submission

The GitHub repository link must be included in the final report PDF. The following GitHub accounts must have collaborator access:

* `Sbnikitha`
* `supriyaselvanganesan`

The completed repository will be tagged:

```text
hw1
```

The uploaded report PDF must be identical to:

```text
reports/hw01/report.pdf
```

at the tagged commit.


## Homework 2 — FastAPI Vulnerability Reports

HW2 extends the HW1 vulnerability-submission form with a FastAPI backend and REST API.

### Local API

Run the application locally:

```powershell
.\.venv\Scripts\python.exe .\code\web_application\main.py
```

Open the application:

```text
http://127.0.0.1:8744
```

### API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/vulnerability-reports` | List all reports |
| GET | `/api/vulnerability-reports/{id}` | Get one report |
| GET | `/api/vulnerability-reports?search=requests` | Search reports |
| POST | `/api/vulnerability-reports` | Create a report |
| PUT | `/api/vulnerability-reports/{id}` | Update a report |
| DELETE | `/api/vulnerability-reports/{id}` | Delete a report |

### Docker

Build the image:

```powershell
docker build -f .\code\Dockerfile -t data260-8844-hw2 .
```

Run the container:

```powershell
docker run -d -p 8744:80 --name data260-8844-hw2-container data260-8844-hw2
```

Open the Dockerized application:

```text
http://127.0.0.1:8744
```

View container logs:

```powershell
docker logs data260-8844-hw2-container
```

Stop and remove the container:

```powershell
docker stop data260-8844-hw2-container
docker rm data260-8844-hw2-container
```

The API validates required fields, email format, description length, allowed severity values, and terms acceptance. Reports are stored in memory while the application is running.


