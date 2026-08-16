from __future__ import annotations

import math
import tkinter as tk


class ArcReactorHUD(tk.Canvas):
    """Lightweight Iron-Man-inspired animated HUD made entirely with Tkinter."""

    COLORS = {
        'idle': '#53e7ff',
        'thinking': '#ffd166',
        'speaking': '#6affb8',
        'listening': '#d98cff',
        'paused': '#86a8b8',
        'error': '#ff5c73',
    }

    def __init__(self, parent, size: int = 220, **kwargs):
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=kwargs.pop('bg', '#06111b'),
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self.size = size
        self.state = 'idle'
        self.phase = 0.0
        self._running = True
        self.after(40, self._animate)

    def set_state(self, state: str) -> None:
        self.state = state if state in self.COLORS else 'idle'

    def stop(self) -> None:
        self._running = False

    def _ring(self, margin: float, color: str, width: int, start: float, extent: float, style='arc'):
        self.create_arc(
            margin,
            margin,
            self.size - margin,
            self.size - margin,
            start=start,
            extent=extent,
            outline=color,
            width=width,
            style=style,
        )

    def _animate(self) -> None:
        if not self._running:
            return
        self.delete('all')
        self.phase = (self.phase + 4.5) % 360
        color = self.COLORS[self.state]
        c = self.size / 2

        self.create_oval(8, 8, self.size - 8, self.size - 8, outline='#12394a', width=1)
        self.create_line(c, 5, c, self.size - 5, fill='#0c2c3a')
        self.create_line(5, c, self.size - 5, c, fill='#0c2c3a')

        pulse = 3.0 + 2.0 * (1 + math.sin(math.radians(self.phase * 2))) / 2
        self._ring(18, '#16475c', 2, self.phase, 245)
        self._ring(28, color, 3, -self.phase * 1.25, 105)
        self._ring(28, color, 3, 180 - self.phase * 1.25, 80)
        self._ring(42, '#2a7890', 2, self.phase * 1.7, 55)
        self._ring(42, '#2a7890', 2, 180 + self.phase * 1.7, 55)

        radius = 46 + 3 * math.sin(math.radians(self.phase * 3))
        self.create_oval(c - radius, c - radius, c + radius, c + radius, outline=color, width=int(pulse))
        self.create_oval(c - 32, c - 32, c + 32, c + 32, fill='#092431', outline='#b9f6ff', width=2)
        self.create_oval(c - 18, c - 18, c + 18, c + 18, fill=color, outline='#e8fdff', width=2)

        for i in range(12):
            a = math.radians(i * 30 + self.phase * 0.35)
            r1, r2 = 58, 72
            x1, y1 = c + math.cos(a) * r1, c + math.sin(a) * r1
            x2, y2 = c + math.cos(a) * r2, c + math.sin(a) * r2
            self.create_line(x1, y1, x2, y2, fill=color, width=2)

        self.create_text(c, c - 4, text='JARVIS', fill='#041017', font=('Consolas', 9, 'bold'))
        self.create_text(c, c + 12, text='V7', fill='#041017', font=('Consolas', 8, 'bold'))
        self.create_text(c, self.size - 17, text=self.state.upper(), fill=color, font=('Consolas', 9, 'bold'))

        if self.state in {'speaking', 'listening', 'thinking'}:
            base_y = self.size - 38
            for i in range(15):
                x = c - 52 + i * 7.5
                amp = 4 + 8 * abs(math.sin(math.radians(self.phase * 2 + i * 27)))
                if self.state == 'thinking':
                    amp *= 0.55
                self.create_line(x, base_y - amp, x, base_y + amp, fill=color, width=2)

        self.after(40, self._animate)
