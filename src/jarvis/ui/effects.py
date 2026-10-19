"""Shared, lifecycle-safe animation clock and lightweight HUD effects for Tk."""
from __future__ import annotations

import math
import sys
import time
import tkinter as tk
from functools import lru_cache

from jarvis.ui import theme


def blend(start: str, end: str, amount: float) -> str:
    return _blend_cached(start, end, round(max(0., min(1., amount))*1024))


@lru_cache(maxsize=8192)
def _blend_cached(start, end, step):
    amount = step/1024
    channels = [round(int(start[i:i+2], 16) * (1-amount) + int(end[i:i+2], 16) * amount)
                for i in (1, 3, 5)]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def approach(current: float, target: float, delta: float, speed: float = 16.) -> float:
    value = current + (target-current) * (1-math.exp(-speed*delta))
    return target if abs(value-target) < .002 else value


class MotionClock:
    """One 30 Hz Tk timer for all chrome, paused while the window is hidden."""
    def __init__(self, root):
        self.root = root
        self.enabled = True
        self.closed = False
        self.elapsed = 0.
        self.last = time.perf_counter()
        self.listeners = {}
        self.sequence = 0
        self.job = None
        root.bind("<Destroy>", self._destroy, add="+")
        self._schedule()

    def subscribe(self, widget, callback):
        self.sequence += 1
        token = self.sequence
        self.listeners[token] = (widget, callback)
        widget.bind("<Destroy>", lambda event: self.listeners.pop(token, None)
                    if event.widget is widget else None, add="+")
        return token

    def _schedule(self):
        if not self.closed:
            self.job = self.root.after(33 if self.enabled and self.root.winfo_viewable() else 150, self._tick)

    def _tick(self):
        self.job = None
        if self.closed:
            return
        now = time.perf_counter()
        delta = min(.1, max(0., now-self.last))
        self.last = now
        if self.root.winfo_viewable():
            if self.enabled:
                self.elapsed += delta
            for token, (widget, callback) in tuple(self.listeners.items()):
                if token in self.listeners and widget.winfo_viewable():
                    try:
                        callback(self.elapsed, delta, self.enabled)
                    except Exception:
                        self.root.report_callback_exception(*sys.exc_info())
        self._schedule()

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)

    def _destroy(self, event):
        if event.widget is self.root:
            self.close()

    def close(self):
        self.closed = True
        if self.job:
            self.root.after_cancel(self.job)
            self.job = None
        self.listeners.clear()


def motion_clock(widget):
    root = widget._root()
    if not hasattr(root, "_motion_clock"):
        root._motion_clock = MotionClock(root)
    return root._motion_clock


class HoverEffect:
    """Color-only easing: no layout jumps, focus theft, or command interception."""
    def __init__(self, widget, *, background=theme.PANEL_ALT, foreground=theme.TEXT,
                 border=theme.BORDER, hover_background="#103b52", accent=theme.CYAN):
        self.widget = widget
        self.background, self.foreground, self.border = background, foreground, border
        self.hover_background, self.accent = hover_background, accent
        self.hovered = self.focused = self.pressed = False
        self.amount = 0.
        self.last_style = None
        options = widget.keys()
        self.has_state = 'state' in options
        self.has_foreground = 'foreground' in options
        self.clock = motion_clock(widget)
        self.clock.subscribe(widget, self._frame)
        for event, name, value in (("<Enter>", "hovered", True), ("<Leave>", "hovered", False),
                                   ("<FocusIn>", "focused", True), ("<FocusOut>", "focused", False),
                                   ("<ButtonPress-1>", "pressed", True), ("<ButtonRelease-1>", "pressed", False)):
            widget.bind(event, lambda _, n=name, v=value: self._change(n, v), add="+")

    def _change(self, name, value):
        setattr(self, name, value)
        if name == "hovered" and not value:
            self.pressed = False
        self._frame(self.clock.elapsed, .033, self.clock.enabled)

    def _frame(self, elapsed, delta, enabled):
        widget = self.widget
        disabled = str(widget.cget("state")) == "disabled" if self.has_state else False
        target = 0. if disabled else (1. if self.hovered or self.focused else 0.)
        self.amount = approach(self.amount, target, delta) if enabled else target
        amount = self.amount
        if self.pressed and not disabled:
            amount = 1.
        style = (blend(self.background, self.hover_background, amount),
                 blend(self.foreground, "#ffffff", amount*.65),
                 blend(self.border, self.accent, amount),
                 1 if self.pressed and not disabled else 0)
        if style != self.last_style:
            options = dict(bg=style[0], highlightbackground=style[2], highlightcolor=self.accent)
            if self.has_foreground:
                options["fg"] = style[1]
            widget.configure(**options)
            if isinstance(widget, tk.Button):
                widget.configure(relief="sunken" if style[3] else "flat")
            self.last_style = style


class ScanStrip(tk.Canvas):
    """A soft moving highlight; Canvas items are reused rather than recreated."""
    def __init__(self, parent, *, accent=theme.CYAN, height=3, **kwargs):
        super().__init__(parent, width=1, height=height, bg=theme.PANEL, highlightthickness=0,
                         takefocus=False, **kwargs)
        self.accent = accent
        self.lines = [self.create_line(0, 1, 1, 1, fill=blend(theme.BORDER, accent, (1-abs(index-7)/8)*.8), width=max(1, height-1)) for index in range(15)]
        self.bind("<Configure>", lambda _: self._frame(0., 0., False))
        motion_clock(self).subscribe(self, self._frame)

    def _frame(self, elapsed, delta, enabled):
        width, height = self.winfo_width(), self.winfo_height()
        center = (elapsed*.16 % 1.4-.2)*width if enabled else width*.5
        radius = max(24, width*.13)
        for index, line in enumerate(self.lines):
            x = center+(index-7)*radius/7
            self.coords(line, max(0, x-radius/14), height/2, min(width, max(0, x+radius/14)), height/2)


class ActivityWave(tk.Canvas):
    """Decorative state visualization, not a microphone amplitude measurement."""
    def __init__(self, parent, state, **kwargs):
        super().__init__(parent, width=1, height=24, bg=theme.PANEL, highlightthickness=0,
                         takefocus=False, **kwargs)
        self.state = state
        self.bars = [self.create_line(0, 0, 0, 0, fill=theme.CYAN, width=2) for _ in range(48)]
        motion_clock(self).subscribe(self, self._frame)

    def _frame(self, elapsed, delta, enabled):
        mode = self.state()
        color = {"speaking": theme.GREEN, "thinking": theme.AMBER, "listening": theme.CYAN}.get(mode, theme.CYAN)
        width, height = self.winfo_width(), self.winfo_height()
        span = min(300, width*.8)
        speed = {"idle": 1.2, "listening": 5., "speaking": 9., "thinking": 6.}.get(mode, 1.)
        for index, bar in enumerate(self.bars):
            x = (width-span)/2+index*span/47
            envelope = math.sin(math.pi*(index+.5)/48)**.7
            wave = .25+.75*abs(math.sin(index*.46+elapsed*speed)*math.cos(index*.17-elapsed*speed*.37))
            amplitude = (2+envelope*wave*(8 if mode != "idle" else 3)) if enabled else 2
            self.coords(bar, x, height/2-amplitude, x, height/2+amplitude)
            self.itemconfigure(bar, fill=blend(theme.BORDER, color, .25+envelope*.7))


class MetricGauge(tk.Canvas):
    """Smooth real percentage readouts; ACTIVE is an activity indicator, not CPU %."""
    def __init__(self, parent):
        super().__init__(parent, width=78, height=82, bg=theme.PANEL_ALT,
                         highlightthickness=0, takefocus=False)
        self.target = self.value = 0.
        self.caption = "—"
        self._last = None
        self.track = self.create_arc(0, 0, 0, 0, start=135, extent=-270,
                                     style="arc", outline=theme.BORDER, width=4)
        self.ring = self.create_arc(0, 0, 0, 0, start=135, extent=0,
                                    style="arc", outline=theme.CYAN, width=4)
        self.readout = self.create_text(0, 0, fill=theme.CYAN_SOFT, font=(theme.MONO, 10, "bold"))
        self.bind("<Configure>", lambda _: self._frame(0, 0, False))
        motion_clock(self).subscribe(self, self._frame)

    def set_value(self, value):
        self.caption = str(value)
        try:
            self.target = max(0., min(100., float(self.caption.rstrip("%"))))
        except ValueError:
            self.target = 0.

    def _frame(self, elapsed, delta, enabled):
        self.value = approach(self.value, self.target, delta, 5.) if enabled else self.target
        width, height = self.winfo_width(), self.winfo_height()
        state = (width, height, round(self.value, 1), self.caption, round(elapsed*65, 1) if self.caption == 'ACTIVE' and enabled else 0)
        if state == self._last:
            return
        self._last = state
        radius = min(width/2-9, height/2-8)
        box = (width/2-radius, height/2-radius, width/2+radius, height/2+radius)
        self.coords(self.track, *box)
        self.coords(self.ring, *box)
        self.coords(self.readout, width/2, height/2)
        active = self.caption == "ACTIVE"
        self.itemconfigure(self.ring, start=135-(elapsed*65 if active and enabled else 0),
                           extent=-70 if active else -270*self.value/100,
                           outline=theme.AMBER if self.value >= 85 else theme.CYAN)
        self.itemconfigure(self.readout, text=self.caption)


class NeuralRibbon(tk.Canvas):
    """Bounded HUD: two flowing strands, traveling packets, stars and pointer parallax.

    Decorative only, not fabricated microphone/network telemetry. Items are allocated once.
    """
    def __init__(self, parent, *, state=lambda: 'idle', height=38):
        super().__init__(parent, width=1, height=height, bg=theme.PANEL, highlightthickness=0, takefocus=False)
        self.state = state
        self.pointer = 0.
        self._accent = None
        self.strands = [self.create_line(0, 0, 1, 1, fill=color, width=1, smooth=True) for color in ('#175570', '#123e53')]
        self.links = [self.create_line(0, 0, 1, 1, fill='#103e52') for _ in range(18)]
        self.halos = [self.create_oval(0, 0, 1, 1, outline='#164b60') for _ in range(10)]
        self.packets = [self.create_oval(0, 0, 1, 1, outline='', fill=theme.CYAN) for _ in range(10)]
        self.stars = [self.create_oval(0, 0, 1, 1, outline='', fill='#16465a') for _ in range(24)]
        self.bind('<Motion>', lambda event: setattr(self, 'pointer', event.x/max(1, self.winfo_width())-.5))
        self.bind('<Leave>', lambda _: setattr(self, 'pointer', 0.))
        motion_clock(self).subscribe(self, self._frame)

    def _frame(self, elapsed, delta, enabled):
        width, height = self.winfo_width(), self.winfo_height()
        t = elapsed  # The shared clock already freezes elapsed in reduced-motion mode.
        mode = self.state()
        accent = {'thinking': theme.AMBER, 'speaking': theme.GREEN}.get(mode, theme.CYAN)
        if accent != self._accent:
            for packet in self.packets:
                self.itemconfigure(packet, fill=accent)
            self._accent = accent
        speed = 1.8 if mode != 'idle' else .7
        def y(x, strand=0):
            return height/2+math.sin(x/max(width, 1)*math.pi*4-t*speed+strand*math.pi)*(height*.26)+self.pointer*3
        for index, line in enumerate(self.strands):
            points = []
            for segment in range(61):
                x = segment*width/60
                points.extend((x, y(x, index)))
            self.coords(line, *points)
        for index, link in enumerate(self.links):
            x = ((index/18+t*.025) % 1)*width
            self.coords(link, x, y(x), x, y(x, 1))
        for index, (packet, halo) in enumerate(zip(self.packets, self.halos)):
            x = ((index/10+t*.055*speed) % 1)*width
            cy = y(x, index % 2)
            size = 1.5+(.5+.5*math.sin(t*3+index))
            self.coords(packet, x-size, cy-size, x+size, cy+size)
            self.coords(halo, x-size-3, cy-size-3, x+size+3, cy+size+3)
        for index, star in enumerate(self.stars):
            x = ((index*.6180339+t*.008) % 1)*width
            cy = ((index*.381966) % 1)*height
            self.coords(star, x, cy, x+1, cy+1)
            self.itemconfigure(star, fill=blend('#0c2435', accent, .12+.3*abs(math.sin(t*.9+index))))
