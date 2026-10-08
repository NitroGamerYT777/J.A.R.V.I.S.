from __future__ import annotations

import math
import random
import tkinter as tk
from tkinter import messagebox
from collections.abc import Callable

from jarvis.ui import theme
from jarvis.agents import AGENTS
from jarvis.tasks import COMPLETED, FAILED, PENDING_APPROVAL, PLANNED, REJECTED, RUNNING, Task


class Panel(tk.Frame):
    def __init__(self, parent: tk.Misc, title: str, *, accent: str = theme.CYAN, **kwargs: object) -> None:
        super().__init__(parent, bg=theme.PANEL, highlightbackground=theme.BORDER, highlightthickness=1, **kwargs)
        header = tk.Frame(self, bg=theme.PANEL)
        header.pack(fill="x", padx=12, pady=(9, 4))
        tk.Frame(header, bg=accent, width=3, height=14).pack(side="left", padx=(0, 7))
        tk.Label(
            header, text=title.upper(), bg=theme.PANEL, fg=theme.CYAN_SOFT,
            font=(theme.MONO, 9, "bold"),
        ).pack(side="left")
        self.body = tk.Frame(self, bg=theme.PANEL)
        self.body.pack(fill="both", expand=True, padx=12, pady=(3, 11))


class Reactor(tk.Canvas):
    """Animated centrepiece which signals idle, thinking, and speaking states."""

    def __init__(self, parent: tk.Misc, **kwargs: object) -> None:
        super().__init__(parent, bg=theme.PANEL, highlightthickness=0, **kwargs)
        self.phase = 0.0
        self.mode = "idle"
        self.message = "TIZIM TAYYOR"
        self.bind("<Configure>", lambda _event: self._draw())
        self.after(30, self._animate)

    def set_state(self, mode: str, message: str) -> None:
        self.mode = mode
        self.message = message.upper()
        self._draw()

    def _animate(self) -> None:
        self.phase += 0.09 if self.mode == "thinking" else 0.035
        self._draw()
        self.after(30, self._animate)

    def _draw(self) -> None:
        self.delete("all")
        width, height = max(self.winfo_width(), 1), max(self.winfo_height(), 1)
        center_x, center_y = width / 2, height / 2 - 5
        radius = min(width * 0.32, height * 0.34)
        pulse = math.sin(self.phase * 2) * 3
        glow = theme.GREEN if self.mode == "speaking" else theme.CYAN

        # Fine scanner lines and rotating digital rings.
        for step in range(3):
            r = radius + step * 14 + pulse
            self.create_oval(center_x-r, center_y-r, center_x+r, center_y+r, outline="#0b5470", width=1)
        for index in range(72):
            angle = (index * 5 + self.phase * 20) * math.pi / 180
            inner = radius + 17
            length = 10 if index % 3 else 18
            x1, y1 = center_x + math.cos(angle) * inner, center_y + math.sin(angle) * inner
            x2, y2 = center_x + math.cos(angle) * (inner + length), center_y + math.sin(angle) * (inner + length)
            self.create_line(x1, y1, x2, y2, fill="#126982", width=1)
        for offset, extent, color in ((self.phase * 70, 95, glow), (-self.phase * 45 + 150, 55, theme.BLUE), (245, 35, theme.AMBER)):
            r = radius + 2
            self.create_arc(center_x-r, center_y-r, center_x+r, center_y+r, start=offset, extent=extent, style="arc", outline=color, width=4)

        # Orbital data points.
        for index in range(8):
            angle = self.phase + index * math.pi / 4
            orbit_x, orbit_y = radius * 1.2, radius * 0.53
            x = center_x + math.cos(angle) * orbit_x
            y = center_y + math.sin(angle) * orbit_y
            size = 2 + (index % 2)
            self.create_oval(x-size, y-size, x+size, y+size, fill=glow, outline="")
        for index in range(35):
            angle = index * math.pi * 2 / 35 + self.phase / 4
            r = radius * (0.45 + (index % 5) / 18)
            x, y = center_x + math.cos(angle) * r, center_y + math.sin(angle) * r
            self.create_oval(x-1, y-1, x+1, y+1, fill="#176681", outline="")

        self.create_oval(center_x-radius*.58, center_y-radius*.58, center_x+radius*.58, center_y+radius*.58, outline=glow, width=2)
        self.create_text(center_x, center_y-8, text="J A R V I S", fill=theme.CYAN_SOFT, font=(theme.MONO, max(18, int(radius*.25)), "bold"))
        self.create_text(center_x, center_y+26, text="AI COMMAND CORE", fill=theme.MUTED, font=(theme.MONO, 9, "bold"))
        self.create_text(center_x, height-20, text=self.message, fill=glow, font=(theme.MONO, 9, "bold"))


class StatusRow(tk.Frame):
    def __init__(self, parent: tk.Misc, icon: str, title: str, value: str, color: str = theme.CYAN) -> None:
        super().__init__(parent, bg=theme.PANEL_ALT, highlightbackground=theme.BORDER, highlightthickness=1)
        tk.Label(self, text=icon, bg=theme.PANEL_ALT, fg=color, font=(theme.FONT, 13)).pack(side="left", padx=(8, 6), pady=7)
        texts = tk.Frame(self, bg=theme.PANEL_ALT)
        texts.pack(side="left", fill="x", expand=True, pady=5)
        tk.Label(texts, text=title, bg=theme.PANEL_ALT, fg=theme.TEXT, font=(theme.FONT, 8, "bold")).pack(anchor="w")
        self.value = tk.Label(texts, text=value, bg=theme.PANEL_ALT, fg=theme.MUTED, font=(theme.MONO, 7))
        self.value.pack(anchor="w")


class GlowButton(tk.Button):
    def __init__(self, parent: tk.Misc, text: str, command: Callable[[], None], **kwargs: object) -> None:
        font = kwargs.pop("font", (theme.FONT, 9))
        super().__init__(
            parent, text=text, command=command, bg=theme.PANEL_ALT, fg=theme.CYAN_SOFT,
            activebackground=theme.BLUE, activeforeground="white", relief="flat",
            highlightbackground=theme.BORDER, highlightthickness=1, font=font, cursor="hand2", **kwargs,
        )


class AgentPanel(Panel):
    """Shows capability-focused agents and their live connection state."""

    def __init__(self, parent: tk.Misc, on_select: Callable[[str], None]) -> None:
        super().__init__(parent, "Agents & skills", accent=theme.GREEN)
        self.on_select = on_select
        self.rows: dict[str, tk.Label] = {}
        self.connected = {agent.key: agent.connected for agent in AGENTS}
        for agent in AGENTS:
            row = tk.Frame(self.body, bg=theme.PANEL_ALT, highlightbackground=theme.BORDER, highlightthickness=1)
            row.pack(fill="x", pady=3)
            dot = "●" if agent.connected else "○"
            tk.Label(row, text=dot, bg=theme.PANEL_ALT, fg=agent.color, font=(theme.MONO, 12)).pack(side="left", padx=(8, 5), pady=7)
            info = tk.Frame(row, bg=theme.PANEL_ALT)
            info.pack(side="left", fill="x", expand=True, pady=4)
            tk.Label(info, text=agent.name.upper(), bg=theme.PANEL_ALT, fg=theme.TEXT, font=(theme.FONT, 8, "bold")).pack(anchor="w")
            label = tk.Label(info, text="ULANGAN" if agent.connected else "ULANMAGAN", bg=theme.PANEL_ALT, fg=agent.color if agent.connected else theme.MUTED, font=(theme.MONO, 7))
            label.pack(anchor="w")
            self.rows[agent.key] = label
            for widget in (row, info, *row.winfo_children(), *info.winfo_children()):
                widget.bind("<Button-1>", lambda _event, key=agent.key: self.on_select(key))
                widget.configure(cursor="hand2")

    def set_working(self, agent_key: str, working: bool) -> None:
        for key, label in self.rows.items():
            agent = next(item for item in AGENTS if item.key == key)
            if key == agent_key and working:
                label.configure(text="BAJARILMOQDA", fg=theme.GREEN)
            else:
                is_connected = self.connected[key]
                label.configure(text="ULANGAN" if is_connected else "ULANMAGAN", fg=agent.color if is_connected else theme.MUTED)

    def set_connected(self, agent_key: str, connected: bool, detail: str | None = None) -> None:
        self.connected[agent_key] = connected
        agent = next(item for item in AGENTS if item.key == agent_key)
        self.rows[agent_key].configure(text=detail or ("ULANGAN" if connected else "ULANMAGAN"), fg=agent.color if connected else theme.MUTED)


class TaskPanel(Panel):
    """Task approval and completion log embedded in the command centre."""

    STATUS_COLORS = {
        PENDING_APPROVAL: theme.AMBER, PLANNED: theme.CYAN, RUNNING: theme.CYAN,
        COMPLETED: theme.GREEN, REJECTED: theme.MUTED, FAILED: theme.RED,
    }

    def __init__(self, parent: tk.Misc, approve: Callable[[int], None], reject: Callable[[int], None]) -> None:
        super().__init__(parent, "Tasks / approval queue", accent=theme.AMBER)
        self.approve, self.reject = approve, reject
        self.tasks: list[Task] = []
        self.listbox = tk.Listbox(self.body, bg=theme.PANEL, fg=theme.TEXT, selectbackground=theme.BLUE, selectforeground="white", relief="flat", highlightthickness=0, font=(theme.FONT, 8), activestyle="none")
        self.listbox.pack(fill="both", expand=True)
        self.status = tk.Label(self.body, text="Tasdiqlanishi kerak bo'lgan amal yo'q.", bg=theme.PANEL, fg=theme.MUTED, wraplength=225, justify="left", font=(theme.FONT, 8))
        self.status.pack(fill="x", pady=(7, 3))
        buttons = tk.Frame(self.body, bg=theme.PANEL)
        buttons.pack(fill="x")
        GlowButton(buttons, "TASDIQLASH", self._approve_selected, font=(theme.FONT, 8, "bold")).pack(side="left", fill="x", expand=True, padx=(0, 3))
        GlowButton(buttons, "RAD ETISH", self._reject_selected, font=(theme.FONT, 8, "bold")).pack(side="left", fill="x", expand=True, padx=(3, 0))
        GlowButton(self.body, "BATAFSIL KO'RISH", self._show_details, font=(theme.FONT, 8)).pack(fill="x", pady=(5, 0))
        self.listbox.bind("<<ListboxSelect>>", self._show_selected)

    def refresh(self, tasks: list[Task]) -> None:
        self.tasks = tasks
        selected = self.listbox.curselection()
        self.listbox.delete(0, "end")
        for task in tasks:
            self.listbox.insert("end", f"[{task.status}] {task.title}")
        if selected and selected[0] < len(tasks):
            self.listbox.selection_set(selected[0])
        elif tasks:
            self.listbox.selection_set(0)
        self._show_selected()

    def _selected_task(self) -> Task | None:
        selected = self.listbox.curselection()
        return self.tasks[selected[0]] if selected else None

    def _show_selected(self, _event: tk.Event[tk.Misc] | None = None) -> None:
        task = self._selected_task()
        if not task:
            self.status.configure(text="Tasdiqlanishi kerak bo'lgan amal yo'q.", fg=theme.MUTED)
            return
        detail = task.result or ("Bu amal bajarilishidan oldin ruxsatingiz kerak." if task.requires_approval else "Vazifa rejalashtirilgan.")
        if len(detail) > 180:
            detail = detail[:180] + "…"
        preview = task.payload[:180] + ("…" if len(task.payload) > 180 else "")
        self.status.configure(text=f"{task.status} • {task.action}\n{preview}\n{detail}", fg=self.STATUS_COLORS.get(task.status, theme.TEXT))

    def _approve_selected(self) -> None:
        task = self._selected_task()
        if task and task.status == PENDING_APPROVAL:
            self.approve(task.id)

    def _reject_selected(self) -> None:
        task = self._selected_task()
        if task and task.status == PENDING_APPROVAL:
            self.reject(task.id)

    def _show_details(self) -> None:
        task = self._selected_task()
        if task:
            messagebox.showinfo(
                f"Task #{task.id}",
                f"Agent: {task.agent_key}\nAmal: {task.action}\nHolat: {task.status}\n\nQiymat:\n{task.payload}\n\nNatija:\n{task.result or 'Hali bajarilmadi.'}",
                parent=self,
            )
