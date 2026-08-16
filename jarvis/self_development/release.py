from __future__ import annotations

from pathlib import Path

from ..config import settings
from .engine import SelfDevelopmentEngine
from .proposal import ProposalStatus


class ControlledReleaseEngine:
    """Explicitly approved production activation for reviewed sandbox improvements.

    Safety gates:
    - proposal must already be APPROVED
    - sandbox tests are re-run immediately before release
    - current diff must still pass immutable-core/file/line policy
    - production worktree must be clean
    - production HEAD must equal the original sandbox base checkpoint
    - deployment is fast-forward only
    - post-deploy full tests run in production
    - optional automatic rollback uses a history-preserving Git revert
    """

    def __init__(self, development: SelfDevelopmentEngine) -> None:
        self.development = development

    def deploy(
        self,
        proposal_id: str,
        *,
        explicit_user_approval: bool,
        auto_rollback: bool | None = None,
    ) -> dict:
        if not explicit_user_approval:
            raise PermissionError('Explicit production release approval is required.')
        if not settings.production_self_modification:
            raise PermissionError(
                'Production self-modification is disabled by configuration. '
                'Enable it deliberately only when you want the approved release engine to deploy.'
            )
        proposal = self.development._require(
            self.development.store.get(proposal_id), {ProposalStatus.APPROVED}
        )
        if not proposal.sandbox_path or not proposal.branch:
            raise RuntimeError('Approved proposal has no verified sandbox/branch.')
        worktree = Path(proposal.sandbox_path)

        # Re-test immediately before release.
        report = self.development.tester.run_regression(worktree)
        if not report.ok:
            proposal.test_summary['pre_release_regression'] = report.as_dict()
            proposal.touch(ProposalStatus.FAILED)
            self.development.store.save(proposal)
            raise RuntimeError('Pre-release regression suite failed; production was not modified.')

        files, lines = self.development.sandbox.git.diff_stats(worktree)
        policy = self.development.policy.validate_change_set(files, lines)
        if not policy.allowed:
            raise PermissionError('Release policy rejected current sandbox diff: ' + '; '.join(policy.reasons))
        if set(files) != set(proposal.changed_files):
            raise RuntimeError('Sandbox diff changed after approval; re-review is required before release.')

        checkpoint = self.development.rollback.get(proposal.id)
        if checkpoint is None:
            raise RuntimeError('Known-good rollback checkpoint is missing.')

        deployed_commit = self.development.sandbox.git.commit_worktree(
            worktree,
            proposal.branch,
            files,
            f'JARVIS self-improvement {proposal.id}: {proposal.title}',
        )
        production_head = self.development.sandbox.git.fast_forward_production(
            proposal.branch,
            expected_head=checkpoint.before_sha,
        )
        if production_head != deployed_commit:
            raise RuntimeError('Production HEAD does not match the reviewed improvement commit.')

        self.development.rollback.mark_deployed(proposal.id, deployed_commit)
        post = self.development.tester.run_regression(self.development.sandbox.repo_root)
        proposal.test_summary['post_release_regression'] = post.as_dict()
        proposal.touch(ProposalStatus.DEPLOYED if post.ok else ProposalStatus.FAILED)
        self.development.store.save(proposal)

        if post.ok:
            return {
                'ok': True,
                'proposal_id': proposal.id,
                'before_sha': checkpoint.before_sha,
                'deployed_sha': deployed_commit,
                'post_release_tests': post.as_dict(),
                'rollback': None,
            }

        reason = 'Post-release regression suite failed.'
        self.development.rollback.mark_rollback_required(proposal.id, reason)
        should_rollback = settings.auto_rollback_enabled if auto_rollback is None else bool(auto_rollback)
        rollback_result = None
        if should_rollback:
            rollback_result = self.rollback(
                proposal.id,
                explicit_confirmation=True,
                expected_current_head=deployed_commit,
            )
        return {
            'ok': False,
            'proposal_id': proposal.id,
            'before_sha': checkpoint.before_sha,
            'deployed_sha': deployed_commit,
            'post_release_tests': post.as_dict(),
            'rollback': rollback_result,
            'message': reason,
        }

    def rollback(
        self,
        proposal_id: str,
        *,
        explicit_confirmation: bool,
        expected_current_head: str | None = None,
    ) -> dict:
        if not explicit_confirmation:
            raise PermissionError('Explicit rollback confirmation is required.')
        checkpoint = self.development.rollback.get(proposal_id)
        if checkpoint is None or not checkpoint.deployed_sha:
            raise RuntimeError('No deployed commit is registered for this proposal.')
        current_expected = expected_current_head or checkpoint.deployed_sha
        reverted_head = self.development.sandbox.git.revert_deployed_commit(
            checkpoint.deployed_sha,
            expected_current_head=current_expected,
        )
        verification = self.development.tester.run_regression(self.development.sandbox.repo_root)
        proposal = self.development.store.get(proposal_id)
        if proposal is not None:
            proposal.test_summary['rollback_regression'] = verification.as_dict()
            proposal.touch(ProposalStatus.ROLLED_BACK if verification.ok else ProposalStatus.FAILED)
            self.development.store.save(proposal)
        self.development.rollback.mark_rollback_required(
            proposal_id,
            'Rollback completed and verified.' if verification.ok else 'Rollback commit created but regression verification failed.',
        )
        return {
            'ok': verification.ok,
            'proposal_id': proposal_id,
            'reverted_commit': checkpoint.deployed_sha,
            'rollback_head': reverted_head,
            'tests': verification.as_dict(),
        }
