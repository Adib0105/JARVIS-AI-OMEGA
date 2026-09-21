from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    returncode: int
    duration_ms: float
    stdout: str
    stderr: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class TestReport:
    ok: bool
    checks: tuple[CheckResult, ...]
    duration_ms: float

    def as_dict(self) -> dict:
        return {
            'ok': self.ok,
            'checks': [item.as_dict() for item in self.checks],
            'duration_ms': self.duration_ms,
        }


class SelfDevelopmentTester:
    """Fails closed until a reviewed OS execution isolation backend is available."""

    def __init__(self, timeout: int = 300) -> None:
        self.timeout = max(10, min(int(timeout), 900))

    def _run(self, name: str, args: list[str], cwd: Path) -> CheckResult:
        # A worktree, timeout and scrubbed environment are not an OS boundary.
        # No supported/reviewed Windows isolation backend exists in this build.
        # Never fall back to host Python, even after ordinary action approval.
        return CheckResult(name=name, ok=False, returncode=126, duration_ms=0.0,
                           stdout='', stderr='EXECUTION_ISOLATION_UNAVAILABLE: '
                           'Generated code was not executed. Use a separately reviewed '
                           'disposable VM; host execution is disabled.')

    def run_regression(self, worktree: Path) -> TestReport:
        worktree = worktree.resolve()
        started = time.perf_counter()
        # ``-f`` is intentional: self-repair can rewrite a file to same-size content
        # within one filesystem timestamp tick (for example 'old' -> 'new'). Python
        # 3.11 can otherwise reuse a stale timestamp/size-based .pyc and report a
        # false regression after the source was actually repaired.
        checks = (
            self._run('compileall', ['-m', 'compileall', '-f', '-q', '.'], worktree),
            self._run('unittest', ['-m', 'unittest', 'discover', '-s', 'tests', '-v'], worktree),
        )
        return TestReport(
            ok=all(item.ok for item in checks),
            checks=checks,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
        )
