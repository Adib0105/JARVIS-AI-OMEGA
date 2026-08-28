from __future__ import annotations

import time

from .display_context import get_display_context
from .targets import TargetMatch, choose_target
from .visual_fallback import VisualTargetBackend
from .windows_ui import WindowsUIBackend


class ComputerActionEngine:
    def __init__(
        self,
        backend: WindowsUIBackend | None = None,
        confidence_threshold: float = 0.82,
        *,
        visual_backend: VisualTargetBackend | None = None,
        visual_threshold: float = 0.88,
    ) -> None:
        self.backend = backend or WindowsUIBackend()
        self.visual_backend = visual_backend or VisualTargetBackend()
        self.confidence_threshold = max(0.5, min(0.99, float(confidence_threshold)))
        self.visual_threshold = max(self.confidence_threshold, min(0.99, float(visual_threshold)))

    def status(self) -> dict:
        status = self.backend.status()
        visual = self.visual_backend.status()
        return {
            'available': bool(status.available or visual.available),
            'backend': status.backend,
            'detail': status.detail,
            'confidence_threshold': self.confidence_threshold,
            'visual_fallback': visual.as_dict(),
            'visual_threshold': self.visual_threshold,
            'display': get_display_context().as_dict(),
        }

    @staticmethod
    def _is_ambiguous(match: TargetMatch) -> bool:
        return 'ambiguous' in str(match.reason).lower()

    @staticmethod
    def _is_visual(match: TargetMatch) -> bool:
        return bool(match.target and match.target.control_type == 'OCRText')

    def resolve(self, target: str, *, window_hint: str = '') -> TargetMatch:
        """Resolve UIA first and use OCR only when UIA cannot identify a target.

        An ambiguous UIA result is never bypassed by OCR because doing so could turn
        uncertainty into an unintended click. OCR itself has a stricter threshold.
        """
        targets = self.backend.enumerate_targets(window_hint=window_hint)
        semantic = choose_target(
            target,
            targets,
            window_hint=window_hint,
            threshold=self.confidence_threshold,
        )
        if semantic.resolved or self._is_ambiguous(semantic):
            return semantic

        visual = self.visual_backend.resolve(target, threshold=self.visual_threshold)
        if visual.resolved:
            return visual
        alternatives = tuple(list(semantic.alternatives) + list(visual.alternatives))[:8]
        confidence = max(float(semantic.confidence), float(visual.confidence))
        return TargetMatch(
            None,
            confidence,
            f'UIA: {semantic.reason} OCR: {visual.reason}',
            alternatives,
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

    def _prepare_uia_target(self, query: str, match: TargetMatch, *, window_hint: str) -> tuple[TargetMatch, dict]:
        if not match.resolved or self._is_visual(match):
            return match, {'supported': False, 'ready': bool(match.resolved), 'reason': 'UIA focus recovery not applicable.'}
        ensure_ready = getattr(self.backend, 'ensure_ready', None)
        if not callable(ensure_ready):
            return match, {'supported': False, 'ready': True, 'reason': 'Backend does not expose focus recovery.'}

        assert match.target is not None
        evidence = dict(ensure_ready(match.target))
        evidence['supported'] = True
        if evidence.get('ready'):
            return match, evidence

        # UI trees can become stale between resolution and action. Refresh UIA once,
        # but do not silently switch to visual clicking during recovery.
        targets = self.backend.enumerate_targets(window_hint=window_hint)
        refreshed = choose_target(
            query,
            targets,
            window_hint=window_hint,
            threshold=self.confidence_threshold,
        )
        evidence['refresh_attempted'] = True
        if not refreshed.resolved:
            evidence['refresh_reason'] = refreshed.reason
            return TargetMatch(None, refreshed.confidence, f'Target became stale before action. {refreshed.reason}', refreshed.alternatives), evidence

        assert refreshed.target is not None
        refreshed_evidence = dict(ensure_ready(refreshed.target))
        evidence['refresh'] = refreshed_evidence
        if not refreshed_evidence.get('ready'):
            return TargetMatch(None, refreshed.confidence, 'Target was re-resolved but its window could not be made ready safely.', refreshed.alternatives), evidence
        return refreshed, evidence

    def _observe_until(self, target, predicate, *, timeout: float = 0.8, interval: float = 0.08) -> dict:
        deadline = time.monotonic() + max(0.0, float(timeout))
        observed = self.backend.observe(target)
        while time.monotonic() < deadline and not predicate(observed):
            if observed.get('exists') is False:
                break
            time.sleep(max(0.01, min(float(interval), 0.2)))
            observed = self.backend.observe(target)
        return observed

    def _visual_click(self, match: TargetMatch) -> dict:
        assert match.target is not None
        try:
            import pyautogui
            x, y = match.target.center
            pyautogui.click(x=x, y=y, button='left')
        except Exception as exc:
            return {
                'ok': False,
                'error': f'OCR-target click failed: {type(exc).__name__}: {exc}',
                'target': match.target.safe_dict(),
                'confidence': round(match.confidence, 4),
                'resolution_backend': 'local-ocr',
            }
        return {
            'ok': True,
            'target': match.target.safe_dict(),
            'confidence': round(match.confidence, 4),
            'resolution_backend': 'local-ocr',
            'action': 'click',
            'verification': {
                'status': 'PARTIAL',
                'verified': False,
                'evidence': {
                    'ocr_label_resolved': True,
                    'clicked_center': list(match.target.center),
                    'reason': 'OCR target location was confident, but the higher-level UI outcome was not independently observed.',
                },
            },
        }

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
        if self._is_visual(match):
            return self._visual_click(match)

        match, readiness = self._prepare_uia_target(target, match, window_hint=window_hint)
        if not match.resolved:
            return {
                'ok': False,
                'error': 'The UI target changed or lost a safely recoverable window before the click.',
                'confidence': round(match.confidence, 4),
                'reason': match.reason,
                'alternatives': list(match.alternatives),
                'focus_recovery': readiness,
            }

        assert match.target is not None
        before = self.backend.observe(match.target)
        try:
            after = self.backend.click(match.target)
        except Exception as exc:
            return {
                'ok': False,
                'error': f'UI click failed: {type(exc).__name__}: {exc}',
                'target': match.target.safe_dict(),
                'confidence': round(match.confidence, 4),
                'resolution_backend': 'windows-uia',
                'focus_recovery': readiness,
            }

        # Focus/selection that already existed before the click is not evidence that the
        # click achieved anything. Wait for a post-action state transition (or target
        # disappearance/value change) instead of promoting an unchanged precondition.
        observed = self._observe_until(
            match.target,
            lambda row: bool(
                (before.get('focused') is not True and row.get('focused') is True)
                or (before.get('selected') is not True and row.get('selected') is True)
                or row.get('exists') is False
                or row.get('value') != before.get('value')
            ),
        )
        verification = self._verify_click(before, after, observed)
        return {
            'ok': True,
            'target': match.target.safe_dict(),
            'confidence': round(match.confidence, 4),
            'resolution_backend': 'windows-uia',
            'action': 'click',
            'focus_recovery': readiness,
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
        visual = self._is_visual(match)
        readiness = {'supported': False, 'ready': True, 'reason': 'Visual target uses click-to-focus.'}
        if not visual:
            match, readiness = self._prepare_uia_target(target, match, window_hint=window_hint)
            if not match.resolved:
                return {
                    'ok': False,
                    'error': 'The UI target changed or lost a safely recoverable window before typing.',
                    'confidence': round(match.confidence, 4),
                    'reason': match.reason,
                    'alternatives': list(match.alternatives),
                    'focus_recovery': readiness,
                }
            assert match.target is not None

        try:
            import pyautogui
            if visual:
                x, y = match.target.center
                pyautogui.click(x=x, y=y, button='left')
            else:
                self.backend.focus(match.target)
            pyautogui.write(str(text), interval=max(0.0, min(float(interval), 0.2)))
        except Exception as exc:
            return {
                'ok': False,
                'error': f'Typing failed: {type(exc).__name__}: {exc}',
                'target': match.target.safe_dict(),
                'confidence': round(match.confidence, 4),
                'resolution_backend': 'local-ocr' if visual else 'windows-uia',
                'focus_recovery': readiness,
            }

        if visual:
            return {
                'ok': True,
                'target': match.target.safe_dict(),
                'confidence': round(match.confidence, 4),
                'resolution_backend': 'local-ocr',
                'action': 'type',
                'verification': {
                    'status': 'PARTIAL',
                    'verified': False,
                    'evidence': {
                        'ocr_label_resolved': True,
                        'typed_after_click': True,
                        'value_readback': 'unavailable',
                    },
                },
            }

        observed = self.backend.observe(match.target)
        value = observed.get('value')
        if isinstance(value, str):
            observed = self._observe_until(match.target, lambda row: isinstance(row.get('value'), str) and str(text) in row.get('value', ''))
            value = observed.get('value')
            verified = isinstance(value, str) and (value.endswith(str(text)) or str(text) in value)
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
            'resolution_backend': 'windows-uia',
            'action': 'type',
            'focus_recovery': readiness,
            'verification': verification,
        }

    @staticmethod
    def _verify_click(before: dict, after: dict, observed: dict) -> dict:
        focused_transition = before.get('focused') is not True and (
            after.get('focused') is True or observed.get('focused') is True
        )
        selected_transition = before.get('selected') is not True and (
            after.get('selected') is True or observed.get('selected') is True
        )
        if focused_transition or selected_transition:
            return {
                'status': 'VERIFIED',
                'verified': True,
                'evidence': {
                    'focus_transition': focused_transition,
                    'selection_transition': selected_transition,
                    'exists': observed.get('exists'),
                },
            }
        if before.get('value') != observed.get('value') and (before.get('value') is not None or observed.get('value') is not None):
            return {
                'status': 'VERIFIED',
                'verified': True,
                'evidence': {'value_changed': True, 'exists': observed.get('exists')},
            }
        if observed.get('exists') is False:
            return {
                'status': 'PARTIAL',
                'verified': False,
                'evidence': {'target_disappeared_after_click': True},
            }
        return {
            'status': 'PARTIAL',
            'verified': False,
            'evidence': {
                'focused_before': before.get('focused'),
                'focused_after': observed.get('focused'),
                'selected_before': before.get('selected'),
                'selected_after': observed.get('selected'),
                'exists': observed.get('exists'),
                'after_action_observation': bool(observed.get('observed')),
                'reason': 'No post-click UI state transition was independently observed.',
            },
        }
