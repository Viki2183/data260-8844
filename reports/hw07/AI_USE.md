# DATA260 HW7 AI Use Statement

Student: Vrishin KunnathamParambath | SID4: 8844

Repository: https://github.com/Viki2183/data260-8844
Submission access still requires confirmation for collaborators `Sbnikitha` and
`supriyaselvanganesan`. Commit/tag hash: pending final packaging.

1. What assistance was used and what the student did

Codex assisted with repository inspection, reading the official HW7 assignment,
reviewing the existing HW1–HW6 implementation, implementing and testing the
HW7 authentication, agent, MRKL, prompt-security, file-tool, migration, and
bike-share UI changes, organizing raw evidence, and preparing the report.
The student supplied the repository, credentials privately when needed,
approved each phase, selected the HW7 scope and test data, reviewed the
results, and retained responsibility for the final submission decisions.

2. Incorrect or unsuitable output and independent verification

One early bike-share evidence result reported a membership cost of $6,830 for
the pay-per-use scenario. It was unsuitable because the calculation used
`included_minutes=0`, even though the selected Citi Bike pricing evidence
provides 45 included member minutes per ride.

3. How the problem was detected or verified

The CSV contained 500 rides and 5,000 total minutes. The pricing snapshot and
the UI pipeline were compared with the raw JSON. The corrected calculation is
20 annual memberships × $239 = $4,780, with 500 × 45 included minutes and no
residual charge. The original raw JSON was preserved and the corrected result
was saved separately as `hw7_bikeshare_scenarios_corrected.json`.

4. What changed and why it works

The bike-share UI pipeline already used `included_minutes=ride_count * 45`.
A separate corrected evidence file and explanatory metrics/run-log notes were
added so the authoritative value is $4,780 without overwriting the original
raw evidence. Other verified corrections included the missing `tool_call_id`
compatibility field, bounded agent repair messaging, duplicate router cleanup,
and the inline `python -c` safety-gate false allow.

Measured failures were reported without alteration: the 20-attempt reliability
experiment recorded 0/20 successful tasks, while the baseline fixed-task
comparison was 0/3 and Reflexion was 1/3. Pytest remained blocked by the
managed temporary-file environment and the repository `code` package shadowing
the standard-library `code` module; a deterministic offline assertion check
was used where appropriate.

No hidden chain-of-thought was stored or returned. Raw evidence contains only
prompts/task inputs where required, tool calls, tool results, verifier output,
final answers, stop reasons, and measured metrics. Passwords, JWTs, password
hashes, and other secrets were not included.
