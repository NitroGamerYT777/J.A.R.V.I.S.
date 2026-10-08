from __future__ import annotations

import os
import sqlite3
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.parse import quote_plus

PENDING_APPROVAL = "Tasdiq kutilmoqda"
PLANNED = "Rejalashtirilgan"
RUNNING = "Bajarilmoqda"
COMPLETED = "Bajarildi"
REJECTED = "Rad etildi"
FAILED = "Xatolik"


@dataclass(frozen=True)
class Task:
    id: int
    title: str
    agent_key: str
    action: str
    payload: str
    status: str
    requires_approval: bool
    created_at: str
    result: str = ""


class TaskStore:
    """Persistent audit trail for every proposed and executed computer action."""

    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database_path)
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY, title TEXT NOT NULL, agent_key TEXT NOT NULL,
                action TEXT NOT NULL, payload TEXT NOT NULL DEFAULT '', status TEXT NOT NULL,
                requires_approval INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                result TEXT NOT NULL DEFAULT ''
            )"""
        )
        self.connection.commit()

    def create(self, title: str, agent_key: str, action: str, payload: str = "", *, requires_approval: bool = True) -> Task:
        status = PENDING_APPROVAL if requires_approval else PLANNED
        cursor = self.connection.execute(
            "INSERT INTO tasks (title, agent_key, action, payload, status, requires_approval) VALUES (?, ?, ?, ?, ?, ?)",
            (title, agent_key, action, payload, status, requires_approval),
        )
        self.connection.commit()
        return self.get(cursor.lastrowid)

    def get(self, task_id: int) -> Task:
        row = self.connection.execute(
            "SELECT id, title, agent_key, action, payload, status, requires_approval, created_at, result FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if row is None:
            raise KeyError(task_id)
        return Task(*row[:6], bool(row[6]), *row[7:])

    def recent(self, limit: int = 30) -> list[Task]:
        rows = self.connection.execute(
            "SELECT id, title, agent_key, action, payload, status, requires_approval, created_at, result FROM tasks ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Task(*row[:6], bool(row[6]), *row[7:]) for row in rows]

    def update(self, task_id: int, status: str, result: str = "") -> Task:
        self.connection.execute("UPDATE tasks SET status = ?, result = ? WHERE id = ?", (status, result, task_id))
        self.connection.commit()
        return self.get(task_id)

    def close(self) -> None:
        self.connection.close()


class TaskPlanner:
    """Converts explicit local-action requests into reviewable task records."""

    def __init__(self, store: TaskStore) -> None:
        self.store = store

    def plan(self, message: str) -> Task | None:
        normalized = message.casefold().strip()
        if normalized.startswith("vazifa qo'sh:") or normalized.startswith("vazifa qo‘sh:"):
            title = message.split(":", 1)[1].strip()
            return self.store.create(title or "Nomsiz vazifa", "automation", "manual", requires_approval=False)
        if normalized.startswith("brauzerda och:") or normalized.startswith("brauzerda och "):
            address = message[len("brauzerda och"):].lstrip(": ").strip()
            candidate = address if "://" in address else "https://" + address
            if address and urlparse(candidate).netloc:
                return self.store.create(f"Brauzerda ochish: {candidate}", "browser", "browser_open", candidate)
        if normalized in {"loyiha papkasini och", "papkani och"}:
            return self.store.create("Loyiha papkasini ochish", "files", "open_folder", str(Path.cwd()))
        return None

    def plan_ai_command(self, command: str, target: str, agent_key: str = "automation") -> Task | None:
        """Turn only an allow-listed, validated LLM command into a reviewable task."""
        target = target.strip()
        if command == "open_url":
            address = target if "://" in target else "https://" + target
            if urlparse(address).netloc:
                return self.store.create(f"Brauzerda ochish: {address}", agent_key, "open_url", address)
        if command == "search_web" and target:
            address = "https://www.google.com/search?q=" + quote_plus(target)
            return self.store.create(f"Internetda qidirish: {target}", agent_key, "open_url", address)
        if command == "run_app" and target:
            return self.store.create(f"Ilovani ishga tushirish: {target}", agent_key, "run_app", target)
        if command == "play_music" and target:
            return self.store.create(f"Musiqani qidirib ijro qilish: {target}", "music", "play_music", target)
        music_controls = {
            "stop_music": "Musiqani pauzaga qo'yish",
            "close_music": "Musiqa oynasini yopish",
            "resume_music": "Musiqani davom ettirish",
            "next_music": "Keyingi qo'shiqqa o'tish",
            "previous_music": "Oldingi qo'shiqqa qaytish",
            "volume_up": "Musiqa ovozini ko'tarish",
            "volume_down": "Musiqa ovozini pasaytirish",
        }
        if command in music_controls:
            return self.store.create(music_controls[command], "music", command, "", requires_approval=False)
        if command == "speak" and target:
            return self.store.create("Ovozli xabarni aytish", "voice", "speak", target, requires_approval=False)
        return None


def execute(task: Task) -> str:
    """A small, auditable allow-list executed only after user approval."""
    if task.action == "open_url":
        webbrowser.open(task.payload, new=2)
        return "Brauzerga ochish so'rovi yuborildi."
    if task.action == "open_folder":
        os.startfile(task.payload)  # type: ignore[attr-defined]
        return "Loyiha papkasini ochish so'rovi yuborildi."
    if task.action == "manual":
        return "Vazifa ro'yxatga olindi."
    if task.action == "run_app":
        safe_apps = {
            "notepad": "notepad.exe", "bloknot": "notepad.exe",
            "calculator": "calc.exe", "kalkulyator": "calc.exe",
            "explorer": "explorer.exe", "fayl menejeri": "explorer.exe",
            "settings": "ms-settings:", "sozlamalar": "ms-settings:",
        }
        app = safe_apps.get(task.payload.casefold())
        if not app:
            raise ValueError("Bu ilova xavfsiz ruxsat ro'yxatida yo'q. Hozircha Notepad, Calculator, Explorer yoki Settings so'rang.")
        if app == "ms-settings:":
            os.startfile(app)  # type: ignore[attr-defined]
        else:
            import subprocess
            subprocess.Popen([app])
        return f"{task.payload} ishga tushirish so'rovi yuborildi."
    if task.action == "play_music":
        from jarvis.music import player
        return player.play(task.payload)
    if task.action == "stop_music":
        from jarvis.music import player
        return player.pause()
    if task.action == "close_music":
        from jarvis.music import player
        player.close()
        return "Musiqa va JARVIS fon Chrome oynasi yopildi."
    if task.action in {"resume_music", "next_music", "previous_music", "volume_up", "volume_down"}:
        from jarvis.music import player
        actions = {
            "resume_music": player.resume,
            "next_music": player.next,
            "previous_music": player.previous,
            "volume_up": player.volume_up,
            "volume_down": player.volume_down,
        }
        return actions[task.action]()
    if task.action == "speak":
        from jarvis.voice import speak
        speak(task.payload)
        return "Ovozli xabar fon rejimida aytilmoqda."
    raise ValueError(f"Ruxsat etilmagan amal: {task.action}")
