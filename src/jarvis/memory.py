from __future__ import annotations

import sqlite3
from pathlib import Path


class Memory:
    """Small local-first store. It can later be replaced without changing the agent."""

    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(database_path)
        self.connection.execute(
            """CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        self.connection.commit()

    def add_note(self, body: str) -> None:
        self.connection.execute("INSERT INTO notes (body) VALUES (?)", (body,))
        self.connection.commit()

    def list_notes(self) -> list[str]:
        rows = self.connection.execute(
            "SELECT body FROM notes ORDER BY id DESC"
        ).fetchall()
        return [row[0] for row in rows]

    def close(self) -> None:
        self.connection.close()
