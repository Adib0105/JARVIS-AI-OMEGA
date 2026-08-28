from __future__ import annotations

import difflib
import hashlib
import os
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
        tracked = self._run(
            ['diff', '--name-only', '-z', 'HEAD', '--'], cwd=worktree
        )
        untracked = self._run(
            ['ls-files', '--others', '--exclude-standard', '-z'], cwd=worktree
        )
        if not tracked.ok or not untracked.ok:
            raise RuntimeError(
                tracked.stderr or untracked.stderr or 'Unable to inspect worktree status.'
            )
        return sorted({
            item for item in (tracked.stdout + untracked.stdout).split('\x00') if item
        })

    def untracked_files(self, worktree: Path) -> list[str]:
        result = self._run(
            ['ls-files', '--others', '--exclude-standard', '-z'], cwd=worktree
        )
        if not result.ok:
            raise RuntimeError(result.stderr or 'Unable to inspect untracked files.')
        return sorted(item for item in result.stdout.split('\x00') if item)

    def tracked_at_head(self, worktree: Path, path: str) -> bool:
        result = self._run(['cat-file', '-e', f'HEAD:{path}'], cwd=worktree)
        return result.ok

    @staticmethod
    def validate_materialized_files(worktree: Path, files: list[str]) -> list[str]:
        """Reject links, special files, binary text or oversized generated files."""
        root = worktree.resolve()
        reasons: list[str] = []
        for relative in files:
            target = root / relative
            if not target.exists() and not target.is_symlink():
                continue  # reviewed deletion
            if target.is_symlink():
                reasons.append(f'{relative}: symbolic links are not allowed in generated changes')
                continue
            try:
                resolved = target.resolve(strict=True)
            except OSError as exc:
                reasons.append(f'{relative}: cannot resolve changed file: {exc}')
                continue
            if root != resolved and root not in resolved.parents:
                reasons.append(f'{relative}: changed file escaped the sandbox')
                continue
            if not resolved.is_file():
                reasons.append(f'{relative}: only regular files may be generated')
                continue
            try:
                size = resolved.stat().st_size
                if size > 2_000_000:
                    reasons.append(f'{relative}: generated file exceeds the 2 MB limit')
                    continue
                raw = resolved.read_bytes()
                if b'\x00' in raw:
                    reasons.append(f'{relative}: binary/NUL content is not allowed')
                    continue
                raw.decode('utf-8')
            except (OSError, UnicodeDecodeError) as exc:
                reasons.append(f'{relative}: changed file is not reviewable UTF-8 text: {exc}')
        return reasons

    def diff(self, worktree: Path, *, max_chars: int = 200000) -> str:
        result = self._run(['diff', '--no-ext-diff', 'HEAD', '--'], cwd=worktree)
        if not result.ok:
            raise RuntimeError(result.stderr or 'Unable to create Git diff.')
        output = result.stdout
        root = worktree.resolve()
        for relative in self.untracked_files(worktree):
            target = root / relative
            if target.is_symlink() or not target.is_file():
                addition = f'\n--- /dev/null\n+++ b/{relative}\n[unreviewable non-regular file]\n'
            else:
                try:
                    raw = target.read_bytes()
                    text = raw.decode('utf-8')
                    addition = ''.join(difflib.unified_diff(
                        [], text.splitlines(keepends=True),
                        fromfile='/dev/null', tofile=f'b/{relative}',
                    ))
                except (OSError, UnicodeDecodeError):
                    addition = f'\n--- /dev/null\n+++ b/{relative}\n[unreviewable binary file]\n'
            if len(output) + len(addition) > max_chars:
                output += '\n[diff truncated at review limit]\n'
                break
            output += addition
        return output[:max_chars]

    def diff_stats(self, worktree: Path) -> tuple[list[str], int]:
        result = self._run(['diff', '--numstat', 'HEAD', '--'], cwd=worktree)
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
        for path in self.untracked_files(worktree):
            files.append(path)
            target = worktree.resolve() / path
            try:
                raw = target.read_bytes()
                lines += len(raw.splitlines())
            except OSError:
                # The materialized-file validator will reject it. Keep the path in
                # the inventory so it cannot disappear from review evidence.
                pass
        return sorted(set(files)), lines

    @staticmethod
    def snapshot_fingerprint(worktree: Path, files: list[str]) -> str:
        """Bind approval to exact paths, modes and bytes, including untracked files."""
        root = worktree.resolve()
        digest = hashlib.sha256()
        for relative in sorted(set(files)):
            target = root / relative
            digest.update(relative.encode('utf-8', errors='surrogateescape'))
            digest.update(b'\x00')
            if target.is_symlink():
                digest.update(b'SYMLINK\x00')
                digest.update(os.readlink(target).encode('utf-8', errors='surrogateescape'))
                continue
            if not target.exists():
                digest.update(b'DELETED\x00')
                continue
            stat = target.stat()
            digest.update(f'FILE:{stat.st_mode & 0o777:o}\x00'.encode('ascii'))
            with target.open('rb') as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                    digest.update(chunk)
            digest.update(b'\x00')
        return digest.hexdigest()

    def commit_worktree(
        self,
        worktree: Path,
        branch: str,
        files: list[str],
        message: str,
        *,
        expected_fingerprint: str,
    ) -> str:
        branch = self.validate_branch(branch)
        if self.current_branch(worktree) != branch:
            raise RuntimeError('Sandbox worktree is not on the expected improvement branch.')
        if not files:
            raise RuntimeError('No reviewed files supplied for improvement commit.')
        # Stage only the policy-reviewed paths. No broad `git add .` is used.
        add = self._run(['add', '--', *files], cwd=worktree)
        if not add.ok:
            raise RuntimeError(add.stderr or 'Unable to stage reviewed improvement files.')
        current_fingerprint = self.snapshot_fingerprint(worktree, files)
        if current_fingerprint != expected_fingerprint:
            raise RuntimeError(
                'Sandbox content changed while staging; deployment stopped for re-review.'
            )
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
