from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


_BRANCH_RE = re.compile(r'^self-improvement/IMP-[A-Z0-9]{8,12}$')


@dataclass(frozen=True)
class GitCommandResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class SelfDevelopmentGitManager:
    """Small allowlisted Git wrapper used only for isolated improvement worktrees."""

    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
        self.git = shutil.which('git')
        if not self.git:
            raise RuntimeError('Git executable is required for self-development sandboxing.')
        if not (self.repo_root / '.git').exists():
            raise RuntimeError(f'Not a Git repository: {self.repo_root}')

    def _run(self, args: list[str], *, cwd: Path | None = None, timeout: int = 120) -> GitCommandResult:
        proc = subprocess.run(
            [self.git, *args],
            cwd=str((cwd or self.repo_root).resolve()),
            text=True,
            capture_output=True,
            timeout=max(5, min(int(timeout), 600)),
            check=False,
        )
        return GitCommandResult(proc.returncode, proc.stdout[-200000:], proc.stderr[-50000:])

    @staticmethod
    def validate_branch(branch: str) -> str:
        branch = branch.strip()
        if not _BRANCH_RE.fullmatch(branch):
            raise ValueError('Self-development branch must match self-improvement/IMP-XXXXXXXX.')
        return branch

    def head(self) -> str:
        result = self._run(['rev-parse', 'HEAD'])
        if not result.ok:
            raise RuntimeError(result.stderr or 'Unable to read Git HEAD.')
        return result.stdout.strip()

    def create_worktree(self, branch: str, destination: Path, *, base: str = 'HEAD') -> Path:
        branch = self.validate_branch(branch)
        destination = destination.resolve()
        if destination.exists() and any(destination.iterdir()):
            raise FileExistsError(f'Sandbox is not empty: {destination}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        result = self._run(['worktree', 'add', '-b', branch, str(destination), base], timeout=180)
        if not result.ok:
            raise RuntimeError(result.stderr or result.stdout or 'Unable to create Git worktree.')
        return destination

    def status_files(self, worktree: Path) -> list[str]:
        result = self._run(['status', '--porcelain=v1'], cwd=worktree)
        if not result.ok:
            raise RuntimeError(result.stderr or 'Unable to inspect worktree status.')
        output: list[str] = []
        for line in result.stdout.splitlines():
            if len(line) < 4:
                continue
            raw = line[3:].strip()
            if ' -> ' in raw:
                raw = raw.split(' -> ', 1)[1]
            output.append(raw)
        return sorted(set(output))

    def diff(self, worktree: Path, *, max_chars: int = 200000) -> str:
        result = self._run(['diff', '--no-ext-diff', '--'], cwd=worktree)
        if not result.ok:
            raise RuntimeError(result.stderr or 'Unable to create Git diff.')
        return result.stdout[:max_chars]

    def diff_stats(self, worktree: Path) -> tuple[list[str], int]:
        result = self._run(['diff', '--numstat', '--'], cwd=worktree)
        if not result.ok:
            raise RuntimeError(result.stderr or 'Unable to calculate Git diff stats.')
        files: list[str] = []
        lines = 0
        for row in result.stdout.splitlines():
            parts = row.split('\t', 2)
            if len(parts) != 3:
                continue
            added, removed, path = parts
            files.append(path)
            if added.isdigit():
                lines += int(added)
            if removed.isdigit():
                lines += int(removed)
        # Include untracked files in the policy file list. Their line count is
        # intentionally not guessed here; builder/tester stages can measure them.
        files.extend(self.status_files(worktree))
        return sorted(set(files)), lines

    def remove_worktree(self, worktree: Path) -> None:
        worktree = worktree.resolve()
        # Git itself validates that this is a registered worktree. No arbitrary
        # filesystem deletion command is exposed by this class.
        result = self._run(['worktree', 'remove', '--force', str(worktree)], timeout=120)
        if not result.ok:
            raise RuntimeError(result.stderr or result.stdout or 'Unable to remove sandbox worktree.')

    def delete_experiment_branch(self, branch: str) -> None:
        branch = self.validate_branch(branch)
        result = self._run(['branch', '-D', branch])
        if not result.ok:
            raise RuntimeError(result.stderr or result.stdout or 'Unable to delete experiment branch.')
