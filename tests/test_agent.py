from pathlib import Path

from jarvis.agent import Jarvis
from jarvis.memory import Memory


def test_add_and_list_note(tmp_path: Path) -> None:
    memory = Memory(tmp_path / "test.db")
    jarvis = Jarvis(memory)
    try:
        assert jarvis.respond("eslatma ol: Uchrashuv 15:00 da").text == "Eslatma saqlandi."
        assert "Uchrashuv 15:00 da" in jarvis.respond("eslatmalarim").text
    finally:
        memory.close()


def test_exit() -> None:
    memory = Memory(Path(":memory:"))
    try:
        assert Jarvis(memory).respond("chiqish").should_exit is True
    finally:
        memory.close()


class FakeAI:
    def ask(self, message: str) -> str:
        return f"AI: {message}"


def test_unknown_command_goes_to_ai(tmp_path: Path) -> None:
    memory = Memory(tmp_path / "test.db")
    try:
        assert Jarvis(memory, ai=FakeAI()).respond("salom").text == "AI: salom"
    finally:
        memory.close()
