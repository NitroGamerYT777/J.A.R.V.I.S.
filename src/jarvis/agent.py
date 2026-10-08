from __future__ import annotations

from datetime import datetime

from jarvis.memory import Memory
from jarvis.models import Response
from jarvis.llm import AIError, AIProvider


class Jarvis:
    """Routes deliberately small, predictable commands to trusted local skills."""

    def __init__(self, memory: Memory, ai: AIProvider | None = None) -> None:
        self.memory = memory
        self.ai = ai

    def respond(self, message: str) -> Response:
        command = message.strip()
        normalized = command.casefold()

        if normalized in {"chiqish", "exit", "quit"}:
            return Response("Xayr. Keyingi buyruqni kutaman.", should_exit=True)
        if normalized in {"yordam", "help"}:
            return Response(
                "Buyruqlar: yordam, soat nechchi, eslatma ol: <matn>, eslatmalarim, chiqish."
            )
        if normalized in {"soat nechchi", "vaqt", "time"}:
            now = datetime.now().astimezone()
            return Response(f"Hozir: {now:%Y-%m-%d %H:%M} ({now.tzname()}).")
        if normalized.startswith("eslatma ol:"):
            note = command.split(":", maxsplit=1)[1].strip()
            if not note:
                return Response("Eslatma matnini ham yozing.")
            self.memory.add_note(note)
            return Response("Eslatma saqlandi.")
        if normalized in {"eslatmalarim", "eslatmalar", "notes"}:
            notes = self.memory.list_notes()
            if not notes:
                return Response("Hali eslatmalar yo‘q.")
            return Response("Eslatmalar:\n" + "\n".join(f"- {note}" for note in notes))
        if self.ai is None:
            return Response(
                "AI hali ulanmagan. `.env.example`dan `.env` yarating, "
                "unga GEMINI_API_KEY yozing va qayta ishga tushiring."
            )
        try:
            return Response(self.ai.ask(command))
        except AIError as error:
            return Response(str(error))
