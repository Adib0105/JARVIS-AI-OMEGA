from __future__ import annotations

from dataclasses import dataclass


LOWER_IS_BETTER = {'tool_error_rate', 'average_tool_latency_ms', 'average_latency_ms', 'safety_violation_rate'}


@dataclass(frozen=True)
class ImprovementEvaluation:
    passed: bool
    improved_metrics: tuple[str, ...]
    regressed_metrics: tuple[str, ...]
    unchanged_metrics: tuple[str, ...]
    notes: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            'passed': self.passed,
            'improved_metrics': list(self.improved_metrics),
            'regressed_metrics': list(self.regressed_metrics),
            'unchanged_metrics': list(self.unchanged_metrics),
            'notes': list(self.notes),
        }


class SelfDevelopmentEvaluator:
    """Compare objective before/after evidence and fail closed when evidence is missing."""

    @staticmethod
    def _value(snapshot: dict, name: str):
        metric = (snapshot.get('metrics') or {}).get(name)
        if isinstance(metric, (int, float)):
            return float(metric)
        if isinstance(metric, dict):
            value = metric.get('value')
            return float(value) if isinstance(value, (int, float)) else None
        return None

    def compare(self, before: dict, after: dict, *, tests_passed: bool, policy_passed: bool) -> ImprovementEvaluation:
        improved: list[str] = []
        regressed: list[str] = []
        unchanged: list[str] = []
        shared = sorted(set((before.get('metrics') or {})) & set((after.get('metrics') or {})))
        comparable = 0
        for name in shared:
            old = self._value(before, name)
            new = self._value(after, name)
            if old is None or new is None:
                continue
            comparable += 1
            delta = new - old
            if abs(delta) < 1e-9:
                unchanged.append(name)
                continue
            improvement = delta < 0 if name in LOWER_IS_BETTER else delta > 0
            (improved if improvement else regressed).append(name)

        notes = [f'tests_passed={tests_passed}', f'policy_passed={policy_passed}']
        if comparable == 0:
            notes.append('No comparable measured before/after metrics were available; improvement is not proven.')
        if regressed:
            notes.append('Measured regression detected; production activation must remain blocked.')
        if comparable and not improved:
            notes.append('No measured target improvement was demonstrated.')

        passed = bool(tests_passed and policy_passed and comparable > 0 and improved and not regressed)
        return ImprovementEvaluation(
            passed=passed,
            improved_metrics=tuple(improved),
            regressed_metrics=tuple(regressed),
            unchanged_metrics=tuple(unchanged),
            notes=tuple(notes),
        )
