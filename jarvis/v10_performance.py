from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PerformanceMode(str, Enum):
    ECO = 'eco'
    BALANCED = 'balanced'
    PERFORMANCE = 'performance'


@dataclass(frozen=True)
class PerformanceProfile:
    mode: PerformanceMode
    max_parallel_tasks: int
    animation_fps: int
    prefer_local_fast_path: bool


PROFILES = {
    PerformanceMode.ECO: PerformanceProfile(PerformanceMode.ECO, 1, 20, True),
    PerformanceMode.BALANCED: PerformanceProfile(PerformanceMode.BALANCED, 2, 30, True),
    PerformanceMode.PERFORMANCE: PerformanceProfile(PerformanceMode.PERFORMANCE, 4, 60, False),
}


def choose_profile(mode: str = 'balanced', *, memory_gb: float | None = None) -> PerformanceProfile:
    try:
        selected = PerformanceMode(mode.strip().lower())
    except (ValueError, AttributeError):
        selected = PerformanceMode.BALANCED
    if memory_gb is not None and memory_gb < 6 and selected is PerformanceMode.PERFORMANCE:
        selected = PerformanceMode.BALANCED
    if memory_gb is not None and memory_gb < 4:
        selected = PerformanceMode.ECO
    return PROFILES[selected]
