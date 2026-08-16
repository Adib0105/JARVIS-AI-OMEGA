from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .git_manager import SelfDevelopmentGitManager


@dataclass(frozen=True)
class SandboxInfo:
    proposal_id: str
    branch: str
    path: str
    base_head: str

    def as_dict(self) -> dict:
        return {
            'proposal_id': self.proposal_id,
            'branch': self.branch,
            'path': self.path,
            'base_head': self.base_head,
        }


class SandboxManager:
    """Creates Git worktree sandboxes outside the production source tree."""

    def __init__(self, repo_root: Path | None = None, workspace_root: Path | None = None) -> None:
        self.repo_root = (repo_root or Path(__file__).resolve().parents[2]).resolve()
        self.workspace_root = (workspace_root or self.repo_root / 'workspace').resolve()
        self.git = SelfDevelopmentGitManager(self.repo_root)
        self._init_layout()

    def _init_layout(self) -> None:
        for name in ('development', 'sandbox', 'experiments', 'backups'):
            (self.workspace_root / name).mkdir(parents=True, exist_ok=True)

    def sandbox_path(self, proposal_id: str) -> Path:
        safe = proposal_id.strip().upper()
        if not safe.startswith('IMP-') or not safe.replace('-', '').isalnum():
            raise ValueError('Invalid improvement proposal ID.')
        target = (self.workspace_root / 'sandbox' / safe).resolve()
        sandbox_root = (self.workspace_root / 'sandbox').resolve()
        if sandbox_root not in target.parents:
            raise ValueError('Sandbox path escaped workspace.')
        return target

    def create(self, proposal_id: str) -> SandboxInfo:
        branch = f'self-improvement/{proposal_id.strip().upper()}'
        target = self.sandbox_path(proposal_id)
        base_head = self.git.head()
        self.git.create_worktree(branch, target, base=base_head)
        return SandboxInfo(proposal_id.upper(), branch, str(target), base_head)

    def destroy(self, proposal_id: str, *, delete_branch: bool = False) -> None:
        branch = f'self-improvement/{proposal_id.strip().upper()}'
        target = self.sandbox_path(proposal_id)
        if target.exists():
            self.git.remove_worktree(target)
        if delete_branch:
            self.git.delete_experiment_branch(branch)
