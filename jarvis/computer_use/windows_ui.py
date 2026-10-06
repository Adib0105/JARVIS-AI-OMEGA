from __future__ import annotations

import os
import re
from contextlib import contextmanager
from dataclasses import dataclass

from .targets import UITarget


@dataclass(frozen=True)
class BackendStatus:
    available: bool
    backend: str
    detail: str


class WindowsUIBackend:
    """Optional Windows UI Automation adapter.

    V7 keeps PyAutoGUI as a coordinate fallback. Semantic targeting uses pywinauto/UIA
    when installed. If unavailable, the agent reports that instead of guessing.
    """

    def __init__(self) -> None:
        self._desktop = None
        self._error = ''
        if os.name != 'nt':
            self._error = 'Windows UI Automation is only available on Windows.'
            return
        try:
            from pywinauto import Desktop
            self._desktop = Desktop(backend='uia')
        except Exception as exc:
            self._error = f'{type(exc).__name__}: {exc}'

    def status(self) -> BackendStatus:
        return BackendStatus(
            available=self._desktop is not None,
            backend='pywinauto-uia',
            detail='ready' if self._desktop is not None else self._error or 'unavailable',
        )

    @contextmanager
    def automation_session(self):
        if os.name != 'nt':
            raise RuntimeError('Semantic desktop actions require Windows UI Automation.')
        import comtypes
        comtypes.CoInitializeEx(0)
        previous = self._desktop
        try:
            from pywinauto import Desktop
            self._desktop = Desktop(backend='uia')
            yield
        finally:
            self._desktop = previous
            comtypes.CoUninitialize()

    @staticmethod
    def protected_field(wrapper, name='', automation_id=''):
        try:
            password = wrapper.element_info.element.CurrentIsPassword
        except Exception:
            return None  # Unknown accessibility state cannot authorize an action.
        if bool(password):
            return True
        markers = r'password|passwd|passcode|secret|token|api.?key|credential|credit.?card|card.?number|cvv|cvc|otp|one.?time|recovery.?code|seed.?phrase'
        return bool(re.search(markers, name + ' ' + automation_id, re.I))

    def describe(self, wrapper, window):
        import psutil
        info = wrapper.element_info
        pid = int(info.process_id)
        process = psutil.Process(pid)
        automation_id = self._safe_element(wrapper, 'automation_id')
        protected = self.protected_field(wrapper)
        name = '[PROTECTED FIELD]' if protected is not False else self._safe_text(wrapper)
        protected = self.protected_field(wrapper, name, automation_id)
        if protected is not False:
            name = '[PROTECTED FIELD]'
        left, top, right, bottom = self._safe_rect(wrapper)
        return UITarget(name=name or automation_id, control_type=str(info.control_type),
                        window_title=self._safe_text(window), automation_id=automation_id,
                        left=left, top=top, right=right, bottom=bottom,
                        visible=bool(wrapper.is_visible()), enabled=bool(wrapper.is_enabled()),
                        backend_ref=wrapper, process_id=pid, process_started=process.create_time(),
                        application=process.exe(), window_handle=int(window.handle),
                        runtime_id=tuple(info.runtime_id), protected=protected)

    def refresh(self, target):
        wrapper = target.backend_ref
        if wrapper is None:
            raise RuntimeError('Missing live UI Automation reference.')
        return self.describe(wrapper, wrapper.top_level_parent())

    def invoke(self, target):
        current = self.refresh(target)
        if current.identity != target.identity or current.protected is not False or not current.visible or not current.enabled:
            raise RuntimeError('Target changed or is protected; invocation was blocked.')
        # InvokePattern addresses this exact element; no coordinate/global click.
        target.backend_ref.iface_invoke.Invoke()

    def replace_text(self, target, text):
        current = self.refresh(target)
        if current.identity != target.identity or current.protected is not False or not current.visible or not current.enabled:
            raise RuntimeError('Target changed or is protected; input was blocked.')
        value = target.backend_ref.iface_value
        if bool(value.CurrentIsReadOnly):
            raise RuntimeError('Target field is read-only.')
        # ValuePattern is literal Unicode replacement, never interpreted keys.
        value.SetValue(text)

    @staticmethod
    def _safe_text(wrapper) -> str:
        try:
            return str(wrapper.window_text() or '').strip()
        except Exception:
            return ''

    @staticmethod
    def _safe_element(wrapper, attr: str) -> str:
        try:
            info = getattr(wrapper, 'element_info', None)
            return str(getattr(info, attr, '') or '').strip()
        except Exception:
            return ''

    @staticmethod
    def _safe_rect(wrapper) -> tuple[int, int, int, int]:
        try:
            rect = wrapper.rectangle()
            return int(rect.left), int(rect.top), int(rect.right), int(rect.bottom)
        except Exception:
            return 0, 0, 0, 0

    def enumerate_targets(self, *, window_hint: str = '', max_windows: int = 12, max_controls: int = 600) -> list[UITarget]:
        if self._desktop is None:
            return []
        output: list[UITarget] = []
        try:
            windows = list(self._desktop.windows(visible_only=True))[: max(1, int(max_windows))]
        except Exception:
            return []

        hint = window_hint.lower().strip()
        for window in windows:
            title = self._safe_text(window)
            if hint and hint not in title.lower():
                # Keep fuzzy title candidates but skip clearly unrelated windows only
                # when an exact substring window hint was requested.
                continue
            try:
                descendants = [window] + list(window.descendants())
            except Exception:
                descendants = [window]
            for wrapper in descendants:
                if len(output) >= max_controls:
                    return output
                try:
                    output.append(self.describe(wrapper, window))
                except Exception:
                    # Missing identity, stale UIA or inaccessible processes are
                    # not actionable; do not synthesize affirmative defaults.
                    continue
        return output

    @staticmethod
    def click(target: UITarget) -> dict:
        wrapper = target.backend_ref
        if wrapper is None:
            raise RuntimeError('Resolved target does not contain a UI Automation reference.')
        try:
            wrapper.click_input()
        except Exception as exc:
            raise RuntimeError(f'UI click failed: {type(exc).__name__}: {exc}') from exc
        return WindowsUIBackend.observe(target)

    @staticmethod
    def focus(target: UITarget) -> dict:
        wrapper = target.backend_ref
        if wrapper is None:
            raise RuntimeError('Resolved target does not contain a UI Automation reference.')
        try:
            wrapper.set_focus()
        except Exception as exc:
            raise RuntimeError(f'UI focus failed: {type(exc).__name__}: {exc}') from exc
        return WindowsUIBackend.observe(target)

    @staticmethod
    def observe(target: UITarget) -> dict:
        wrapper = target.backend_ref
        evidence = target.safe_dict()
        if wrapper is None:
            return evidence | {'observed': False}
        try:
            evidence['exists'] = int(wrapper.element_info.element.CurrentProcessId) == target.process_id
        except Exception:
            evidence['exists'] = False
        try:
            evidence['focused'] = bool(wrapper.has_keyboard_focus())
        except Exception:
            evidence['focused'] = None
        try:
            evidence['selected'] = bool(wrapper.is_selected())
        except Exception:
            evidence['selected'] = None
        try:
            protected = WindowsUIBackend.protected_field(wrapper, target.name, target.automation_id)
            evidence['value'] = wrapper.get_value() if protected is False else None
        except Exception:
            evidence['value'] = None
        evidence['observed'] = True
        return evidence
