from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..evaluation.benchmark import AgentEvaluationBenchmark, ScenarioResult
if TYPE_CHECKING:
    from .engine import SelfDevelopmentEngine

@dataclass(frozen=True)
class ImprovementBenchmarkResult:
    proposal_id: str
    before_id: str
    after_id: str
    comparison: dict
    def as_dict(self)->dict: return {'proposal_id':self.proposal_id,'before_id':self.before_id,'after_id':self.after_id,'comparison':dict(self.comparison)}

class SelfImprovementBenchmark:
    """Attach deterministic before/after benchmark evidence to an improvement proposal."""
    def __init__(self, development: SelfDevelopmentEngine, benchmark: AgentEvaluationBenchmark)->None:
        self.development=development; self.benchmark=benchmark
    def record_baseline(self, proposal_id: str, results: list[ScenarioResult])->dict:
        proposal=self.development.store.get(proposal_id)
        if proposal is None: raise KeyError(proposal_id)
        if not results: raise ValueError('Baseline benchmark requires at least one deterministic scenario result.')
        snapshot=self.benchmark.record(f'{proposal_id}:before',results); proposal.evaluation_summary['benchmark_before_id']=snapshot.id; proposal.evaluation_summary['benchmark_before']=snapshot.metrics; self.development.store.save(proposal); return snapshot.as_dict()
    def record_after(self, proposal_id: str, results: list[ScenarioResult])->ImprovementBenchmarkResult:
        proposal=self.development.store.get(proposal_id)
        if proposal is None: raise KeyError(proposal_id)
        if not results: raise ValueError('Candidate benchmark requires at least one deterministic scenario result.')
        before_id=proposal.evaluation_summary.get('benchmark_before_id')
        if not before_id: raise RuntimeError('Record the before benchmark before post-change evaluation.')
        before=next((item for item in self.benchmark.history(1000) if item.get('id')==before_id),None)
        if before is None: raise RuntimeError('Stored baseline benchmark could not be found.')
        after=self.benchmark.record(f'{proposal_id}:after',results); comparison=self.benchmark.compare(before,after.as_dict()); proposal.evaluation_summary['benchmark_after_id']=after.id; proposal.evaluation_summary['benchmark_after']=after.metrics; proposal.evaluation_summary['benchmark_comparison']=comparison; self.development.store.save(proposal); return ImprovementBenchmarkResult(proposal_id,before_id,after.id,comparison)
    def evidence_allows_success(self, proposal_id: str)->bool:
        proposal=self.development.store.get(proposal_id)
        if proposal is None: raise KeyError(proposal_id)
        comparison=proposal.evaluation_summary.get('benchmark_comparison') or {}; regression=proposal.test_summary.get('regression') or {}
        return bool(regression.get('ok') and proposal.evaluation_summary.get('benchmark_before_id') and proposal.evaluation_summary.get('benchmark_after_id') and comparison.get('successful_improvement') and not comparison.get('regressions'))
