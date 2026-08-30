# AI Use Disclosure

## 1. What did I use an AI assistant for, and what did I do myself?

I used an AI assistant to help interpret the assignment, organize the project structure, draft starter code, troubleshoot Docker, and identify required tests. I personally created and ran the files, tested the HTML and JavaScript validation, built the Docker image, ran the Ollama experiments, verified the outputs, and recorded the screenshots and metrics.

## 2. What AI-produced output was wrong or unsuitable, or what did I independently verify?

During the first code-review client test, the model incorrectly stated that `def divide(a, b): return a / b` divided `a` by `b` twice. The visible code contained only one division operation.

## 3. How did I detect or verify the problem?

I manually inspected the one-line function and counted the division operators. The expression `a / b` contains exactly one division operation, so the model's first bullet was factually incorrect.

## 4. What did I change, and why does it work now?

I strengthened `AGENT.md` to require the model to review only operations visibly present in the supplied code, avoid unsupported claims, and return every response line as a bullet. I also added `/no_think` to the system instructions used by `hw1_client.py`. I restarted the official five-turn test and verified that all five responses passed the bullet-only format check.