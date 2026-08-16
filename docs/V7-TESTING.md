# JARVIS AI OMEGA V7 / V7.5 — Testing & Evaluation

## Quality rule

A feature is not called complete merely because a module exists. The expected quality gate is:

```text
IMPLEMENTED
+ INTEGRATED
+ TESTED
+ VERIFIED
```

## CI matrix

The V7.5 workflow targets:

- Linux Python 3.11
- Linux Python 3.12
- Linux Python 3.13
- Linux Python 3.14
- Windows Python 3.14

Every job runs:

```text
python -m compileall -f -q .
python -m unittest discover -s tests -v
```

`ResourceWarning` is promoted to an error in CI so leaked files/SQLite handles cannot be ignored.

## Test categories

The repository includes coverage for:

- provider/foundation behavior
- missions / retry / recovery / replanning / pause / resume / cancel
- security/capability policy/audit/secret filtering
- layered memory/context/retrieval
- computer use target confidence and verification
- Browser V2 trust/injection handling
- documents and content-hash indexing
- self-evaluation and capability gap detection
- self-development sandbox and immutable-core policy
- bounded self-coding/self-debugging
- offline development truthfulness
- skill proposals/workflow learning
- backup/restore integrity
- controlled release/rollback
- observability/cost truthfulness/health
- adversarial security cases

## Evaluation benchmark

`jarvis/evaluation/benchmark.py` stores deterministic scenario results historically. Supported metric categories include:

- task success
- tool accuracy
- verification accuracy
- recovery
- replanning
- safety
- memory accuracy
- computer-use accuracy
- browser accuracy
- average latency

Before/after comparison treats lower latency as better and success/accuracy metrics as higher-is-better. A model statement such as “performance improved” is not accepted as benchmark evidence.

## Security regression expectations

Tests should fail safely for attempts involving prompt injection, secret persistence/extraction, private browser targets, unknown tools, permission bypass, sandbox escape, security-core self-modification and unrestricted shell exposure.

## Rule for red CI

Do not weaken/delete a failing test or hard-code its expected value just to make the build green. Inspect the first meaningful failure and fix the root behavior.
