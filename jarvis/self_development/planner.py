from __future__ import annotations

from dataclasses import dataclass

from .analyzer import ImprovementAnalysis


@dataclass(frozen=True)
class ImprovementPlan:
    steps: tuple[str, ...]
    required_tests: tuple[str, ...]
    stop_conditions: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            'steps': list(self.steps),
            'required_tests': list(self.required_tests),
            'stop_conditions': list(self.stop_conditions),
        }


class SelfDevelopmentPlanner:
    """Creates a conservative engineering plan from observed evidence."""

    def plan(self, analysis: ImprovementAnalysis) -> ImprovementPlan:
        paths = ', '.join(analysis.existing_paths[:6]) or 'relevant subsystem files'
        steps = (
            f'Inspect the smallest relevant extension points: {paths}.',
            'Create or strengthen a deterministic regression test that reproduces the capability gap.',
            'Implement the minimum change in the isolated self-improvement worktree.',
            'Run compileall and the full unittest regression suite.',
            'Inspect Git diff and enforce immutable-core/file/line policies.',
            'Compare measurable evaluation evidence when the affected metric is available.',
            'Produce a concise diff/test/security summary and wait for production approval.',
        )
        required_tests = tuple(path for path in analysis.existing_paths if path.startswith('tests/')) or ('full unittest discovery',)
        stop_conditions = (
            'Security-core or rollback policy modification is required.',
            'Configured file/line/build limits would be exceeded.',
            'Regression tests remain red after the bounded repair limit.',
            'The sandbox cannot be created or verified.',
            'Production activation lacks explicit approval.',
        )
        return ImprovementPlan(steps, required_tests, stop_conditions)
