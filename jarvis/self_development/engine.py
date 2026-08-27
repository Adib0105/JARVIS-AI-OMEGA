from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from ..evaluation.benchmark import AgentEvaluationBenchmark
from .analyzer import SelfDevelopmentAnalyzer
from .builder import SelfDevelopmentBuilder
from .evaluator import SelfDevelopmentEvaluator
from .lease import DevelopmentLeaseStore
from .planner import SelfDevelopmentPlanner
from .policies import SelfDevelopmentPolicy
from .proposal import ImprovementProposal, ProposalStatus, ProposalStore
from .rollback import RollbackManager
from .sandbox import SandboxManager
from .tester import SelfDevelopmentTester


class SelfDevelopmentEngine:
    """Controlled, cross-process-safe improvement pipeline."""

    def __init__(self, db_path: Path | None = None, *, repo_root: Path | None = None, workspace_root: Path | None = None) -> None:
        self.store = ProposalStore(db_path)
        self.benchmark = AgentEvaluationBenchmark(db_path)
        self.policy = SelfDevelopmentPolicy()
        self.sandbox = SandboxManager(repo_root, workspace_root)
        self.analyzer = SelfDevelopmentAnalyzer(self.sandbox.repo_root)
        self.planner = SelfDevelopmentPlanner()
        self.tester = SelfDevelopmentTester(self.policy.max_build_time)
        self.evaluator = SelfDevelopmentEvaluator()
        self.rollback = RollbackManager(db_path)
        self.leases = DevelopmentLeaseStore(db_path, default_ttl_seconds=max(120, self.policy.max_build_time + 120))
        self.recovery_summary = self.recover_interrupted()

    @staticmethod
    def _require(proposal: ImprovementProposal | None, allowed: set[ProposalStatus]) -> ImprovementProposal:
        if proposal is None:
            raise KeyError('Improvement proposal not found.')
        if proposal.status not in allowed:
            names = ', '.join(sorted(item.value for item in allowed))
            raise RuntimeError(f'Proposal {proposal.id} is {proposal.status.value}; expected one of: {names}.')
        return proposal

    @contextmanager
    def operation(self, proposal_id: str, operation: str, *, lease_token: str | None = None):
        with self.leases.hold(proposal_id, operation, owner_token=lease_token, ttl_seconds=max(120, self.policy.max_build_time + 120)) as lease:
            yield lease.owner_token

    def recover_interrupted(self) -> dict:
        expired = self.leases.cleanup_expired()
        recovered: list[dict] = []
        interrupted = {ProposalStatus.TESTING, ProposalStatus.SECURITY_REVIEW, ProposalStatus.EVALUATED}
        requires_sandbox = {ProposalStatus.SANDBOX_READY, ProposalStatus.TESTING, ProposalStatus.TESTED, ProposalStatus.EVALUATED, ProposalStatus.SECURITY_REVIEW, ProposalStatus.AWAITING_APPROVAL, ProposalStatus.APPROVED}
        for row in self.store.list_recent(500):
            proposal_id = str(row.get('id') or '')
            proposal = self.store.get(proposal_id) if proposal_id else None
            if proposal is None or self.leases.get(proposal.id) is not None:
                continue
            reason = ''
            if proposal.status in interrupted:
                reason = f'Interrupted {proposal.status.value} operation had no active lease.'
            elif proposal.status in requires_sandbox:
                sandbox_path = Path(proposal.sandbox_path) if proposal.sandbox_path else None
                if sandbox_path is None or not sandbox_path.exists():
                    reason = 'Recorded self-development sandbox is missing.'
            if not reason:
                continue
            previous = proposal.status.value
            proposal.test_summary = {**dict(proposal.test_summary or {}), 'recovery': {'previous_status': previous, 'reason': reason, 'safe_to_retry': True}}
            proposal.touch(ProposalStatus.FAILED)
            self.store.save(proposal)
            recovered.append({'proposal_id': proposal.id, 'from': previous, 'reason': reason})
        return {'expired_leases_removed': expired, 'recovered': recovered}

    def proposal_from_gap(self, gap: dict) -> ImprovementProposal:
        capability = str(gap.get('capability') or 'Unknown Capability')[:160]
        proposal = ImprovementProposal(title=str(gap.get('title') or f'Improve {capability}')[:240], capability=capability, problem=str(gap.get('description') or 'Capability gap detected from persisted evidence.')[:4000], objective=str(gap.get('recommended_action') or f'Resolve the measured {capability} gap without regressions.')[:4000], evidence=[str(item)[:1000] for item in gap.get('evidence', [])][:30], risk=str(gap.get('severity') or 'MEDIUM'), source_gap_id=str(gap.get('id') or '') or None)
        analysis = self.analyzer.analyze(capability, proposal.problem, proposal.evidence)
        plan = self.planner.plan(analysis)
        proposal.plan = list(plan.steps)
        proposal.policy_summary = {'analysis': analysis.as_dict(), 'required_tests': list(plan.required_tests), 'stop_conditions': list(plan.stop_conditions)}
        self.store.save(proposal)
        return proposal

    def prepare_sandbox(self, proposal_id: str, *, _lease_token: str | None = None) -> ImprovementProposal:
        with self.operation(proposal_id, 'prepare-sandbox', lease_token=_lease_token):
            proposal = self._require(self.store.get(proposal_id), {ProposalStatus.PROPOSED})
            info = self.sandbox.create(proposal.id)
            proposal.branch, proposal.sandbox_path = info.branch, info.path
            proposal.touch(ProposalStatus.SANDBOX_READY)
            self.rollback.create(proposal.id, info.base_head)
            self.store.save(proposal)
            return proposal

    def apply_changes(self, proposal_id: str, changes: dict[str, str], *, _lease_token: str | None = None) -> ImprovementProposal:
        with self.operation(proposal_id, 'apply-changes', lease_token=_lease_token):
            proposal = self._require(self.store.get(proposal_id), {ProposalStatus.SANDBOX_READY, ProposalStatus.FAILED})
            if not proposal.sandbox_path:
                raise RuntimeError('Proposal has no prepared sandbox.')
            written = SelfDevelopmentBuilder(Path(proposal.sandbox_path), self.policy).apply(changes)
            proposal.changed_files = sorted(set(proposal.changed_files) | {item.path for item in written})
            proposal.test_summary = {**dict(proposal.test_summary or {}), 'build_changes': [item.as_dict() for item in written]}
            proposal.touch(ProposalStatus.SANDBOX_READY)
            self.store.save(proposal)
            return proposal

    def run_tests(self, proposal_id: str, *, _lease_token: str | None = None) -> ImprovementProposal:
        with self.operation(proposal_id, 'run-tests', lease_token=_lease_token) as token:
            proposal = self._require(self.store.get(proposal_id), {ProposalStatus.SANDBOX_READY, ProposalStatus.FAILED})
            if not proposal.sandbox_path:
                raise RuntimeError('Proposal has no prepared sandbox.')
            proposal.touch(ProposalStatus.TESTING); self.store.save(proposal)
            self.leases.refresh(proposal.id, token, operation='run-tests')
            report = self.tester.run_regression(Path(proposal.sandbox_path))
            proposal.test_summary = {**dict(proposal.test_summary), 'regression': report.as_dict()}
            proposal.touch(ProposalStatus.TESTED if report.ok else ProposalStatus.FAILED)
            self.store.save(proposal)
            return proposal

    def _persisted_benchmark_evidence(self, proposal: ImprovementProposal) -> tuple[dict, dict, list[str]]:
        summary = proposal.evaluation_summary or {}
        before_id, after_id = summary.get('benchmark_before_id'), summary.get('benchmark_after_id')
        reasons: list[str] = []
        if not before_id:
            reasons.append('Missing persisted baseline benchmark evidence.')
        if not after_id:
            reasons.append('Missing persisted candidate benchmark evidence.')
        if reasons:
            return {}, {}, reasons
        history = self.benchmark.history(1000)
        by_id = {item.get('id'): item for item in history if isinstance(item, dict)}
        before, after = by_id.get(before_id), by_id.get(after_id)
        if before is None:
            reasons.append('Persisted baseline benchmark snapshot was not found.')
        if after is None:
            reasons.append('Persisted candidate benchmark snapshot was not found.')
        if reasons:
            return before or {}, after or {}, reasons
        if before.get('label') != f'{proposal.id}:before':
            reasons.append('Baseline benchmark is not bound to this proposal.')
        if after.get('label') != f'{proposal.id}:after':
            reasons.append('Candidate benchmark is not bound to this proposal.')
        for name, snapshot in (('baseline', before), ('candidate', after)):
            if not isinstance(snapshot.get('results'), list) or not snapshot['results']:
                reasons.append(f'Persisted {name} benchmark has no scenario evidence.')
            if not isinstance(snapshot.get('metrics'), dict) or not snapshot['metrics']:
                reasons.append(f'Persisted {name} benchmark has invalid metrics.')
        return before, after, reasons

    def review(self, proposal_id: str, *, _lease_token: str | None = None) -> ImprovementProposal:
        with self.operation(proposal_id, 'review', lease_token=_lease_token):
            proposal = self._require(self.store.get(proposal_id), {ProposalStatus.TESTED})
            worktree = Path(proposal.sandbox_path)
            files, lines = self.sandbox.git.diff_stats(worktree)
            check = self.policy.validate_change_set(files, lines)
            diff = self.sandbox.git.diff(worktree)
            code_changed = any(path.endswith(('.py', '.js', '.ts', '.tsx', '.jsx', '.ps1', '.bat', '.sh')) for path in files)
            tests_changed = any(path.replace('\\', '/').startswith('tests/') for path in files)
            reasons = list(check.reasons)
            if not files: reasons.append('No sandbox changes exist.')
            if code_changed and not tests_changed: reasons.append('Code changed without a changed/added regression test.')
            tests_ok = bool((proposal.test_summary.get('regression') or {}).get('ok'))
            before, after, evidence_reasons = self._persisted_benchmark_evidence(proposal)
            reasons.extend(evidence_reasons)
            policy_ok = check.allowed and not [r for r in reasons if r not in evidence_reasons]
            evaluation = self.evaluator.compare(before, after, tests_passed=tests_ok, policy_passed=policy_ok and not evidence_reasons)
            persisted = dict(proposal.evaluation_summary or {})
            proposal.changed_files = files
            proposal.policy_summary = {**proposal.policy_summary, 'change_check': check.as_dict(), 'review_reasons': reasons, 'tests_changed': tests_changed, 'code_changed': code_changed}
            proposal.evaluation_summary = {**persisted, **evaluation.as_dict(), 'evidence_status': 'VALID' if not evidence_reasons else 'INSUFFICIENT EVIDENCE', 'evidence_reasons': evidence_reasons}
            proposal.diff_summary = diff[:200000]
            proposal.touch(ProposalStatus.AWAITING_APPROVAL if tests_ok and policy_ok and not evidence_reasons and evaluation.passed else ProposalStatus.FAILED)
            self.store.save(proposal)
            return proposal

    def approve(self, proposal_id: str, *, explicit_user_approval: bool, _lease_token: str | None = None) -> ImprovementProposal:
        with self.operation(proposal_id, 'approve', lease_token=_lease_token):
            proposal = self._require(self.store.get(proposal_id), {ProposalStatus.AWAITING_APPROVAL})
            if not self.policy.can_activate_production(explicit_user_approval=explicit_user_approval):
                raise PermissionError('Explicit production approval is required. No code was deployed.')
            proposal.touch(ProposalStatus.APPROVED); self.store.save(proposal); return proposal

    def reject(self, proposal_id: str, *, _lease_token: str | None = None) -> ImprovementProposal:
        with self.operation(proposal_id, 'reject', lease_token=_lease_token):
            proposal = self._require(self.store.get(proposal_id), {ProposalStatus.PROPOSED, ProposalStatus.SANDBOX_READY, ProposalStatus.TESTED, ProposalStatus.AWAITING_APPROVAL})
            proposal.touch(ProposalStatus.REJECTED); self.store.save(proposal); return proposal

    def get(self, proposal_id: str) -> dict | None:
        proposal = self.store.get(proposal_id); return proposal.as_dict() if proposal else None

    def recent(self, limit: int = 50) -> list[dict]:
        return self.store.list_recent(limit)
