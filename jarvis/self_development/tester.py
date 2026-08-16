from __future__ import annotations

import subprocess
import sys
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
    """Runs only explicit Python quality gates inside an isolated worktree."""

    def __init__(self, timeout: int = 300) -> None:
        self.timeout = max(10, min(int(timeout), 900))

    def _run(self, name: str, args: list[str], cwd: Path) -> CheckResult:
        started = time.perf_counter()
        try:
            proc = subprocess.run(
                [sys.executable, *args],
                cwd=str(cwd.resolve()),
                text=True,
                capture_output=True,
                timeout=self.timeout,
                check=False,
            )
            return CheckResult(
                name=name,
                ok=proc.returncode == 0,
                returncode=proc.returncode,
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
                stdout=proc.stdout[-200000:],
                stderr=proc.stderr[-200000:],
            )
        except subprocess.TimeoutExpired as exc:
            return CheckResult(
                name=name,
                ok=False,
                returncode=124,
                duration_ms=round((time.perf_counter() - started) * 1000, 3),
                stdout=str(exc.stdout or '')[-200000:],
                stderr=('TIMEOUT: ' + str(exc))[-200000:],
            )

    def run_regression(self, worktree: Path) -> TestReport:
        worktree = worktree.resolve()
        started = time.perf_counter()
        checks = (
            self._run('compileall', ['-m', 'compileall', '-q', '.'], worktree),
            self._run('unittest', ['-m', 'unittest', 'discover', '-s', 'tests', '-v'], worktree),
        )
        return TestReport(
            ok=all(item.ok for item in checks),
            checks=checks,
            duration_ms=round((time.perf_counter() - started) * 1000, 3),
        )
