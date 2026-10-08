from __future__ import annotations

from pathlib import Path

from jarvis.agent import Jarvis
from jarvis.config import load_local_env
from jarvis.llm import ai_from_environment
from jarvis.memory import Memory


def main() -> None:
    load_local_env()
    memory = Memory(Path("data") / "jarvis.db")
    ai = ai_from_environment()
    jarvis = Jarvis(memory, ai=ai)
    status = "AI ulangan." if ai else "AI kaliti topilmadi — lokal buyruqlar rejimi."
    print(f"JARVIS tayyor. {status} `yordam` deb yozing.")
    try:
        while True:
            response = jarvis.respond(input("Siz > "))
            print(f"JARVIS > {response.text}")
            if response.should_exit:
                break
    except (EOFError, KeyboardInterrupt):
        print("\nXayr.")
    finally:
        memory.close()


if __name__ == "__main__":
    main()
