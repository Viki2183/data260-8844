# AI Use Statement — DATA 260 Homework 2

## 1. What I Used an AI Assistant For

I used an AI assistant for guidance while extending my DATA 260 Homework 1 repository. The assistance included explaining the FastAPI and REST API requirements, suggesting a project structure, helping write code with comments, explaining Docker commands, and helping organize the experiment and report files.

I also used the assistant to understand error messages, check command results, and plan the implementation one step at a time. I personally ran the commands, created and saved the files, tested the application, reviewed the browser output, and pushed the final work to GitHub.

## 2. One AI-Produced Output That Was Initially Unsuitable

One initial backend startup command used the Uvicorn import path:

`code.web_application.main:app`

This failed because Python treated `code` incorrectly and reported that `code.web_application` was not a package. The first Docker image also did not include the stylesheet because `styles.css` had not been saved in the required application folder.

## 3. How I Detected the Problems

I detected the backend problem from the Python traceback:

`ModuleNotFoundError: No module named 'code.web_application'; 'code' is not a package`

I detected the stylesheet problem by checking the local file path with PowerShell and requesting the stylesheet from the running container. The local check returned `False`, and the Docker log reported:

`File at path /app/web_application/styles.css does not exist.`

I also independently verified the completed application through syntax checks, API requests, browser tests, Docker logs, and Git status checks.

## 4. What I Changed and Why It Works

I changed the Uvicorn startup code to pass the FastAPI application object directly instead of importing it through the invalid package path. I saved `styles.css` inside `code/web_application`, rebuilt the Docker image, and recreated the container.

These changes worked because Uvicorn could start the application without the incorrect module import, and Docker copied the stylesheet into `/app/web_application`. The final tests confirmed that the API responded, the webpage loaded with styling, the form submitted records, search worked, report ID 1 could be updated, and the highest-ID report could be deleted.