# DATA260 Homework 7 - Final Report Source

Student: Vrishin KunnathamParambath  
SID4: 8844  
Domain: open-source package vulnerabilities  
Repository: https://github.com/Viki2183/data260-8844  
Collaborator-access confirmation: `Sbnikitha`, `supriyaselvanganesan` - pending submission confirmation.  
Commit/tag hash: **pending final packaging**  

## Configuration and hardware

Model: `qwen3:8b` through local Ollama at `127.0.0.1:11434`.  
`PORT_BASE=8744`, `PREFIX=s8844`, `SEED=8844`, `VERIFY_SEED=268844`, `DOMAIN_ID=4`.  
HW6 hardware description: Intel Core i7-10750H CPU, approximately 16 GB RAM.

## AI use and verification boundary

Codex assisted with repository inspection, reading the official assignment,
implementation review, offline testing, evidence organization, and report
preparation. The student supplied the repository and private credentials when
needed, approved the phases and test scope, selected test data, reviewed the
results, and retained responsibility for submission decisions. The complete
answer is synchronized in `AI_USE.md`.

**What assistance was used?** Repository inspection, code review, bounded test
design, raw-evidence organization, and report/PDF preparation were assisted by
Codex. **What did the student do?** The student supplied the repository,
approved scope, entered private credentials locally when needed, selected the
test identities/data, reviewed outputs, and remains responsible for the final
submission. **What was corrected?** The original pay-per-use evidence carried a
$6,830 membership value caused by `included_minutes=0`; it was preserved and
superseded by a separately recorded $4,780 calculation. **What was manually
verified?** Repository state, source files, offline assertions, live JWT
responses, raw evidence, screenshots, and PDF output were checked. **What was
not complete?** Full pytest remained blocked, and final Git packaging and
verification metadata were not performed. No hidden chain-of-thought was
stored.

No hidden chain-of-thought was stored or returned. Evidence stores only task
inputs where needed, tool calls, tool results, verifier outputs, final answers,
stop reasons, and measured metrics. Passwords, password hashes, JWT strings,
and secrets are excluded.

The measured 20-attempt reliability result is reported without alteration:
20 attempts were recorded, with 0/20 successful task completions. The baseline
fixed-task comparison was 0/3 and Reflexion was 1/3. Pytest remained blocked by
the managed temporary-file environment and the repository `code` package
shadowing the standard-library `code` module; deterministic offline checks were
used where appropriate. These checks do not replace the blocked full pytest run.

## Part 1 - JWT authentication, roles, and database migration

### Implementation excerpts

`code/web_application/auth_hw7.py` defines the HW7 JWT routes and helpers:

```python
@router.post("/login", response_model=TokenResponse)
def login(payload: LoginPayload, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(models.UserDB).filter(
        models.UserDB.username == payload.username.strip()
    ).first()
    if user is None or user.role not in ALLOWED_ROLES or not verify_password(
        payload.password, user.password_hash
    ):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return TokenResponse(access_token=create_access_token(user.username, user.role))

@router.get("/me", response_model=IdentityResponse)
def me(user: models.UserDB = Depends(get_current_user)) -> IdentityResponse:
    return IdentityResponse(username=user.username, role=user.role)
```

JWT creation validates `reader`, `writer`, and `moderator`, signs HS256 claims,
and includes `iat` and `exp`. Validation checks the signature, header, username,
role, and expiration. Passwords use bcrypt:

```python
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
```

Role dependencies are explicit: authenticated reads are available to all three
roles; create is available to writer/moderator; delete is moderator-only.

### Live status evidence

Source: `raw/hw7_live_jwt_authorization.json`, 19 cases, all recorded as passing.

| Check | Expected | Recorded |
|---|---:|---:|
| Reader/writer/moderator login | 200 | 200/200/200 |
| Invalid password and unknown username | 401 | 401/401 |
| `/auth/me` reader/writer/moderator | 200 | 200/200/200 |
| Missing, invalid, expired token | 401 | 401/401/401 |
| Authenticated list/read for all roles | 200 | 200/200/200 |
| Reader create | 403 | 403 |
| Writer create | 201 | 201 |
| Moderator create | 201 | 201 |
| Writer delete | 403 | 403 |
| Moderator delete | 200 | 200 |

The live evidence records no stored JWT values and no stored passwords. Created
HW7 test records were limited to the labeled test records; the moderator delete
target was cleaned up. No HW1-HW6 record was deleted or modified.

### Users schema and migration

`code/web_application/hw7_migration.py` defines a non-destructive
`CREATE TABLE IF NOT EXISTS users` shape with `id`, `name`, `username`, `email`,
`password_hash`, `role`, a primary key, unique username/email keys, and a role
check for `reader`, `writer`, or `moderator`. It explicitly requires preflight
inspection before altering an existing table and does not invent a username
backfill.

| id | username | role | password_hash |
|---:|---|---|---|
| 1 | vikki1 | reader | exists; value not displayed |
| 2 | vikki2 | writer | exists; value not displayed |
| 3 | vikki3 | moderator | exists; value not displayed |

This table records only safe fields from the approved live preflight. A dedicated
MySQL-table screenshot/raw artifact was not created; manual capture is required
if the instructor requires visual database evidence. No schema or row change is
performed by this report.

Ruff scoped checks passed for the HW7 scope. Pre-commit configuration validation
passed, while the configured fixing hook was not run because it can modify files.
No successful commit/tag screenshot exists; packaging hashes remain pending.

## Part 2 - bounded agent loop and reliability

### Actual implementation

`code/hw7_agent.py` uses `run_agent`, not a pseudo-agent. It validates each model
decision as `tool` or `final`, dispatches the named handler, catches tool errors
as bounded observations, appends a `tool` message with deterministic IDs such as
`hw7-tool-call-1`, and appends a continuation message. The loop is bounded by
`max_steps`; malformed/unknown decisions and incomplete required sequences have
at most one repair in the recorded smoke/reliability configuration.

The repair includes the next required tool and, for Task A, the package ID from
the search observation. A final answer before the required sequence yields
`human_review` after the repair budget is exhausted. Other bounded stop reasons
are `success` and `budget_exhausted`.

The loop logs tool name, inputs, observation, tool-call count, repair count,
latency, final answer, and stop reason. It does not store hidden reasoning.

### Fixed-task evidence

`raw/hw7_agent_fixed_tasks.json` records the earlier fixed-task run with the
pre-compatibility `tool_call_id` failure. Later evidence
`raw/hw7_task_a_package00001.json` records the corrected Task A smoke input:
`search(package-00001) -> detail(package_id=1)`, two tool calls, final answer
produced, and `success`. These are separate runs and are not merged.

Tasks B and C have raw run evidence but no dedicated successful browser screenshot.
The report uses raw logs and marks B/C visual capture as manual-capture required.
Nonexistent-ID recovery is covered by the offline agent tests and bounded tool
error handling; no database write is required for that recovery path.

### Reliability table

Source: `raw/hw7_reliability_20_attempts_v2.json`.

| Metric | Actual value |
|---|---:|
| Total attempts | 20 |
| Well-formed call rate before repair | 20/20 (100%) |
| Well-formed call rate after repair | 0/20 (0%) |
| Malformed arguments | 0 |
| Unknown tool | 0 |
| Text when a tool was required | 20 |
| Lost multi-step chain | 0 |
| Successful tasks | 0/20 |
| `human_review` stops | 20 |
| Average latency | 13,160.690 ms |
| Median latency | 12,423.832 ms |
| Average tool calls | 0 |

## Part 3 - Reflexion and verifier

`verify_task` checks the stop reason, required tool set, and answer presence. It
returns `success`, `unsupported_claims`, and `missing_tools`. `reflexion_run`
retries only after verifier failure, allows at most two retries, stores concise
reflections with the prior trace/verifier evidence, and returns one of
`success` or `human_review`; the agent itself also has `budget_exhausted`.

Reflections are isolated within a run and passed as a model-factory context;
they are not instructions, permissions, role definitions, or safety gates. The
tool registry and authorization policy remain fixed. Hidden chain-of-thought is
not stored.

| Task | Condition | Success | Unsupported claims | Retry rate | Tool calls | Tokens | Latency ms | False rejection |
|---|---|---:|---:|---:|---:|---:|---:|---|
| A | baseline | 0/1 | verifier false | 0 | 0 | available in raw | 13,579.628 | unavailable |
| A | Reflexion | 0/1 | verifier false | 2 | 1 | available in raw | 78,020.263 | unavailable |
| B | baseline | 0/1 | verifier false | 0 | 0 | available in raw | 13,030.116 | unavailable |
| B | Reflexion | 0/1 | verifier false | 2 | 1 | available in raw | 41,699.474 | unavailable |
| C | baseline | 0/1 | verifier false | 0 | 0 | available in raw | 19,814.970 | unavailable |
| C | Reflexion | 1/1 | false | 1 | 2 | available in raw | 42,979.888 | unavailable |

Aggregate source summary: baseline 0/3, Reflexion 1/3, Reflexion maximum retry
count 2, baseline average latency 15,474.905 ms, Reflexion average latency
54,233.208 ms, average Reflexion tool calls 1.333. Verifier false-rejection
data is unavailable because the evidence does not contain an independent
false-rejection adjudication.

## Part 4 - MRKL and bike-share application

The three pure/isolated tools share a response shape with `success`, optional
`data`, optional `error`, optional `source`, and `ts`:

```python
def _result(success, data=None, error=None, source=None):
    value = {"success": success}
    if data is not None: value["data"] = data
    if error: value["error"] = error
    if source: value["source"] = source
    value["ts"] = datetime.now(timezone.utc).isoformat()
    return value

def csv_sql(csv_text, sql):
    if not re.match(r"^\s*select\b", sql, re.IGNORECASE):
        return _result(False, error="csv_sql accepts one read-only SELECT")
    # parse uploaded CSV into an in-memory SQLite table and return rows

def policy_retriever(url, query, k=3):
    # retrieve bounded passages and return source=url in the common shape

def calculator(expression, units=None):
    # permit only a checked arithmetic AST, then return value and units
```

`csv_sql` rejects non-SELECT statements independently of the model. The
calculator rejects unsupported characters and AST nodes. Missing files,
malformed CSV, invalid arithmetic, and SQL injection/non-SELECT attempts are
covered by offline tests.

The official pricing URL recorded in evidence is
`https://citibikenyc.com/plans-and-pricing`. Both snapshots have access timestamp
`2026-10-25T07:27:04.715872+00:00` and SHA-256
`07fb221a434fb166302571050657a0c2c53f995214af78771faf735e7733c71d`.

| Scenario | Rows | Weekly rides | Avg duration | Weekly spend | Pay/use | Membership | Residual | Break-even | Actual | Steps | Stop |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|
| Membership wins | 500 | 500/month (period: one month) | 30 min | source period; not separately recorded | $8,645 | $19.92 | $0 | 1.15 rides | 500 rides/15,000 min | 5 | success |
| Pay-per-use wins | 500 | 25/year = 0.48/week | 10 min | source period; not separately recorded | $4,545 | $4,780 | $0 | not recomputed in corrected file | 500 rides/5,000 min over 20 years | 5 | success |

The membership scenario is one month of 30-minute rides, all within the
45-minute member allowance, and remains unchanged. The pay-per-use scenario is
a 20-year observation horizon with 25 short rides per year. Annual membership
pricing is applied for each of the 20 years: `20 * $239 = $4,780`. The corrected
calculation uses 500 rides x 45 included minutes, so no residual charge remains.

The original `raw/hw7_bikeshare_scenarios.json` is preserved unchanged. Its old
pay-per-use recommendation displayed `$6,830` because it used
`included_minutes=0`, even though its calculator result recorded `$4,780`.
`raw/hw7_bikeshare_scenarios_corrected.json` is the authoritative correction:
pay-per-use `$4,545`, membership `$4,780`, decision `Pay Per Ride/Minute`.

## Part 5 - prompt-injection threat model

Threats are: retrieved text overriding the recommendation; model-directed
non-read-only SQL; and inappropriate inclusion of complete uploaded CSV content.

| Attack | Before defenses | Prompt defense | Prompt + tool boundary |
|---|---|---|---|
| Recommendation override | blocked: no | blocked: yes | blocked: yes |
| Non-SELECT SQL misuse | blocked: no | blocked: no | blocked: yes |
| CSV-content exfiltration | blocked: no | blocked: yes | blocked: yes |

Prompt-only defenses label retrieved policy as untrusted and rely on model
instruction following. Tool-boundary defenses enforce executable restrictions;
`csv_sql` independently accepts only read-only SELECT statements. Raw source:
`raw/hw7_prompt_injection_results.json`.

## Part 6 - file tools and safety gate

`code/hw7_file_tools.py` implements `read_file`, `write_file`, `edit_file`,
`glob_files`, `search_in_files`, and `bash`. `_safe` resolves every path under
the temporary course sandbox. `SAFE_PREFIXES` allowlists bounded local commands.
`is_destructive` independently detects destructive patterns, including the
original false allow: `python -c` file writes. `confirm_bash` requires explicit
confirmation for destructive commands, and `bash` applies a 30-second timeout.

Representative implementation excerpts:

```python
def read_file(path, root, max_lines=None):
    lines = _safe(path, root).read_text(encoding="utf-8").splitlines()
    return "\n".join(lines if max_lines is None else lines[:max_lines])

def write_file(path, content, root):
    target = _safe(path, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return str(target.relative_to(root.resolve()))

def edit_file(path, old, new, root):
    target = _safe(path, root)
    before = target.read_text(encoding="utf-8")
    if old not in before: raise ValueError("text to replace was not found")
    target.write_text(before.replace(old, new, 1), encoding="utf-8")

def glob_files(pattern, root): ...
def search_in_files(query, root, file_pattern="*"): ...
def bash(command, auto_approve=False):
    decision = confirm_bash(command, auto_approve)
    if not decision["allowed"]: return decision
    return subprocess.run(command, shell=True, timeout=30, ...)
```

The safety constants and independent checks are:

```python
SAFE_PREFIXES = ("python ", "python3 ", "pytest ", "ruff ",
                 "git status", "git diff", "git log")
DESTRUCTIVE_PATTERNS = (..., r"\bpython(?:3)?\s+-c\b")
def is_destructive(command):
    return any(re.search(pattern, command, re.IGNORECASE)
               for pattern in DESTRUCTIVE_PATTERNS)
def confirm_bash(command, auto_approve=False):
    if is_destructive(command):
        return {"allowed": bool(auto_approve),
                "reason": "destructive command requires explicit confirmation"}
```

The corrected run in `raw/hw7_file_tools_safety_results_corrected.json` reports:

| Check | Result |
|---|---:|
| Glob -> search -> read found `DEBUG` | pass |
| Allowed commands | 5/5 |
| Blocked commands | 5/5 |
| Corrected false allows | 0 |
| Outside sandbox modified | false |
| Database accessed | false |
| Model called | false |

The independent deny-list added `python -c` after the first run identified the
inline Python file-write command as a false allow. No application file outside
the temporary sandbox was modified.

## Tests, limitations, and preservation

Offline tests covered JWT creation/validation, password hashing, roles, bounded
agent repair and tool-call budgets, Reflexion retry bounds, MRKL calculator and
SQL validation, prompt security, file-tool sandbox behavior, migration safety,
and the bike-share UI pipeline. Scoped Ruff passed. Full pytest was not claimed
because collection/execution remained blocked by the managed environment and
the repository `code` package shadowing the standard-library `code` module.

Existing HW1-HW6 source changes, reports, screenshots, raw evidence, database
state, branches, tags, `.hw6-chrome-pdf-profile*`, and `MEMORY.md.before-hw6`
remain preserved. This report does not create `verification.json`. Commit 1,
the verifier-generated `verification.json`, Commit 2, and the annotated `hw7`
tag remain the next packaging steps. A GitHub push remains pending approval.

### Remediation and manual-capture matrix

| Assignment requirement | Existing evidence/code | Missing report content | Missing screenshot | Proposed report section | Manual capture? |
|---|---|---|---|---|---|
| JWT login/me/roles | auth module, 19-case JSON, screenshots | code/output linkage | MySQL table; writer/moderator login visuals | Part 1 | MySQL/table and any missing role visuals |
| Agent loop/reliability | hw7_agent.py, reliability JSON | actual implementation and full metric table | B/C visuals | Part 2 | B/C screenshots |
| Reflexion | agent verifier and comparison JSON | verifier/budget/isolation explanation | no dedicated verifier terminal | Part 3 | optional terminal capture |
| MRKL scenarios | source, CSVs, snapshots, corrected JSON | cost assumptions, hashes, horizon, caveat | existing screenshots are readable | Part 4 | no, unless instructor requests crops |
| Prompt injection | prompt-security source and raw JSON | written threat model/table | existing screenshot | Part 5 | no |
| File safety | source and corrected JSON | actual function excerpts and false-allow correction | existing screenshot | Part 6 | no |
| Packaging | current Git state | final hashes | no successful commit screenshot | Tests/limitations | yes, after approved packaging |

## Packaging status

The PDF is prepared for review only. `verification.json` is intentionally not
created because the final commit hash does not yet exist. No commit, tag, push,
database change, source-code change, screenshot change, or raw-evidence change
is part of this remediation.
