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
    """Small allowlisted Git wrapper for isolated improvements and controlled release."""

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

    def head(self, cwd: Path | None = None) -> str:
        result = self._run(['rev-parse', 'HEAD'], cwd=cwd)
        if not result.ok:
            raise RuntimeError(result.stderr or 'Unable to read Git HEAD.')
        return result.stdout.strip()

    def current_branch(self, cwd: Path | None = None) -> str:
        result = self._run(['branch', '--show-current'], cwd=cwd)
        if not result.ok:
            raise RuntimeError(result.stderr or 'Unable to read Git branch.')
        return result.stdout.strip()

    def is_clean(self, cwd: Path | None = None) -> bool:
        result = self._run(['status', '--porcelain=v1'], cwd=cwd)
        if not result.ok:
            raise RuntimeError(result.stderr or 'Unable to inspect Git status.')
        return not result.stdout.strip()

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
        files.extend(self.status_files(worktree))
        return sorted(set(files)), lines

    def commit_worktree(self, worktree: Path, branch: str, files: list[str], message: str) -> str:
        branch = self.validate_branch(branch)
        if self.current_branch(worktree) != branch:
            raise RuntimeError('Sandbox worktree is not on the expected improvement branch.')
        if not files:
            raise RuntimeError('No reviewed files supplied for improvement commit.')
        # Stage only the policy-reviewed paths. No broad `git add .` is used.
        add = self._run(['add', '--', *files], cwd=worktree)
        if not add.ok:
            raise RuntimeError(add.stderr or 'Unable to stage reviewed improvement files.')
        commit = self._run(['commit', '-m', message[:240]], cwd=worktree)
        if not commit.ok:
            raise RuntimeError(commit.stderr or commit.stdout or 'Unable to commit improvement branch.')
        return self.head(worktree)

    def fast_forward_production(self, branch: str, *, expected_head: str) -> str:
        branch = self.validate_branch(branch)
        if self.head(self.repo_root) != expected_head:
            raise RuntimeError('Production HEAD changed since sandbox creation; deployment stopped for rebase/review.')
        if not self.is_clean(self.repo_root):
            raise RuntimeError('Production worktree is not clean; deployment stopped.')
        result = self._run(['merge', '--ff-only', branch], cwd=self.repo_root, timeout=180)
        if not result.ok:
            raise RuntimeError(result.stderr or result.stdout or 'Fast-forward production deployment failed.')
        return self.head(self.repo_root)

    def revert_deployed_commit(self, deployed_sha: str, *, expected_current_head: str | None = None) -> str:
        if expected_current_head and self.head(self.repo_root) != expected_current_head:
            raise RuntimeError('Production HEAD changed after deployment; automatic rollback stopped for manual review.')
        if not self.is_clean(self.repo_root):
            raise RuntimeError('Production worktree is not clean; rollback stopped.')
        result = self._run(['revert', '--no-edit', deployed_sha], cwd=self.repo_root, timeout=180)
        if not result.ok:
            # Abort any partial revert state so the worktree is not left in conflict mode.
            self._run(['revert', '--abort'], cwd=self.repo_root, timeout=30)
            raise RuntimeError(result.stderr or result.stdout or 'Controlled Git revert failed.')
        return self.head(self.repo_root)

    def remove_worktree(self, worktree: Path) -> None:
        worktree = worktree.resolve()
        result = self._run(['worktree', 'remove', '--force', str(worktree)], timeout=120)
        if not result.ok:
            raise RuntimeError(result.stderr or result.stdout or 'Unable to remove sandbox worktree.')

    def delete_experiment_branch(self, branch: str) -> None:
        branch = self.validate_branch(branch)
        result = self._run(['branch', '-D', branch])
        if not result.ok:
            raise RuntimeError(result.stderr or result.stdout or 'Unable to delete experiment branch.')
