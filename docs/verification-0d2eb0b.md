# Verified baseline: 0d2eb0b

Verified commit: `0d2eb0b81365362f794af7b9f6249de13615a336`

GitHub Actions run: `33047451678`

## Complete suite

Command executed on Linux and Windows:

`python -m unittest discover -s tests -v`

Result:

- TOTAL: 188
- PASSED: 188
- FAILED: 0
- ERRORS: 0
- SKIPPED: 0

The regression matrix completed successfully on Linux Python 3.11, 3.12, 3.13, and 3.14, and Windows Python 3.14.

## Explicitly verified coverage

The executed suite includes and passed the benchmark tests, self-coding tests including sandbox repair behavior, self-development end-to-end pipeline tests, release tests, rollback history-preservation test, benchmark evidence/binding tests, and Windows regression.

No tests were weakened, deleted, or skipped to obtain the green baseline.

## Packaging gate

Windows packaging is permitted only after this green baseline. The workflow's `windows-package-smoke (3.14)` job also completed successfully after the regression jobs.