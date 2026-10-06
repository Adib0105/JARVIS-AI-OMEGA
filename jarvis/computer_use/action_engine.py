from __future__ import annotations

import time
import threading
import uuid
from contextlib import nullcontext
from dataclasses import replace

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
        self._observations = {}
        self._action_lock = threading.Lock()
        self._clock = time.monotonic
        self.observation_ttl = 30.0

    def _session(self):
        return self.backend.automation_session() if hasattr(self.backend, 'automation_session') else nullcontext()

    def inspect_target(self, target: str, *, window_hint: str):
        """Produce a bounded, single-use identity snapshot before approval."""
        if not target.strip() or not window_hint.strip():
            return {'ok': False, 'error': 'An explicit target and application window hint are required.'}
        if not self._action_lock.acquire(blocking=False):
            return {'ok': False, 'error': 'A desktop operation is already active.'}
        try:
            with self._session():
                match = self.resolve(target, window_hint=window_hint)
                if not match.resolved:
                    return {'ok': False, 'error': match.reason, 'alternatives': list(match.alternatives)}
                item = match.target
                if self._is_visual(match):
                    return {'ok': True, 'actionable': False, 'target': item.safe_dict(),
                            'reason': 'OCR location has no verified application/field identity. Manual action is required.'}
                if not item.has_identity or item.protected is not False or not item.enabled or not item.visible:
                    return {'ok': False, 'error': 'Target identity or non-sensitive accessibility state could not be confirmed.'}
                now = self._clock()
                self._observations = {k: v for k, v in self._observations.items() if v[1] > now}
                if len(self._observations) >= 32:
                    self._observations.pop(next(iter(self._observations)))
                observation = uuid.uuid4().hex
                self._observations[observation] = (replace(item, backend_ref=None), now + self.observation_ttl)
                return {'ok': True, 'actionable': True, 'observation_id': observation,
                        'expires_in_seconds': self.observation_ttl, 'target': item.safe_dict(),
                        'confidence': match.confidence, 'resolution_backend': 'windows-uia'}
        finally:
            self._action_lock.release()

    def act_observed(self, action, observation_id, *, app, window_title, target, text=''):
        """Act once on a re-observed element; never retarget or retry an effect."""
        if not self._action_lock.acquire(blocking=False):
            return {'ok': False, 'error': 'A desktop operation is already active.'}
        try:
            stored = self._observations.pop(observation_id, None)
            if stored is None or stored[1] <= self._clock():
                return {'ok': False, 'error': 'Observation expired, was consumed or belongs to another session. Inspect again.'}
            expected, _expires = stored
            if (app.casefold(), window_title, target) != (expected.application.casefold(), expected.window_title, expected.name):
                return {'ok': False, 'error': 'Approved application/window/target does not match the observation.'}
            if action not in ('click', 'type') or len(text) > 2000:
                return {'ok': False, 'error': 'Unsupported action or input exceeds 2,000 characters.'}
            if action == 'type':
                from ..security.secrets import ensure_safe_for_persistent_memory
                ensure_safe_for_persistent_memory(text)
            with self._session():
                targets = self.backend.enumerate_targets(window_hint=window_title)
                matches = [item for item in targets if item.identity == expected.identity]
                if len(matches) != 1:
                    return {'ok': False, 'error': 'Stale or ambiguous application/window/element identity. No action was attempted.'}
                item = matches[0]
                if (item.name != expected.name or item.window_title != expected.window_title
                        or item.automation_id != expected.automation_id or item.control_type != expected.control_type
                        or (item.left, item.top, item.right, item.bottom) != (expected.left, expected.top, expected.right, expected.bottom)
                        or not item.visible or not item.enabled or item.protected is not False):
                    return {'ok': False, 'error': 'Target changed, moved, became inaccessible or is protected. Inspect again.'}
                before = self.backend.observe(item)
                if before.get('exists') is not True:
                    return {'ok': False, 'error': 'Target existence could not be confirmed.'}
                if self._clock() >= _expires:
                    return {'ok': False, 'error': 'Observation expired during revalidation. Inspect again.'}
                if action == 'type':
                    if item.control_type != 'Edit' or not isinstance(before.get('value'), str):
                        return {'ok': False, 'error': 'Only non-sensitive edit fields with value readback are supported.'}
                    if before['value'] == text:
                        return {'ok': False, 'error': 'Field already contains that value; no new input was performed.'}
                    self.backend.replace_text(item, text)
                else:
                    self.backend.invoke(item)
                observed = self.backend.observe(item)
                current = self.backend.refresh(item)
                same = current.identity == item.identity and current.protected is False
                verified = (action == 'type' and same and observed.get('exists') is True
                            and observed.get('value') == text and observed.get('value') != before.get('value'))
                return {'ok': same and (action == 'click' or verified), 'action': action,
                        'resolution_backend': 'windows-uia', 'target': expected.safe_dict(),
                        'verification': {'verified': verified, 'status': 'VERIFIED' if verified else 'UNKNOWN',
                                         'evidence': {'identity_preserved': same, 'value_changed': verified,
                                                      'scope': 'field_value_replacement' if verified else 'invocation_only'}}}
        except Exception as exc:
            from ..security.redaction import redact_text
            return {'ok': False, 'error': redact_text(f'{type(exc).__name__}: {exc}'),
                    'verification': {'verified': False, 'status': 'UNKNOWN',
                                     'evidence': 'Action outcome is uncertain; do not retry automatically.'}}
        finally:
            self._action_lock.release()

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
                'status': 'UNKNOWN',
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
            'resolution_backend': 'windows-uia',
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
        visual = self._is_visual(match)
        before = {} if visual else self.backend.observe(match.target)
        if before.get('exists') is False:
            return {'ok': False, 'error': 'Target no longer exists; no text was entered.'}
        try:
            import pyautogui
            if visual:
                x, y = match.target.center
                pyautogui.click(x=x, y=y, button='left')
            else:
                focus = self.backend.focus(match.target)
                if focus.get('focused') is not True or focus.get('exists') is not True:
                    return {'ok': False, 'error': 'Target focus could not be confirmed; no text was entered.'}
            pyautogui.write(str(text), interval=max(0.0, min(float(interval), 0.2)))
        except Exception as exc:
            return {
                'ok': False,
                'error': f'Typing failed: {type(exc).__name__}: {exc}',
                'target': match.target.safe_dict(),
                'confidence': round(match.confidence, 4),
                'resolution_backend': 'local-ocr' if visual else 'windows-uia',
            }

        if visual:
            return {
                'ok': True,
                'target': match.target.safe_dict(),
                'confidence': round(match.confidence, 4),
                'resolution_backend': 'local-ocr',
                'action': 'type',
                'verification': {
                    'status': 'UNKNOWN',
                    'verified': False,
                    'evidence': {
                        'ocr_label_resolved': True,
                        'typed_after_click': True,
                        'value_readback': 'unavailable',
                    },
                },
            }

        time.sleep(0.08)
        observed = self.backend.observe(match.target)
        value = observed.get('value')
        previous = before.get('value')
        requested = str(text)
        if isinstance(value, str) and isinstance(previous, str):
            # Existing text is not proof that write() did anything. We can only
            # attest an observed value change, not a submitted form/workflow.
            verified = (bool(requested) and observed.get('focused') is True
                        and observed.get('exists') is True
                        and value != previous and value.count(requested) > previous.count(requested))
            verification = {
                'status': 'VERIFIED' if verified else 'FAILED',
                'verified': verified,
                'evidence': {'focused': observed.get('focused'), 'value_changed': value != previous,
                             'additional_text_observed': verified, 'scope': 'field_value_change'},
            }
        else:
            verification = {
                'status': 'UNKNOWN',
                'verified': False,
                'evidence': {'focused': observed.get('focused'), 'value_readback': 'unavailable'},
            }
        return {
            'ok': verification['status'] != 'FAILED',
            'target': match.target.safe_dict(),
            'confidence': round(match.confidence, 4),
            'resolution_backend': 'windows-uia',
            'action': 'type',
            'verification': verification,
        }

    @staticmethod
    def _verify_click(before: dict, after: dict, observed: dict) -> dict:
        # Focus/selection is acknowledgement, not proof of the requested outcome.
        if observed.get('exists') is False:
            return {
                'status': 'UNKNOWN',
                'verified': False,
                'evidence': {'target_disappeared_after_click': True},
            }
        return {
            'status': 'UNKNOWN',
            'verified': False,
            'evidence': {
                'focused': observed.get('focused'),
                'selected': observed.get('selected'),
                'exists': observed.get('exists'),
            },
        }
