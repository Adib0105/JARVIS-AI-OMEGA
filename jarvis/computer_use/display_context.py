from __future__ import annotations

import ctypes
import os
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DisplayContext:
    available: bool
    monitor_count: int
    virtual_left: int
    virtual_top: int
    virtual_width: int
    virtual_height: int
    primary_width: int
    primary_height: int
    system_dpi: int
    scale_percent: int
    detail: str

    @property
    def virtual_bounds(self) -> tuple[int, int, int, int]:
        return (
            self.virtual_left,
            self.virtual_top,
            self.virtual_left + self.virtual_width,
            self.virtual_top + self.virtual_height,
        )

    def as_dict(self) -> dict:
        data = asdict(self)
        data['virtual_bounds'] = list(self.virtual_bounds)
        return data


def get_display_context() -> DisplayContext:
    """Observe Windows display geometry without changing process DPI state.

    The action engine uses physical UIA coordinates. Reporting virtual-desktop bounds
    and effective DPI makes multi-monitor/DPI mismatches visible instead of silently
    assuming a single 100%-scaled primary display.
    """
    if os.name != 'nt':
        return DisplayContext(False, 0, 0, 0, 0, 0, 0, 0, 96, 100, 'Windows display metrics unavailable on this platform.')

    try:
        user32 = ctypes.windll.user32
        # GetSystemMetrics constants from WinUser.h.
        primary_width = int(user32.GetSystemMetrics(0))
        primary_height = int(user32.GetSystemMetrics(1))
        virtual_left = int(user32.GetSystemMetrics(76))
        virtual_top = int(user32.GetSystemMetrics(77))
        virtual_width = int(user32.GetSystemMetrics(78))
        virtual_height = int(user32.GetSystemMetrics(79))
        monitor_count = max(1, int(user32.GetSystemMetrics(80)))
        dpi = 96
        try:
            get_dpi = user32.GetDpiForSystem
            get_dpi.restype = ctypes.c_uint
            dpi = max(1, int(get_dpi()))
        except Exception:
            pass
        scale = max(50, min(500, int(round(dpi * 100 / 96))))
        return DisplayContext(
            True,
            monitor_count,
            virtual_left,
            virtual_top,
            virtual_width,
            virtual_height,
            primary_width,
            primary_height,
            dpi,
            scale,
            'Windows virtual-desktop metrics observed.',
        )
    except Exception as exc:
        return DisplayContext(False, 0, 0, 0, 0, 0, 0, 0, 96, 100, f'{type(exc).__name__}: {exc}')
