from __future__ import annotations

from pathlib import Path

from .analyzer import SelfDevelopmentAnalyzer
from .builder import SelfDevelopmentBuilder
from .evaluator import SelfDevelopmentEvaluator
from .planner import SelfDevelopmentPlanner
from .policies import SelfDevelopmentPolicy
from .proposal import ImprovementProposal, ProposalStatus, ProposalStore
from .rollback import RollbackManager
from .sandbox import SandboxManager
from .tester import SelfDevelopmentTester


class SelfDevelopmentEngine:
    """Controlled improvement pipeline that stops before production activation.

    Flow implemented here:
      GAP -> PROPOSAL -> ANALYZE/PLAN -> SANDBOX -> BUILD -> TEST -> POLICY/DIFF
      -> AWAITING_APPROVAL -> APPROVED/REJECTED

    A later controlled release engine owns production merge/deploy/monitor/rollback.
    This engine never silently writes to the production worktree.
    """

    def __init__(
        self,
        db_path: Path | None = None,
        *,
        repo_root: Path | None = None,
        workspace_root: Path | None = None,
    ) -> None:
        self.store = ProposalStore(db_path)
        self.policy = SelfDevelopmentPolicy()
        self.sandbox = SandboxManager(repo_root, workspace_root)
        self.analyzer = SelfDevelopmentAnalyzer(self.sandbox.repo_root)
        self.planner = SelfDevelopmentPlanner()
        self.tester = SelfDevelopmentTester(self.policy.max_build_time)
        self.evaluator = SelfDevelopmentEvaluator()
        self.rollback = RollbackManager(db_path)

    @staticmethod
    def _require(proposal: ImprovementProposal | None, allowed: set[ProposalStatus]) -> ImprovementProposal:
        if proposal is None:
            raise KeyError('Improvement proposal not found.')
        if proposal.status not in allowed:
            names = ', '.join(sorted(item.value for item in allowed))
            raise RuntimeError(f'Proposal {proposal.id} is {proposal.status.value}; expected one of: {names}.')
        return proposal

    def proposal_from_gap(self, gap: dict) -> ImprovementProposal:
        capability = str(gap.get('capability') or 'Unknown Capability')[:160]
        title = str(gap.get('title') or f'Improve {capability}')[:240]
        problem = str(gap.get('description') or 'Capability gap detected from persisted evidence.')[:4000]
        objective = str(gap.get('recommended_action') or f'Resolve the measured {capability} gap without regressions.')[:4000]
        evidence = [str(item)[:1000] for item in gap.get('evidence', [])][:30]
        proposal = ImprovementProposal(
            title=title,
            capability=capability,
            problem=problem,
            objective=objective,
            evidence=evidence,
            risk=str(gap.get('severity') or 'MEDIUM'),
            source_gap_id=str(gap.get('id') or '') or None,
        )
        analysis = self.analyzer.analyze(capability, problem, evidence)
        plan = self.planner.plan(analysis)
        proposal.plan = list(plan.steps)
        proposal.policy_summary = {
            'analysis': analysis.as_dict(),
            'required_tests': list(plan.required_tests),
            'stop_conditions': list(plan.stop_conditions),
        }
        self.store.save(proposal)
        return proposal

    def prepare_sandbox(self, proposal_id: str) -> ImprovementProposal:
        proposal = self._require(self.store.get(proposal_id), {ProposalStatus.PROPOSED})
        info = self.sandbox.create(proposal.id)
        proposal.branch = info.branch
        proposal.sandbox_path = info.path
        proposal.touch(ProposalStatus.SANDBOX_READY)
        self.rollback.create(proposal.id, info.base_head)
        self.store.save(proposal)
        return proposal

    def apply_changes(self, proposal_id: str, changes: dict[str, str]) -> ImprovementProposal:
        proposal = self._require(
            self.store.get(proposal_id),
            {ProposalStatus.SANDBOX_READY, ProposalStatus.FAILED},
        )
        if not proposal.sandbox_path:
            raise RuntimeError('Proposal has no prepared sandbox.')
        builder = SelfDevelopmentBuilder(Path(proposal.sandbox_path), self.policy)
        written = builder.apply(changes)
        proposal.changed_files = sorted({item.path for item in written})
        proposal.test_summary = {'build_changes': [item.as_dict() for item in written]}
        proposal.touch(ProposalStatus.SANDBOX_READY)
        self.store.save(proposal)
        return proposal

    def run_tests(self, proposal_id: str) -> ImprovementProposal:
        proposal = self._require(
            self.store.get(proposal_id),
            {ProposalStatus.SANDBOX_READY, ProposalStatus.FAILED},
        )
        if not proposal.sandbox_path:
            raise RuntimeError('Proposal has no prepared sandbox.')
        proposal.touch(ProposalStatus.TESTING)
        self.store.save(proposal)
        report = self.tester.run_regression(Path(proposal.sandbox_path))
        existing_build = dict(proposal.test_summary)
        existing_build['regression'] = report.as_dict()
        proposal.test_summary = existing_build
        proposal.touch(ProposalStatus.TESTED if report.ok else ProposalStatus.FAILED)
        self.store.save(proposal)
        return proposal

    def review(self, proposal_id: str) -> ImprovementProposal:
        proposal = self._require(self.store.get(proposal_id), {ProposalStatus.TESTED})
        worktree = Path(proposal.sandbox_path)
        files, lines = self.sandbox.git.diff_stats(worktree)
        check = self.policy.validate_change_set(files, lines)
        diff = self.sandbox.git.diff(worktree)
        code_changed = any(path.endswith(('.py', '.js', '.ts', '.tsx', '.jsx', '.ps1', '.bat', '.sh')) for path in files)
        tests_changed = any(path.replace('\\', '/').startswith('tests/') for path in files)
        reasons = list(check.reasons)
        if not files:
            reasons.append('No sandbox changes exist.')
        if code_changed and not tests_changed:
            reasons.append('Code changed without a changed/added regression test.')

        tests_ok = bool((proposal.test_summary.get('regression') or {}).get('ok'))
        policy_ok = check.allowed and not reasons
        evaluation = self.evaluator.compare({}, {}, tests_passed=tests_ok, policy_passed=policy_ok)
        proposal.changed_files = files
        proposal.policy_summary = {
            **proposal.policy_summary,
            'change_check': check.as_dict(),
            'review_reasons': reasons,
            'tests_changed': tests_changed,
            'code_changed': code_changed,
        }
        proposal.evaluation_summary = evaluation.as_dict()
        proposal.diff_summary = diff[:200000]
        if tests_ok and policy_ok and evaluation.passed:
            proposal.touch(ProposalStatus.AWAITING_APPROVAL)
        else:
            proposal.touch(ProposalStatus.FAILED)
        self.store.save(proposal)
        return proposal

    def approve(self, proposal_id: str, *, explicit_user_approval: bool) -> ImprovementProposal:
        proposal = self._require(self.store.get(proposal_id), {ProposalStatus.AWAITING_APPROVAL})
        if not self.policy.can_activate_production(explicit_user_approval=explicit_user_approval):
            raise PermissionError('Explicit production approval is required. No code was deployed.')
        proposal.touch(ProposalStatus.APPROVED)
        self.store.save(proposal)
        return proposal

    def reject(self, proposal_id: str) -> ImprovementProposal:
        proposal = self._require(
            self.store.get(proposal_id),
            {ProposalStatus.PROPOSED, ProposalStatus.SANDBOX_READY, ProposalStatus.TESTED, ProposalStatus.AWAITING_APPROVAL},
        )
        proposal.touch(ProposalStatus.REJECTED)
        self.store.save(proposal)
        return proposal

    def get(self, proposal_id: str) -> dict | None:
        proposal = self.store.get(proposal_id)
        return proposal.as_dict() if proposal else None

    def recent(self, limit: int = 50) -> list[dict]:
        return self.store.list_recent(limit)
