"""Tk wrapper that preserves the existing reactor's set_state interface."""
from __future__ import annotations

import tkinter as tk

from jarvis.ui import theme
from jarvis.ui.widgets import Reactor
from jarvis.ui.effects import ActivityWave, motion_clock, blend


class Reactor3D(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=theme.PANEL, **kwargs)
        self.mode = "idle"
        self.message = "TIZIM TAYYOR"
        self.error = ""
        self.revision = 0
        self.viewport = None
        self.fallback = None
        self.status = tk.Label(self, text=self.message, bg=theme.PANEL, fg=theme.CYAN,
                               font=(theme.MONO, 9, "bold"), pady=5)
        self.status.pack(side="bottom", fill="x")
        self.hint = tk.Label(self, text="3D CORE  ·  USHLAB AYLANTIRING  ·  G'ILDIRAK: ZOOM",
                             bg=theme.PANEL, fg=theme.MUTED, font=(theme.MONO, 7))
        self.hint.pack(side="bottom", fill="x")
        self.wave = ActivityWave(self, lambda: self.mode)
        self.wave.pack(side="bottom", fill="x")
        motion_clock(self).subscribe(self, self._animate_status)
        try:
            from jarvis.ui.native3d import CoreViewport
            self.viewport = CoreViewport(self, on_error=self._failed)
            self.viewport.pack(fill="both", expand=True)
        except Exception as error:
            self._failed(error)

    def _animate_status(self, elapsed, delta, enabled):
        import math
        color = {"speaking": theme.GREEN, "thinking": theme.AMBER}.get(self.mode, theme.CYAN)
        self.status.configure(fg=blend(theme.MUTED, color, .75+.2*math.sin(elapsed*2) if enabled else 1.))
        if self.viewport is not None:
            self.viewport.motion_enabled = enabled

    @property
    def ready(self):
        return self.viewport is not None and self.viewport.ready

    def _failed(self, error):
        if self.fallback is not None or not self.winfo_exists():
            return
        self.error = str(error)
        if self.viewport is not None:
            self.viewport.destroy()
            self.viewport = None
        self.fallback = Reactor(self)
        self.fallback.pack(fill="both", expand=True)
        self.fallback.set_state(self.mode, self.message)
        self.status.pack_forget()
        self.hint.configure(text="ODDIY YADRO  ·  3D RENDERER ISHGA TUSHMADI")

    def set_state(self, mode, message):
        self.revision += 1
        self.mode = mode if mode in {"idle", "thinking", "speaking", "listening"} else "idle"
        self.message = message.upper()
        self.status.configure(text=self.message, fg=theme.GREEN if self.mode == "speaking" else theme.CYAN)
        if self.viewport is not None:
            self.viewport.mode = self.mode
        if self.fallback is not None:
            self.fallback.set_state(self.mode, self.message)

    def destroy(self):
        if self.viewport is not None:
            self.viewport.destroy()
            self.viewport = None
        super().destroy()
