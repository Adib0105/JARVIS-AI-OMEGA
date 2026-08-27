from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass

from .targets import UITarget


@dataclass(frozen=True)
class BackendStatus:
    available: bool
    backend: str
    detail: str


class WindowsUIBackend:
    """Windows UI Automation adapter backed by pywinauto/UIA.

    Semantic actions use UIA first and expose concrete pre/post observations. The
    backend also attempts bounded focus recovery for a resolved target instead of
    blindly sending input to whichever window currently owns focus.
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

    @staticmethod
    def _safe_window_handle(wrapper) -> int | None:
        try:
            handle = int(getattr(wrapper, 'handle'))
            return handle if handle > 0 else None
        except Exception:
            return None

    @staticmethod
    def _window_dpi(wrapper) -> int | None:
        if os.name != 'nt':
            return None
        handle = WindowsUIBackend._safe_window_handle(wrapper)
        if not handle:
            return None
        try:
            get_dpi = ctypes.windll.user32.GetDpiForWindow
            get_dpi.argtypes = [ctypes.c_void_p]
            get_dpi.restype = ctypes.c_uint
            return int(get_dpi(handle))
        except Exception:
            return None

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
                continue
            try:
                descendants = [window] + list(window.descendants())
            except Exception:
                descendants = [window]
            for wrapper in descendants:
                if len(output) >= max_controls:
                    return output
                name = self._safe_text(wrapper)
                automation_id = self._safe_element(wrapper, 'automation_id')
                control_type = self._safe_element(wrapper, 'control_type') or type(wrapper).__name__
                if not name and not automation_id:
                    continue
                left, top, right, bottom = self._safe_rect(wrapper)
                try:
                    visible = bool(wrapper.is_visible())
                except Exception:
                    visible = True
                try:
                    enabled = bool(wrapper.is_enabled())
                except Exception:
                    enabled = True
                output.append(UITarget(
                    name=name or automation_id,
                    control_type=control_type,
                    window_title=title,
                    automation_id=automation_id,
                    left=left,
                    top=top,
                    right=right,
                    bottom=bottom,
                    enabled=enabled,
                    visible=visible,
                    backend_ref=wrapper,
                ))
        return output

    @staticmethod
    def ensure_ready(target: UITarget) -> dict:
        """Re-check target state and recover its top-level window focus when possible."""
        wrapper = target.backend_ref
        if wrapper is None:
            return {'ready': False, 'reason': 'Resolved target does not contain a UI Automation reference.'}

        evidence: dict = {'ready': False, 'restored': False, 'window_focused': None}
        try:
            exists = bool(wrapper.exists(timeout=0.5))
        except Exception:
            exists = True
        try:
            visible = bool(wrapper.is_visible())
        except Exception:
            visible = target.visible
        try:
            enabled = bool(wrapper.is_enabled())
        except Exception:
            enabled = target.enabled
        evidence.update({'exists': exists, 'visible': visible, 'enabled': enabled})
        if not (exists and visible and enabled):
            evidence['reason'] = 'Resolved target is no longer available, visible, and enabled.'
            return evidence

        try:
            top = wrapper.top_level_parent()
        except Exception:
            top = wrapper
        try:
            if bool(top.is_minimized()):
                top.restore()
                evidence['restored'] = True
        except Exception:
            pass
        try:
            top.set_focus()
            evidence['window_focused'] = True
        except Exception as exc:
            evidence['window_focused'] = False
            evidence['focus_error'] = f'{type(exc).__name__}: {exc}'
            return evidence

        evidence['ready'] = True
        evidence['window_title'] = WindowsUIBackend._safe_text(top) or target.window_title
        dpi = WindowsUIBackend._window_dpi(top)
        if dpi:
            evidence['window_dpi'] = dpi
            evidence['window_scale_percent'] = int(round(dpi * 100 / 96))
        return evidence

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
            evidence['exists'] = bool(wrapper.exists(timeout=0.5))
        except Exception:
            evidence['exists'] = True
        try:
            evidence['visible_now'] = bool(wrapper.is_visible())
        except Exception:
            evidence['visible_now'] = None
        try:
            evidence['enabled_now'] = bool(wrapper.is_enabled())
        except Exception:
            evidence['enabled_now'] = None
        try:
            evidence['focused'] = bool(wrapper.has_keyboard_focus())
        except Exception:
            evidence['focused'] = None
        try:
            evidence['selected'] = bool(wrapper.is_selected())
        except Exception:
            evidence['selected'] = None
        try:
            evidence['value'] = wrapper.get_value()
        except Exception:
            evidence['value'] = None
        dpi = WindowsUIBackend._window_dpi(wrapper)
        if dpi:
            evidence['dpi'] = dpi
            evidence['scale_percent'] = int(round(dpi * 100 / 96))
        evidence['observed'] = True
        return evidence