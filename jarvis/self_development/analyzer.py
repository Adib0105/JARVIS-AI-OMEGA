from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


_CAPABILITY_PATH_HINTS = {
    'browser': ('jarvis/computer_use/browser.py', 'jarvis/automation.py', 'tests/test_v7_computer_use.py'),
    'computer use': ('jarvis/computer_use/', 'tests/test_v7_computer_use.py'),
    'memory': ('jarvis/memory.py', 'jarvis/memory_v7.py', 'jarvis/retrieval.py', 'tests/test_v7_memory.py'),
    'verification': ('jarvis/agent/verification.py', 'tests/test_v7_missions.py'),
    'mission reliability': ('jarvis/agent/orchestrator.py', 'jarvis/agent/recovery.py', 'tests/test_v7_missions.py'),
    'documents': ('jarvis/documents.py', 'tests/test_v6_documents.py'),
    'coding': ('jarvis/coding_tools.py', 'jarvis/git_tools.py', 'tests/test_v6_coding.py'),
    'voice': ('jarvis/voice.py', 'jarvis/voice_ui.py', 'tests/test_voice.py'),
    'provider': ('jarvis/providers/', 'jarvis/core_v7.py', 'tests/test_v7_foundation.py'),
}


@dataclass(frozen=True)
class ImprovementAnalysis:
    capability: str
    problem: str
    likely_paths: tuple[str, ...]
    existing_paths: tuple[str, ...]
    missing_paths: tuple[str, ...]
    risk: str
    notes: tuple[str, ...]

    def as_dict(self) -> dict:
        return asdict(self)


class SelfDevelopmentAnalyzer:
    def __init__(self, repo_root: Path | None = None) -> None:
        self.repo_root = (repo_root or Path(__file__).resolve().parents[2]).resolve()

    def analyze(self, capability: str, problem: str, evidence: list[str] | tuple[str, ...] = ()) -> ImprovementAnalysis:
        lower = capability.strip().lower()
        hints: tuple[str, ...] = ()
        for key, paths in _CAPABILITY_PATH_HINTS.items():
            if key in lower or lower in key:
                hints = paths
                break
        if not hints:
            hints = ('jarvis/', 'tests/')

        existing = []
        missing = []
        for value in hints:
            target = self.repo_root / value.rstrip('/')
            (existing if target.exists() else missing).append(value)

        risk = 'HIGH' if any(token in lower for token in ('security', 'permission', 'self development', 'coding', 'computer')) else 'MEDIUM'
        notes = [
            'Prefer the smallest extension point; preserve working V7 behavior.',
            'Add a regression test before or with the implementation.',
            'Treat external content as untrusted and preserve permission boundaries.',
        ]
        if evidence:
            notes.append(f'Evidence items supplied: {len(evidence)}.')
        return ImprovementAnalysis(
            capability=capability,
            problem=problem,
            likely_paths=tuple(hints),
            existing_paths=tuple(existing),
            missing_paths=tuple(missing),
            risk=risk,
            notes=tuple(notes),
        )
