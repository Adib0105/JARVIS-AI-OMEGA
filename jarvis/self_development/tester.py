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
    """Use the shared opt-in container boundary; never execute host Python."""

    def __init__(self, timeout: int = 300) -> None:
        self.timeout = max(10, min(int(timeout), 900))

    def _run(self, name: str, args: list[str], cwd: Path) -> CheckResult:
        from ..code_execution import COMMANDS, DockerCodeRunner
        if COMMANDS.get(name) != args:
            raise PermissionError('Test command is not allowlisted.')
        try:
            result = DockerCodeRunner().run(cwd, kind=name, timeout=self.timeout)
        except PermissionError as exc:
            return CheckResult(name, False, 126, 0.0, '', str(exc))
        return CheckResult(name, result['ok'], result['returncode'], result['duration_ms'],
                           result['stdout'], result['stderr'] + ('\n' + result['error'] if result.get('error') else ''))

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
