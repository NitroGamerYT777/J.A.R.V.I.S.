from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from jarvis.llm import GeminiAI, OpenAICompatibleAI


PROVIDER_DEFAULTS = {
    "gemini": ("Google Gemini", "gemini-3.6-flash"),
    "openai": ("OpenAI", "gpt-6-astra"),
    "groq": ("Groq", "openai/gpt-oss-20b"),
    "openrouter": ("OpenRouter", "~openai/gpt-latest"),
}


@dataclass
class Connection:
    id: str
    provider: str
    model: str
    api_key: str
    label: str
    status: str = "ready"
    last_error: str = ""


class ConnectionStore:
    """Local-only multi-key vault. `data/` is excluded from source control."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connections: list[Connection] = []
        self.default_id = ""
        self.assignments: dict[str, str] = {}
        self._load()
        self._migrate_legacy_env()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.connections = [Connection(**item) for item in data.get("connections", [])]
            self.default_id = str(data.get("default_id", ""))
            self.assignments = {str(key): str(value) for key, value in data.get("assignments", {}).items()}
        except (json.JSONDecodeError, TypeError, KeyError):
            self.connections = []

    def _migrate_legacy_env(self) -> None:
        if self.connections:
            return
        provider = os.environ.get("AI_PROVIDER", "gemini").strip().casefold()
        key = os.environ.get("AI_API_KEY", "").strip() or os.environ.get("GEMINI_API_KEY", "").strip()
        if key and key != "bu_yerga_kalitingizni_yozing":
            model = os.environ.get("AI_MODEL", "") or os.environ.get("GEMINI_MODEL", "") or PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["gemini"])[1]
            self.add(provider if provider in PROVIDER_DEFAULTS else "gemini", model, key, "Legacy default", make_default=True)

    def save(self) -> None:
        self.path.write_text(json.dumps({"connections": [asdict(item) for item in self.connections], "default_id": self.default_id, "assignments": self.assignments}, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, provider: str, model: str, api_key: str, label: str = "", *, make_default: bool = False) -> Connection:
        if provider not in PROVIDER_DEFAULTS:
            raise ValueError("Noma'lum AI provayderi.")
        name, default_model = PROVIDER_DEFAULTS[provider]
        connection = Connection(uuid.uuid4().hex, provider, model or default_model, api_key.strip(), label.strip() or f"{name} • {model or default_model}")
        self.connections.append(connection)
        # Gemini is preferred as the initial chat/triage model.
        if make_default or not self.default_id or provider == "gemini":
            self.default_id = connection.id
        self.save()
        return connection

    def remove(self, connection_id: str) -> None:
        self.connections = [item for item in self.connections if item.id != connection_id]
        if self.default_id == connection_id:
            gemini = next((item for item in self.connections if item.provider == "gemini"), None)
            self.default_id = gemini.id if gemini else (self.connections[0].id if self.connections else "")
        self.assignments = {agent: value for agent, value in self.assignments.items() if value != connection_id}
        self.save()

    def get(self, connection_id: str) -> Connection | None:
        return next((item for item in self.connections if item.id == connection_id), None)

    def default_connection(self) -> Connection | None:
        return self.get(self.default_id)

    def set_default(self, connection_id: str) -> None:
        if not self.get(connection_id):
            raise KeyError(connection_id)
        self.default_id = connection_id
        self.save()

    def assign(self, agent_key: str, connection_id: str) -> None:
        if connection_id and not self.get(connection_id):
            raise KeyError(connection_id)
        self.assignments[agent_key] = connection_id
        self.save()

    def connection_for(self, agent_key: str) -> Connection | None:
        return self.get(self.assignments.get(agent_key, "")) or self.default_connection()

    def mark_error(self, connection_id: str, error: str) -> None:
        connection = self.get(connection_id)
        if connection:
            connection.status = "invalid" if "(401)" in error or "(403)" in error else "error"
            connection.last_error = error
            self.save()


def build_ai(connection: Connection | None) -> GeminiAI | OpenAICompatibleAI | None:
    if connection is None or not connection.api_key:
        return None
    if connection.provider == "gemini":
        return GeminiAI(api_key=connection.api_key, model=connection.model)
    settings = {
        "openai": ("OpenAI", "https://api.openai.com/v1"),
        "groq": ("Groq", "https://api.groq.com/openai/v1"),
        "openrouter": ("OpenRouter", "https://openrouter.ai/api/v1"),
    }
    name, base_url = settings[connection.provider]
    return OpenAICompatibleAI(connection.api_key, connection.model, base_url, name)
