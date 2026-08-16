from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re


_TOKEN_RE = re.compile(r'[\w-]{2,}', flags=re.UNICODE)


def _tokens(text: str) -> set[str]:
    return {item.lower() for item in _TOKEN_RE.findall(str(text))}


@dataclass(frozen=True)
class UITarget:
    name: str
    control_type: str
    window_title: str
    automation_id: str = ''
    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0
    enabled: bool = True
    visible: bool = True
    backend_ref: object | None = None

    @property
    def center(self) -> tuple[int, int]:
        return ((self.left + self.right) // 2, (self.top + self.bottom) // 2)

    def safe_dict(self) -> dict:
        return {
            'name': self.name,
            'control_type': self.control_type,
            'window_title': self.window_title,
            'automation_id': self.automation_id,
            'bounds': [self.left, self.top, self.right, self.bottom],
            'enabled': self.enabled,
            'visible': self.visible,
        }


@dataclass(frozen=True)
class TargetMatch:
    target: UITarget | None
    confidence: float
    reason: str
    alternatives: tuple[dict, ...] = ()

    @property
    def resolved(self) -> bool:
        return self.target is not None


def target_score(query: str, target: UITarget, window_hint: str = '') -> float:
    query_norm = ' '.join(str(query).lower().split())
    name_norm = ' '.join(target.name.lower().split())
    if not query_norm or not name_norm:
        return 0.0

    exact = 1.0 if query_norm == name_norm else 0.0
    substring = 1.0 if query_norm in name_norm or name_norm in query_norm else 0.0
    ratio = SequenceMatcher(None, query_norm, name_norm).ratio()
    q_tokens = _tokens(query_norm)
    n_tokens = _tokens(name_norm)
    overlap = len(q_tokens & n_tokens) / max(1, len(q_tokens | n_tokens))
    automation = SequenceMatcher(None, query_norm, target.automation_id.lower()).ratio() if target.automation_id else 0.0

    score = 0.42 * exact + 0.20 * substring + 0.20 * ratio + 0.14 * overlap + 0.04 * automation
    if not target.enabled or not target.visible:
        score *= 0.65

    if window_hint:
        hint = ' '.join(window_hint.lower().split())
        title = ' '.join(target.window_title.lower().split())
        window_score = SequenceMatcher(None, hint, title).ratio()
        if hint in title or title in hint:
            window_score = max(window_score, 0.9)
        score = 0.82 * score + 0.18 * window_score

    return max(0.0, min(1.0, score))


def rank_targets(query: str, targets: list[UITarget], *, window_hint: str = '', limit: int = 8) -> list[tuple[float, UITarget]]:
    ranked = [(target_score(query, target, window_hint), target) for target in targets]
    ranked = [item for item in ranked if item[0] > 0]
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[: max(1, min(int(limit), 20))]


def choose_target(
    query: str,
    targets: list[UITarget],
    *,
    window_hint: str = '',
    threshold: float = 0.82,
    ambiguity_margin: float = 0.08,
) -> TargetMatch:
    ranked = rank_targets(query, targets, window_hint=window_hint, limit=6)
    alternatives = tuple(
        {'confidence': round(score, 4), **target.safe_dict()}
        for score, target in ranked[:5]
    )
    if not ranked:
        return TargetMatch(None, 0.0, 'No visible UI target matched the requested label.', alternatives)

    best_score, best = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0.0
    if best_score < threshold:
        return TargetMatch(
            None,
            best_score,
            f'Best visible target confidence {best_score:.2f} is below threshold {threshold:.2f}.',
            alternatives,
        )
    if second_score and best_score - second_score < ambiguity_margin:
        return TargetMatch(
            None,
            best_score,
            f'Top UI matches are ambiguous ({best_score:.2f} vs {second_score:.2f}); refusing to guess.',
            alternatives,
        )
    return TargetMatch(best, best_score, 'Target resolved confidently.', alternatives)
