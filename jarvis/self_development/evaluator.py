from __future__ import annotations

from dataclasses import dataclass


LOWER_IS_BETTER = {'tool_error_rate', 'average_tool_latency_ms', 'safety_violation_rate'}


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
    """Compare measured before/after snapshots; never uses subjective model claims as proof."""

    @staticmethod
    def _value(snapshot: dict, name: str):
        metric = (snapshot.get('metrics') or {}).get(name) or {}
        value = metric.get('value')
        return float(value) if isinstance(value, (int, float)) else None

    def compare(self, before: dict, after: dict, *, tests_passed: bool, policy_passed: bool) -> ImprovementEvaluation:
        improved: list[str] = []
        regressed: list[str] = []
        unchanged: list[str] = []
        shared = sorted(set((before.get('metrics') or {})) & set((after.get('metrics') or {})))
        for name in shared:
            old = self._value(before, name)
            new = self._value(after, name)
            if old is None or new is None:
                continue
            delta = new - old
            if abs(delta) < 1e-9:
                unchanged.append(name)
                continue
            improvement = delta < 0 if name in LOWER_IS_BETTER else delta > 0
            (improved if improvement else regressed).append(name)

        notes = [
            f'tests_passed={tests_passed}',
            f'policy_passed={policy_passed}',
        ]
        if not shared:
            notes.append('No comparable measured metrics were available; regression tests are the evidence gate.')
        if regressed:
            notes.append('Measured regression detected; production activation must remain blocked.')

        passed = bool(tests_passed and policy_passed and not regressed)
        return ImprovementEvaluation(
            passed=passed,
            improved_metrics=tuple(improved),
            regressed_metrics=tuple(regressed),
            unchanged_metrics=tuple(unchanged),
            notes=tuple(notes),
        )
