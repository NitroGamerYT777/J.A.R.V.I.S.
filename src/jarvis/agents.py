from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec


@dataclass(frozen=True)
class AgentProfile:
    key: str
    name: str
    role: str
    connected: bool
    color: str


AGENTS = (
    AgentProfile("core", "AI Core", "Suhbat va rejalashtirish", True, "#1fe1a0"),
    AgentProfile("memory", "Memory Agent", "Eslatmalar va xotira", True, "#19d9ed"),
    AgentProfile("system", "System Agent", "Tizim ko'rsatkichlari", True, "#ffc857"),
    AgentProfile("gemini", "Gemini API", "AI model provayderi", False, "#a88cff"),
    AgentProfile("openai", "OpenAI API", "GPT modellari", False, "#6ee7c8"),
    AgentProfile("groq", "Groq API", "Juda tez LLM inference", False, "#ff9f66"),
    AgentProfile("openrouter", "OpenRouter", "Ko'p modelga bitta ulanish", False, "#88b8ff"),
    AgentProfile("files", "File Agent", "Fayllar bilan ishlash", False, "#9e7bff"),
    AgentProfile("browser", "Browser Agent", "Veb sahifalarni ochish", find_spec("selenium") is not None, "#42b8ff"),
    AgentProfile("desktop", "Desktop Agent", "Ekran va klaviatura", find_spec("pyautogui") is not None and find_spec("pyperclip") is not None, "#42d9ff"),
    AgentProfile("automation", "Automation Agent", "Tasdiqlangan amallar", False, "#ff6680"),
    AgentProfile("music", "Music Agent", "Musiqa qidirish va ijro", find_spec("selenium") is not None, "#ff6fb7"),
    AgentProfile("voice", "Voice Agent", "JARVIS TTS ovozi", True, "#83f7ff"),
)


def get_agent(key: str) -> AgentProfile:
    return next(agent for agent in AGENTS if agent.key == key)
