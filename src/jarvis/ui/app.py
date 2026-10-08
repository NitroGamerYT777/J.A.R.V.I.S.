from __future__ import annotations

import queue
import json
import re
import threading
import tkinter as tk
import os
import time
from tkinter import messagebox
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from jarvis.agent import Jarvis
from jarvis.agents import AGENTS
from jarvis.automation import BROWSER_ACTIONS, DESKTOP_ACTIONS, browser, execute_automation
from jarvis.config import load_local_env
from jarvis.connections import ConnectionStore, build_ai
from jarvis.intent import AIIntent
from jarvis.llm import AIError
from jarvis.memory import Memory
from jarvis.tasks import COMPLETED, FAILED, REJECTED, RUNNING, Task, TaskPlanner, TaskStore, execute
from jarvis.voice import speak
from jarvis.ui import theme
from jarvis.ui.monitor import system_metrics
from jarvis.ui.widgets import AgentPanel, GlowButton, Panel, Reactor, TaskPanel


class AIProviderConnectionDialog(tk.Toplevel):
    """In-app connector for popular LLM APIs using a user-owned API key."""

    PROVIDERS = (
        ("gemini", "Google Gemini", "gemini-3.6-flash"),
        ("openai", "OpenAI", "gpt-6-astra"),
        ("groq", "Groq", "openai/gpt-oss-20b"),
        ("openrouter", "OpenRouter", "~openai/gpt-latest"),
    )

    def __init__(self, parent: tk.Misc, selected_provider: str, on_connect: callable) -> None:
        super().__init__(parent)
        self.on_connect = on_connect
        self.title("JARVIS • AI API ulash")
        self.configure(bg=theme.PANEL)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        frame = tk.Frame(self, bg=theme.PANEL, padx=22, pady=20)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="AI API ULASH", bg=theme.PANEL, fg=theme.CYAN_SOFT, font=(theme.MONO, 13, "bold")).pack(anchor="w")
        tk.Label(frame, text="Provayder, model va API kalitini tanlang. Kalitlar faqat lokal kompyuteringizda saqlanadi.", bg=theme.PANEL, fg=theme.MUTED, wraplength=370, justify="left", font=(theme.FONT, 9)).pack(anchor="w", pady=(4, 14))
        self.providers = tk.Listbox(frame, height=len(self.PROVIDERS), bg=theme.PANEL_ALT, fg=theme.TEXT, selectbackground=theme.BLUE, relief="flat", font=(theme.MONO, 10), activestyle="none")
        self.providers.pack(fill="x")
        for _, name, _ in self.PROVIDERS:
            self.providers.insert("end", name)
        index = next((i for i, item in enumerate(self.PROVIDERS) if item[0] == selected_provider), 0)
        self.providers.selection_set(index)
        self.providers.bind("<<ListboxSelect>>", self._provider_changed)
        tk.Label(frame, text="MODEL", bg=theme.PANEL, fg=theme.CYAN, font=(theme.MONO, 8, "bold")).pack(anchor="w", pady=(15, 4))
        self.model = tk.Entry(frame, bg=theme.PANEL_ALT, fg=theme.TEXT, insertbackground=theme.CYAN, relief="flat", font=(theme.MONO, 10), width=45)
        self.model.pack(fill="x", ipady=7)
        self.model.insert(0, self.PROVIDERS[index][2])
        tk.Label(frame, text="API KEY", bg=theme.PANEL, fg=theme.CYAN, font=(theme.MONO, 8, "bold")).pack(anchor="w", pady=(15, 4))
        self.key = tk.Entry(frame, show="•", bg=theme.PANEL_ALT, fg=theme.TEXT, insertbackground=theme.CYAN, relief="flat", font=(theme.MONO, 10), width=45)
        self.key.pack(fill="x", ipady=7)
        self.message = tk.Label(frame, text="Kalit faqat lokal .env faylingizda saqlanadi.", bg=theme.PANEL, fg=theme.MUTED, font=(theme.FONT, 8))
        self.message.pack(anchor="w", pady=(5, 13))
        controls = tk.Frame(frame, bg=theme.PANEL)
        controls.pack(fill="x")
        GlowButton(controls, "BEKOR QILISH", self.destroy).pack(side="right")
        GlowButton(controls, "ULASH", self._save, font=(theme.FONT, 9, "bold")).pack(side="right", padx=(0, 7))
        self.key.focus_set()

    def _save(self) -> None:
        selected = self.providers.curselection()
        key = self.key.get().strip()
        model = self.model.get().strip()
        if not selected or not key or not model:
            self.message.configure(text="Model va API kaliti majburiy.", fg=theme.RED)
            return
        provider = self.PROVIDERS[selected[0]][0]
        self.on_connect(provider, key, model)
        self.destroy()

    def _provider_changed(self, _event: tk.Event[tk.Misc]) -> None:
        selected = self.providers.curselection()
        if selected:
            self.model.delete(0, "end")
            self.model.insert(0, self.PROVIDERS[selected[0]][2])


class JarvisApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        load_local_env()
        self.memory = Memory(Path("data") / "jarvis.db")
        self.connections = ConnectionStore(Path("data") / "connections.json")
        self.active_connection = self.connections.default_connection()
        self.tasks = TaskStore(Path("data") / "jarvis.db")
        self.planner = TaskPlanner(self.tasks)
        self.ai = build_ai(self.active_connection)
        self.agent = Jarvis(self.memory, ai=self.ai)
        self.voice_enabled = True
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.title("JARVIS • AI Command Center")
        self.geometry("1360x780")
        self.minsize(980, 620)
        self.configure(bg=theme.BACKGROUND)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build()
        self._tick()
        self.after(80, self._read_events)

    def _build(self) -> None:
        self._build_header()
        content = tk.Frame(self, bg=theme.BACKGROUND)
        content.pack(fill="both", expand=True, padx=15, pady=(0, 12))
        content.grid_columnconfigure(0, weight=0, minsize=175)
        content.grid_columnconfigure(1, weight=4)
        content.grid_columnconfigure(2, weight=1, minsize=250)
        content.grid_rowconfigure(0, weight=3)
        content.grid_rowconfigure(1, weight=2)

        self._build_sidebar(content)
        self._build_centre(content)
        self._build_right(content)
        self._build_bottom(content)
        self._build_command_bar()

    def _build_header(self) -> None:
        header = tk.Frame(self, bg=theme.BACKGROUND, height=62)
        header.pack(fill="x", padx=16, pady=(12, 5))
        header.pack_propagate(False)
        tk.Label(header, text="◉  J A R V I S", bg=theme.BACKGROUND, fg=theme.CYAN_SOFT, font=(theme.MONO, 17, "bold")).pack(side="left")
        tk.Label(header, text="COMMAND CENTER / v1.0", bg=theme.BACKGROUND, fg=theme.MUTED, font=(theme.MONO, 8)).pack(side="left", padx=15)
        self.clock = tk.Label(header, bg=theme.BACKGROUND, fg=theme.CYAN, font=(theme.MONO, 13, "bold"))
        self.clock.pack(side="right", padx=(15, 0))
        provider = self.active_connection.provider.upper() if self.active_connection else "GEMINI"
        self.connection = tk.Label(
            header, text=f"● {provider} ONLINE" if self.ai else "● LOCAL MODE", bg=theme.PANEL,
            fg=theme.GREEN if self.ai else theme.AMBER, font=(theme.MONO, 8, "bold"), padx=12, pady=7,
        )
        self.connection.pack(side="right")
        self.voice_button = GlowButton(header, "🔊 OVOZ: ON", self._toggle_voice, padx=9, pady=4, font=(theme.FONT, 8, "bold"))
        self.voice_button.pack(side="right", padx=(0, 8))

    def _build_sidebar(self, parent: tk.Misc) -> None:
        sidebar = tk.Frame(parent, bg=theme.PANEL, highlightbackground=theme.BORDER, highlightthickness=1)
        sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10))
        tk.Label(sidebar, text="NAVIGATION", bg=theme.PANEL, fg=theme.MUTED, font=(theme.MONO, 8, "bold")).pack(anchor="w", padx=15, pady=(18, 8))
        for label in ("⌘  Command Center", "◌  AI Core", "▣  Agents", "▤  Assignments", "▧  Calendar", "▤  Memory", "▢  Conversations", "⌁  Tools & Skills"):
            active = "Command" in label
            item = tk.Label(sidebar, text=label, anchor="w", bg=theme.PANEL_ALT if active else theme.PANEL, fg=theme.CYAN_SOFT if active else theme.TEXT, font=(theme.FONT, 9), padx=13, pady=9, cursor="hand2" if label in {"▣  Agents", "▤  Assignments"} else "")
            item.pack(fill="x", padx=8, pady=2)
            if label == "▣  Agents":
                item.bind("<Button-1>", lambda _event: self._show_agents_section())
            elif label == "▤  Assignments":
                item.bind("<Button-1>", lambda _event: self._show_assignments_section())
        voice = Panel(sidebar, "Voice status", accent=theme.GREEN)
        voice.pack(side="bottom", fill="x", padx=10, pady=12)
        tk.Label(voice.body, text="◉  STANDBY", bg=theme.PANEL, fg=theme.GREEN, font=(theme.MONO, 9, "bold")).pack(pady=(3, 5))
        tk.Label(voice.body, text="Ovoz moduli keyingi versiyada", bg=theme.PANEL, fg=theme.MUTED, wraplength=135, justify="center", font=(theme.FONT, 8)).pack()

    def _build_centre(self, parent: tk.Misc) -> None:
        core = Panel(parent, "AI Core Overview")
        core.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=(0, 10))
        self.reactor = Reactor(core.body)
        self.reactor.pack(fill="both", expand=True)

    def _build_right(self, parent: tk.Misc) -> None:
        right = tk.Frame(parent, bg=theme.BACKGROUND)
        right.grid(row=0, column=2, sticky="nsew", pady=(0, 10))
        right.grid_rowconfigure(0, weight=3)
        right.grid_rowconfigure(1, weight=2)
        right.grid_columnconfigure(0, weight=1)
        feed = Panel(right, "Live intelligence feed", accent=theme.GREEN)
        feed.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        self.feed = tk.Text(feed.body, height=10, bg=theme.PANEL, fg=theme.TEXT, insertbackground=theme.CYAN, relief="flat", wrap="word", font=(theme.FONT, 9), state="disabled")
        self.feed.pack(fill="both", expand=True)
        self._add_feed("JARVIS tizimi ishga tushdi.", theme.GREEN)
        self._add_feed("AI modeli: " + ("Gemini ulangan" if self.ai else "lokal rejim"), theme.CYAN)
        self._add_feed("Buyruq kutilyapti...", theme.MUTED)
        self.task_panel = TaskPanel(right, self._approve_task, self._reject_task)
        self.task_panel.grid(row=1, column=0, sticky="nsew")
        self._refresh_tasks()

    def _build_bottom(self, parent: tk.Misc) -> None:
        lower = tk.Frame(parent, bg=theme.BACKGROUND)
        lower.grid(row=1, column=1, columnspan=2, sticky="nsew")
        lower.grid_columnconfigure(0, weight=1)
        lower.grid_columnconfigure(1, weight=1)
        lower.grid_columnconfigure(2, weight=1)
        monitor = Panel(lower, "System monitor")
        monitor.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.cpu_value = self._metric_label(monitor.body, "CPU", "Monitoring")
        self.ram_value = self._metric_label(monitor.body, "RAM", "—")
        self.disk_value = self._metric_label(monitor.body, "DISK", "—")

        routing = Panel(lower, "Task routing")
        routing.grid(row=0, column=1, sticky="nsew", padx=3)
        self.route_status = tk.Label(routing.body, text="Gemini Chat AI: tayyor", bg=theme.PANEL, fg=theme.GREEN, font=(theme.MONO, 9, "bold"))
        self.route_status.pack(anchor="w", pady=(8, 8))
        tk.Label(routing.body, text="Buyruqlar Gemini tomonidan tahlil qilinadi va mos agentga yuboriladi.", bg=theme.PANEL, fg=theme.MUTED, wraplength=220, justify="left", font=(theme.FONT, 9)).pack(anchor="w")
        GlowButton(routing.body, "AGENTLARNI BOSHQARISH", self._show_agents_section).pack(anchor="w", pady=(14, 0))
        # Agentlar dashboard'ga joylashtirilmaydi; holatni boshqaruvchi yashirin model.
        self.agent_panel = AgentPanel(self, self._select_agent)
        if self.ai:
            self.agent_panel.set_connected(self.active_connection.provider, True, f"ULANGAN • {self.ai.model}")

        quick = Panel(lower, "Quick commands")
        quick.grid(row=0, column=2, sticky="nsew", padx=(7, 0))
        for label, command in (("⌁  Vaqtni ayt", "soat nechchi"), ("▤  Eslatmalar", "eslatmalarim"), ("◉  Tizim holati", "Joriy tizim holatini qisqacha ayt")):
            GlowButton(quick.body, label, lambda value=command: self._send(value)).pack(fill="x", pady=4)

    def _metric_label(self, parent: tk.Misc, title: str, initial: str) -> tk.Label:
        box = tk.Frame(parent, bg=theme.PANEL_ALT, highlightbackground=theme.BORDER, highlightthickness=1)
        box.pack(side="left", fill="both", expand=True, padx=3, pady=4)
        tk.Label(box, text=title, bg=theme.PANEL_ALT, fg=theme.MUTED, font=(theme.MONO, 8, "bold")).pack(pady=(12, 2))
        label = tk.Label(box, text=initial, bg=theme.PANEL_ALT, fg=theme.CYAN, font=(theme.MONO, 12, "bold"))
        label.pack(pady=(0, 12))
        return label

    def _build_command_bar(self) -> None:
        bar = tk.Frame(self, bg=theme.PANEL, highlightbackground=theme.BORDER, highlightthickness=1)
        bar.pack(fill="x", padx=15, pady=(0, 14), ipady=7)
        tk.Label(bar, text="›_", bg=theme.PANEL, fg=theme.CYAN, font=(theme.MONO, 18, "bold")).pack(side="left", padx=(14, 7))
        self.prompt = tk.Entry(bar, bg=theme.PANEL, fg=theme.TEXT, insertbackground=theme.CYAN, relief="flat", font=(theme.FONT, 11))
        self.prompt.pack(side="left", fill="x", expand=True, ipady=8)
        self.prompt.insert(0, "JARVISga buyruq yoki savol yozing...")
        self.prompt.bind("<FocusIn>", self._clear_hint)
        self.prompt.bind("<Return>", lambda _event: self._send())
        GlowButton(bar, "YUBORISH  ›", self._send, padx=18, pady=7).pack(side="right", padx=10)
        self.prompt.focus_set()

    def _clear_hint(self, _event: tk.Event[tk.Misc]) -> None:
        if self.prompt.get() == "JARVISga buyruq yoki savol yozing...":
            self.prompt.delete(0, "end")

    def _send(self, message: str | None = None) -> None:
        message = message or self.prompt.get().strip()
        if not message or message == "JARVISga buyruq yoki savol yozing...":
            return
        self.prompt.delete(0, "end")
        planned = self.planner.plan(message)
        if planned:
            self._refresh_tasks()
            self._add_feed(f"TASK #{planned.id}: {planned.title}", theme.AMBER)
            self.reactor.set_state("idle", "TASK RUXSATINI KUTMOQDA" if planned.requires_approval else "VAZIFA REJALASHTIRILDI")
            return
        self.reactor.set_state("thinking", "SO'ROV TAHLIL QILINMOQDA")
        self.agent_panel.set_working("core", True)
        self._add_feed(f"> {message}", theme.CYAN)
        threading.Thread(target=self._reply, args=(message,), daemon=True).start()

    def _reply(self, message: str) -> None:
        local_prefixes = ("yordam", "help", "soat nechchi", "vaqt", "time", "eslatma ol:", "eslatmalarim", "eslatmalar", "notes")
        if self.ai and not message.casefold().startswith(local_prefixes):
            for attempt in range(3):
                try:
                    intent = self.ai.interpret(message)
                    intent = self._ground_theme_intent(message, intent)
                    music_fallback = self._local_intent(message)
                    if not intent.is_command and music_fallback and music_fallback.category == "media":
                        intent = music_fallback
                    if intent.is_command:
                        agent_key = {"browser": "browser", "computer": "desktop", "media": "music", "voice": "voice"}.get(intent.category, "automation")
                        assigned = self.connections.connection_for(agent_key)
                        if assigned and self.active_connection and assigned.id != self.active_connection.id:
                            try:
                                specialist = build_ai(assigned)
                                candidate = specialist.interpret(message) if specialist else None
                                allowed_for_agent = {
                                    "browser": BROWSER_ACTIONS | {"open_url", "search_web", "workflow"},
                                    "desktop": DESKTOP_ACTIONS | {"run_app", "workflow"},
                                    "music": {"play_music", "stop_music", "close_music", "resume_music", "next_music", "previous_music", "volume_up", "volume_down"},
                                    "voice": {"speak"},
                                }.get(agent_key, set())
                                if candidate and candidate.is_command and candidate.command in allowed_for_agent:
                                    intent = candidate
                                    self.events.put(("agent_note", f"{agent_key} agent buyruqni {assigned.label} bilan aniqlashtirdi."))
                            except AIError as error:
                                self.events.put(("agent_note", f"{agent_key} AI ulanishi javob bermadi: {error}. Default reja ishlatiladi."))
                    intent = self._ground_theme_intent(message, intent)
                    self.events.put(("intent", intent))
                    return
                except AIError as error:
                    if "(503)" in str(error) and attempt < 2:
                        time.sleep(2 ** attempt)
                        continue
                    fallback = self._local_intent(message)
                    if fallback:
                        self.events.put(("intent", fallback))
                    else:
                        self.events.put(("provider_error", str(error)))
                    return
            return
        response = self.agent.respond(message)
        self.events.put(("response", response.text))

    def _toggle_voice(self) -> None:
        self.voice_enabled = not self.voice_enabled
        self.voice_button.configure(text="🔊 OVOZ: ON" if self.voice_enabled else "🔇 OVOZ: OFF")
        self._add_feed("Voice Agent " + ("yoqildi." if self.voice_enabled else "o'chirildi."), theme.CYAN)

    @staticmethod
    def _ground_theme_intent(message: str, intent: AIIntent) -> AIIntent:
        """Replace a guessed RoboContest selector with its verified theme action."""
        lowered = message.casefold()
        if "robocontest" not in lowered or not any(word in lowered for word in ("mavzu", "tema", "theme")):
            return intent
        if "?" in message or "qanday" in lowered:
            return intent
        if any(word in lowered for word in ("to'q ko'k", "to‘q ko‘k", "dark", "qorong", "qora")):
            selected = "dark"
        elif any(word in lowered for word in ("light", "yorug", "oq rang")):
            selected = "light"
        else:
            return intent
        if intent.is_command and intent.command not in {"browser_click", "browser_set_theme"}:
            return intent
        target = json.dumps({"theme": selected}, ensure_ascii=False)
        return AIIntent("command", f"RoboContest mavzusi {selected} holatiga o'tkaziladi.", "browser", "browser_set_theme", target)

    def _local_intent(self, message: str) -> AIIntent | None:
        """Keeps common local commands usable during a temporary LLM outage."""
        lowered = message.casefold()
        if "qanday" not in lowered and "?" not in lowered:
            music_controls = (
                ("stop_music", ("qo'shiqni to'xtat", "qo‘shiqni to‘xtat", "musiqani to'xtat", "musiqani pauza", "stop music"), "Musiqa pauzaga qo'yiladi."),
                ("close_music", ("musiqani o'chir", "musiqani o‘chir", "qo'shiqni o'chir", "qo‘shiqni o‘chir", "musiqa oynasini yop"), "Musiqa oynasi yopiladi."),
                ("resume_music", ("musiqani davom ettir", "qo'shiqni davom ettir", "qo‘shiqni davom ettir", "musiqani qayta qo'y", "resume music"), "Musiqa davom ettiriladi."),
                ("next_music", ("keyingi qo'shiq", "keyingi qo‘shiq", "keyingi trek", "next song"), "Keyingi qo'shiqqa o'tiladi."),
                ("previous_music", ("oldingi qo'shiq", "oldingi qo‘shiq", "oldingisiga qayt", "oldingi trek", "previous song"), "Oldingi qo'shiqqa qaytiladi."),
                ("volume_up", ("ovozni ko'tar", "ovozni ko‘tar", "musiqa ovozini oshir", "volume up"), "Musiqa ovozi oshiriladi."),
                ("volume_down", ("ovozni pasaytir", "musiqa ovozini kamaytir", "volume down"), "Musiqa ovozi pasaytiriladi."),
            )
            for command, phrases, reply in music_controls:
                if any(phrase in lowered for phrase in phrases):
                    return AIIntent("command", reply, "media", command, "")
            if lowered.strip(" .!?\t\n") in {"to'xtat", "to‘xtat", "pauza", "pause"}:
                return AIIntent("command", "Musiqa pauzaga qo'yiladi.", "media", "stop_music", "")
            if lowered.strip(" .!?\t\n") in {"o'chir", "o‘chir", "yop"}:
                return AIIntent("command", "Musiqa oynasi yopiladi.", "media", "close_music", "")
        domain = re.search(r"(?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/\S*)?", message, re.IGNORECASE)
        if domain and any(word in lowered for word in ("och", "kiring", "kir", "open")):
            return AIIntent("command", "Gemini band, saytni lokal tahlilchi orqali ochish uchun task yaratdim.", "browser", "open_url", domain.group(0))
        if any(word in lowered for word in ("qidir", "izla", "search")):
            query = re.sub(r"\b(qidir|izla|search|internetda|google.?da|haqida)\b", "", message, flags=re.IGNORECASE).strip(" :.-")
            if query:
                return AIIntent("command", "Gemini band, qidiruv uchun task yaratdim.", "browser", "search_web", query)
        if any(word in lowered for word in ("qo'shiq", "qo‘shiq", "musiqa", "song", "music")) and any(word in lowered for word in ("qo'y", "qo‘", "play", "tingla")):
            title = re.sub(r"\b(qo'shiq|qo‘shiq|musiqa|song|music|qo'y|qo‘|play|tingla|ni|ni)\b", "", message, flags=re.IGNORECASE).strip(" :.-")
            return AIIntent("command", "Gemini band, musiqa uchun task yaratdim.", "media", "play_music", title or message)
        return None

    def _select_agent(self, agent_key: str) -> None:
        if agent_key in {"gemini", "openai", "groq", "openrouter"}:
            AIProviderConnectionDialog(self, agent_key, self._connect_ai_provider)
            return
        self._add_feed("Agent: " + agent_key + ". Bu agent talab qilingan task bajarilganda faollashadi.", theme.MUTED)

    def _show_agents_section(self) -> None:
        """Separate section for adding API connections and reviewing agent availability."""
        window = tk.Toplevel(self)
        window.title("JARVIS • Agentlar")
        window.configure(bg=theme.PANEL)
        window.geometry("560x620")
        body = tk.Frame(window, bg=theme.PANEL, padx=20, pady=18)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="AGENTLARNI QO'SHISH VA BOSHQARISH", bg=theme.PANEL, fg=theme.CYAN_SOFT, font=(theme.MONO, 13, "bold")).pack(anchor="w")
        tk.Label(body, text="AI Connections orqali bitta provayder uchun bir nechta API kalit qo'shishingiz mumkin.", bg=theme.PANEL, fg=theme.MUTED, font=(theme.FONT, 9)).pack(anchor="w", pady=(4, 12))
        GlowButton(body, "+ AI CONNECTION QO'SHISH", lambda: AIProviderConnectionDialog(window, "gemini", self._connect_ai_provider)).pack(anchor="w", pady=(0, 10))
        list_body = self._scrollable_body(body)
        for agent in AGENTS:
            provider = agent.key in {"gemini", "openai", "groq", "openrouter"}
            connected = any(item.provider == agent.key for item in self.connections.connections) if provider else agent.connected
            state = "ULANGAN" if connected else "ULANMAGAN"
            tk.Label(list_body, text=f"{'●' if state == 'ULANGAN' else '○'}  {agent.name:<18}  {state}  —  {agent.role}", bg=theme.PANEL_ALT, fg=theme.GREEN if state == "ULANGAN" else theme.MUTED, anchor="w", padx=10, pady=7, font=(theme.FONT, 9)).pack(fill="x", pady=2)

    def _show_assignments_section(self) -> None:
        """Separate section that binds enabled agents to a selected AI connection."""
        window = tk.Toplevel(self)
        window.title("JARVIS • Agent assignments")
        window.configure(bg=theme.PANEL)
        window.geometry("610x580")
        body = tk.Frame(window, bg=theme.PANEL, padx=20, pady=18)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="AGENT → AI BIRIKTIRISHLARI", bg=theme.PANEL, fg=theme.CYAN_SOFT, font=(theme.MONO, 13, "bold")).pack(anchor="w")
        tk.Label(body, text="Gemini default Chat AI bo'lib qoladi. Task turi aniqlangach mos agent shu yerda biriktirilgan AI bilan ishlaydi.", bg=theme.PANEL, fg=theme.MUTED, wraplength=560, justify="left", font=(theme.FONT, 9)).pack(anchor="w", pady=(4, 14))
        list_body = self._scrollable_body(body)
        choices = [("Default Gemini / Chat AI", "")] + [(f"{item.label} [{item.status}]", item.id) for item in self.connections.connections]
        variables: dict[str, tk.StringVar] = {}
        roles = [agent for agent in AGENTS if agent.key not in {"gemini", "openai", "groq", "openrouter"}]
        for agent in roles:
            row = tk.Frame(list_body, bg=theme.PANEL_ALT)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=agent.name, bg=theme.PANEL_ALT, fg=theme.TEXT, width=18, anchor="w", padx=8, pady=7, font=(theme.FONT, 9, "bold")).pack(side="left")
            current = self.connections.assignments.get(agent.key, "")
            label = next((text for text, key in choices if key == current), choices[0][0])
            value = tk.StringVar(value=label)
            variables[agent.key] = value
            tk.OptionMenu(row, value, *(text for text, _ in choices)).pack(side="right", padx=8, pady=4)
        def save_assignments() -> None:
            reverse = {text: key for text, key in choices}
            for agent_key, value in variables.items():
                self.connections.assign(agent_key, reverse[value.get()])
            self._add_feed("Agent → AI biriktirishlari saqlandi.", theme.GREEN)
            window.destroy()
        GlowButton(body, "BIRIKTIRISHLARNI SAQLASH", save_assignments).pack(anchor="e", pady=14)

    @staticmethod
    def _scrollable_body(parent: tk.Misc) -> tk.Frame:
        wrapper = tk.Frame(parent, bg=theme.PANEL)
        wrapper.pack(fill="both", expand=True)
        canvas = tk.Canvas(wrapper, bg=theme.PANEL, highlightthickness=0)
        scrollbar = tk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=theme.PANEL)
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        inner.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        return inner

    def _connect_ai_provider(self, provider: str, api_key: str, model: str) -> None:
        added = self.connections.add(provider, model, api_key)
        if provider == "gemini":
            self.connections.set_default(added.id)
        self.active_connection = self.connections.default_connection()
        self.ai = build_ai(self.active_connection)
        self.agent.ai = self.ai
        self.connection.configure(text=f"● {self.active_connection.provider.upper()} ONLINE", fg=theme.GREEN)
        self.agent_panel.set_connected(provider, True, f"ULANGAN • {model}")
        self._add_feed(f"{provider.title()} API kaliti qo'shildi: {model}", theme.GREEN)

    def _approve_task(self, task_id: int) -> None:
        task = self.tasks.update(task_id, RUNNING)
        self._refresh_tasks()
        self.agent_panel.set_working(task.agent_key, True)
        self.reactor.set_state("thinking", "TASDIQLANGAN AMAL BAJARILMOQDA")
        assigned = self.connections.connection_for(task.agent_key)
        if assigned:
            self._add_feed(f"{task.agent_key} agent → {assigned.label} bilan ishga tushdi.", theme.CYAN)
        status = "tasdiqlandi" if task.requires_approval else "ishga tushdi"
        self._add_feed(f"TASK #{task.id} {status}: {task.title}", theme.GREEN)
        threading.Thread(target=self._execute_task, args=(task,), daemon=True).start()

    def _execute_task(self, task: Task) -> None:
        try:
            action = "browser_open" if task.action == "open_url" else task.action
            result = execute_automation(action, task.payload) if action in BROWSER_ACTIONS | DESKTOP_ACTIONS | {"workflow"} else execute(task)
            self.events.put(("task_done", (task, COMPLETED, result)))
        except Exception as error:
            self.events.put(("task_done", (task, FAILED, str(error))))

    def _reject_task(self, task_id: int) -> None:
        task = self.tasks.update(task_id, REJECTED, "Foydalanuvchi ruxsat bermadi.")
        self._refresh_tasks()
        self._add_feed(f"TASK #{task.id} rad etildi: {task.title}", theme.MUTED)

    def _read_events(self) -> None:
        try:
            while True:
                kind, message = self.events.get_nowait()
                if kind == "response":
                    self.reactor.set_state("speaking", "JAVOB TAYYOR")
                    self.agent_panel.set_working("core", False)
                    self._add_feed("JARVIS: " + str(message), theme.GREEN)
                    if self.voice_enabled:
                        speak(str(message))
                    self.after(3300, lambda: self.reactor.set_state("idle", "TIZIM TAYYOR"))
                elif kind == "agent_note":
                    self._add_feed(str(message), theme.CYAN)
                elif kind == "intent":
                    intent = message
                    self.agent_panel.set_working("core", False)
                    self._add_feed("JARVIS: " + intent.reply, theme.GREEN)
                    if self.voice_enabled:
                        speak(intent.reply)
                    if intent.is_command:
                        if intent.command == "workflow":
                            task = self.tasks.create(f"Workflow: {intent.reply}", "automation", "workflow", intent.target)
                        elif intent.command in BROWSER_ACTIONS or intent.command in DESKTOP_ACTIONS:
                            agent_key = "browser" if intent.command in BROWSER_ACTIONS else "desktop"
                            task = self.tasks.create(f"{agent_key}: {intent.command} — {intent.target[:70]}", agent_key, intent.command, intent.target)
                        elif intent.command == "open_url":
                            task = self.tasks.create(f"Browser: {intent.target}", "browser", "browser_open", intent.target)
                        elif intent.command == "search_web":
                            address = "https://www.google.com/search?q=" + quote_plus(intent.target)
                            task = self.tasks.create(f"Browser qidiruvi: {intent.target}", "browser", "browser_open", address)
                        else:
                            agent_key = {"browser": "browser", "media": "music", "voice": "voice"}.get(intent.category, "automation")
                            task = self.planner.plan_ai_command(intent.command, intent.target, agent_key)
                        if task:
                            self._refresh_tasks()
                            if task.requires_approval:
                                self._add_feed(f"TASK #{task.id}: {task.title}", theme.AMBER)
                                self.reactor.set_state("idle", "TASK RUXSATINI KUTMOQDA")
                            else:
                                self._approve_task(task.id)
                        else:
                            self.reactor.set_state("speaking", "BUYRUQ ANIQLASHTIRILMOQDA")
                    else:
                        self.reactor.set_state("speaking", "JAVOB TAYYOR")
                        self.after(3300, lambda: self.reactor.set_state("idle", "TIZIM TAYYOR"))
                elif kind == "provider_error":
                    self.agent_panel.set_working("core", False)
                    error = str(message)
                    self._add_feed("AI API: " + error, theme.RED)
                    if self.active_connection:
                        self.connections.mark_error(self.active_connection.id, error)
                    if "(401)" in error or "(403)" in error:
                        if messagebox.askyesno("API kaliti yaroqsiz", "API kaliti yaroqsiz yoki muddati tugagan. Uni lokal ro'yxatdan o'chiraymi?"):
                            if self.active_connection:
                                self.connections.remove(self.active_connection.id)
                            self.active_connection = self.connections.default_connection()
                            self.ai = build_ai(self.active_connection)
                            self.agent.ai = self.ai
                            label = f"● {self.active_connection.provider.upper()} ONLINE" if self.ai else "● LOCAL MODE"
                            self.connection.configure(text=label, fg=theme.GREEN if self.ai else theme.AMBER)
                elif kind == "task_done":
                    task, status, result = message  # type: ignore[misc]
                    updated = self.tasks.update(task.id, status, result)
                    if task.action == "play_music":
                        self.lift()
                        self.focus_force()
                    self.agent_panel.set_working(updated.agent_key, False)
                    self._refresh_tasks()
                    self._add_feed(f"TASK #{updated.id} {status.lower()}: {result}", theme.GREEN if status == COMPLETED else theme.RED)
                    self.reactor.set_state("speaking", "AMAL YAKUNLANDI")
                    self.after(2500, lambda: self.reactor.set_state("idle", "TIZIM TAYYOR"))
        except queue.Empty:
            pass
        self.after(80, self._read_events)

    def _add_feed(self, message: str, color: str) -> None:
        timestamp = datetime.now().strftime("%H:%M")
        self.feed.configure(state="normal")
        self.feed.insert("end", f"[{timestamp}] {message}\n\n", (color,))
        self.feed.tag_configure(color, foreground=color)
        self.feed.see("end")
        self.feed.configure(state="disabled")

    def _refresh_tasks(self) -> None:
        self.task_panel.refresh(self.tasks.recent())

    def _tick(self) -> None:
        now = datetime.now()
        self.clock.configure(text=now.strftime("%A, %d %B  •  %H:%M:%S"))
        metrics = system_metrics()
        self.cpu_value.configure(text="ACTIVE")
        self.ram_value.configure(text=f"{metrics.memory_percent}%")
        self.disk_value.configure(text=f"{metrics.disk_percent}%")
        self.after(1000, self._tick)

    def _close(self) -> None:
        self.memory.close()
        self.tasks.close()
        browser.close()
        from jarvis.music import player
        player.close()
        self.destroy()


def main() -> None:
    JarvisApp().mainloop()


if __name__ == "__main__":
    main()
