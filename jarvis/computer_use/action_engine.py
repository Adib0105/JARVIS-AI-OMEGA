from __future__ import annotations

import time

from .targets import TargetMatch, choose_target
from .windows_ui import WindowsUIBackend


class ComputerActionEngine:
    def __init__(self, backend: WindowsUIBackend | None = None, confidence_threshold: float = 0.82) -> None:
        self.backend = backend or WindowsUIBackend()
        self.confidence_threshold = max(0.5, min(0.99, float(confidence_threshold)))

    def status(self) -> dict:
        status = self.backend.status()
        return {
            'available': status.available,
            'backend': status.backend,
            'detail': status.detail,
            'confidence_threshold': self.confidence_threshold,
        }

    def resolve(self, target: str, *, window_hint: str = '') -> TargetMatch:
        targets = self.backend.enumerate_targets(window_hint=window_hint)
        return choose_target(
            target,
            targets,
            window_hint=window_hint,
            threshold=self.confidence_threshold,
        )

    def list_targets(self, query: str = '', *, window_hint: str = '', limit: int = 20) -> dict:
        targets = self.backend.enumerate_targets(window_hint=window_hint)
        if query.strip():
            from .targets import rank_targets
            ranked = rank_targets(query, targets, window_hint=window_hint, limit=limit)
            items = [{'confidence': round(score, 4), **target.safe_dict()} for score, target in ranked]
        else:
            items = [target.safe_dict() for target in targets[: max(1, min(int(limit), 50))]]
        return {'backend': self.status(), 'count': len(items), 'targets': items}

    def semantic_click(self, target: str, *, window_hint: str = '') -> dict:
        match = self.resolve(target, window_hint=window_hint)
        if not match.resolved:
            return {
                'ok': False,
                'error': "I can't confidently identify the target. I will not guess.",
                'confidence': round(match.confidence, 4),
                'reason': match.reason,
                'alternatives': list(match.alternatives),
            }
        assert match.target is not None
        before = self.backend.observe(match.target)
        after = self.backend.click(match.target)
        time.sleep(0.08)
        observed = self.backend.observe(match.target)
        verification = self._verify_click(before, after, observed)
        return {
            'ok': True,
            'target': match.target.safe_dict(),
            'confidence': round(match.confidence, 4),
            'action': 'click',
            'verification': verification,
        }

    def semantic_type(self, target: str, text: str, *, window_hint: str = '', interval: float = 0.01) -> dict:
        match = self.resolve(target, window_hint=window_hint)
        if not match.resolved:
            return {
                'ok': False,
                'error': "I can't confidently identify the target. I will not guess.",
                'confidence': round(match.confidence, 4),
                'reason': match.reason,
                'alternatives': list(match.alternatives),
            }
        assert match.target is not None
        self.backend.focus(match.target)
        try:
            import pyautogui
            pyautogui.write(str(text), interval=max(0.0, min(float(interval), 0.2)))
        except Exception as exc:
            return {
                'ok': False,
                'error': f'Typing failed: {type(exc).__name__}: {exc}',
                'target': match.target.safe_dict(),
                'confidence': round(match.confidence, 4),
            }
        time.sleep(0.08)
        observed = self.backend.observe(match.target)
        value = observed.get('value')
        if isinstance(value, str):
            verified = value.endswith(str(text)) or str(text) in value
            verification = {
                'status': 'VERIFIED' if verified else 'FAILED',
                'verified': verified,
                'evidence': {'focused': observed.get('focused'), 'value_contains_text': verified},
            }
        else:
            verification = {
                'status': 'PARTIAL',
                'verified': False,
                'evidence': {'focused': observed.get('focused'), 'value_readback': 'unavailable'},
            }
        return {
            'ok': verification['status'] != 'FAILED',
            'target': match.target.safe_dict(),
            'confidence': round(match.confidence, 4),
            'action': 'type',
            'verification': verification,
        }

    @staticmethod
    def _verify_click(before: dict, after: dict, observed: dict) -> dict:
        if observed.get('focused') is True or observed.get('selected') is True:
            return {
                'status': 'VERIFIED',
                'verified': True,
                'evidence': {
                    'focused': observed.get('focused'),
                    'selected': observed.get('selected'),
                    'exists': observed.get('exists'),
                },
            }
        if observed.get('exists') is False:
            # A button/menu item disappearing can be a real post-click state change,
            # but it is not sufficient to infer the intended higher-level outcome.
            return {
                'status': 'PARTIAL',
                'verified': False,
                'evidence': {'target_disappeared_after_click': True},
            }
        return {
            'status': 'PARTIAL',
            'verified': False,
            'evidence': {
                'focused': observed.get('focused'),
                'selected': observed.get('selected'),
                'exists': observed.get('exists'),
            },
        }
