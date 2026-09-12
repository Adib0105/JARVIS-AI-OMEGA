"""Lightweight animated Friday portrait; no GPU, downloads or extra runtime."""
from __future__ import annotations
import math
import tkinter as tk


class ArcReactorHUD(tk.Canvas):
    """Keep the existing HUD interface while rendering the Friday persona."""
    COLORS = {'idle': '#bdabff', 'thinking': '#ffd39a', 'speaking': '#79ebcf',
              'listening': '#e9a7e3', 'paused': '#9da6c0', 'error': '#ff7e96'}

    def __init__(self, parent, size=220, **kwargs):
        super().__init__(parent, width=size, height=size,
                         bg=kwargs.pop('bg', '#101525'), highlightthickness=0, bd=0, **kwargs)
        self.size, self.state, self.phase = size, 'idle', 0.0
        self._running = True
        self._timer = self.after(40, self._animate)
        self.bind('<Destroy>', self._destroyed, add='+')

    def _destroyed(self, event):
        if event.widget is self:
            self.stop()

    def set_state(self, state):
        self.state = state if state in self.COLORS else 'idle'

    def stop(self):
        self._running = False
        if self._timer is not None:
            try:
                self.after_cancel(self._timer)
            except tk.TclError:
                pass
            self._timer = None

    def _animate(self):
        self._timer = None
        if not self._running:
            return
        # Hidden-to-tray windows do not need portrait rendering.
        if self.winfo_viewable():
            self.phase = (self.phase + 0.04) % 120
            self.delete('all')
            self._portrait()
        self._timer = self.after(40 if self.winfo_viewable() else 250, self._animate)

    def _portrait(self):
        s = self.size / 220
        bob = math.sin(self.phase * 1.4) * 1.5
        color = self.COLORS[self.state]
        def oval(box, **kw):
            return self.create_oval(*(v*s for v in box), **kw)
        def line(points, **kw):
            return self.create_line(*(v*s for v in points), **kw)
        def poly(points, **kw):
            return self.create_polygon(*(v*s for v in points), **kw)
        oval((12, 9, 208, 205), fill='#111d35', outline='#34456b', width=1)
        oval((22, 19, 198, 195), outline=color, width=1)
        for i in range(7):
            x = 40 + i*23
            oval((x, 35+(i%3)*12, x+2, 37+(i%3)*12), fill='#738eb7', outline='')
        # Hair silhouette, shoulders, collar and neck.
        oval((61, 32+bob, 159, 169+bob), fill='#22223f', outline='#5b547e', width=2)
        poly((30,195, 51,163, 86,151, 133,151, 169,166, 191,195),
             fill='#28385c', outline='#60739f', smooth=True)
        poly((91,131+bob, 128,131+bob, 132,157, 111,175, 88,157), fill='#c9938e', smooth=True)
        poly((70,157, 89,149, 111,173, 96,189), fill='#54698e', smooth=True)
        poly((150,157, 130,149, 111,173, 127,189), fill='#54698e', smooth=True)
        oval((76,49+bob, 146,149+bob), fill='#e9b8a8', outline='#f6d8c6', width=1)
        # Swept hair framing the face.
        poly((65,112, 65,42, 104,25, 147,37, 159,102, 144,92, 136,53,
              114,58, 95,69, 79,86, 74,133), fill='#272640', smooth=True)
        line((80,64, 101,43, 130,41, 146,64), fill='#696083', smooth=True, width=2)
        blink = self.phase % 4.6 > 4.42
        for x in (94,127):
            y = 95 + bob
            line((x-8,y-10,x,y-12,x+7,y-10), fill='#57404d', smooth=True, width=2)
            if blink:
                line((x-8,y,x,y+2,x+8,y), fill='#594251', smooth=True, width=2)
            else:
                oval((x-8,y-4,x+8,y+5), fill='#fff0e7', outline='#895b68')
                oval((x-3,y-3,x+3,y+5), fill='#51758a', outline='')
                oval((x-1,y-1,x+2,y+3), fill='#19283c', outline='')
                oval((x-1,y-2,x+1,y), fill='white', outline='')
        line((110,102+bob,107,116+bob,113,116+bob), fill='#b67a78', smooth=True)
        # Speaking animation indicates playback state; it is not phoneme lip sync.
        mouth = 2 + (4*abs(math.sin(self.phase*13)) if self.state == 'speaking' else 0)
        oval((100,125+bob-mouth/2,122,128+bob+mouth), fill='#85465f', outline='#b7677f')
        line((101,125+bob,110,123+bob,121,125+bob), fill='#d98195', smooth=True)
        oval((149,104,155,110), fill=color, outline='')
        line((152,109,150,122,141,126), fill=color, width=2, smooth=True)
        self.create_text(110*s, 207*s, text='F R I D A Y', fill=color, font=('Segoe UI', max(8,int(11*s)), 'bold'))
        self.create_text(110*s, 17*s, text=self.state.upper(), fill=color, font=('Segoe UI', max(7,int(8*s))))
