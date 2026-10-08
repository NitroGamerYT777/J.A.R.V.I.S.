from __future__ import annotations

from dataclasses import dataclass

from jarvis.automation import BROWSER_ACTIONS, DESKTOP_ACTIONS


ALLOWED_COMMANDS = frozenset({
    "open_url", "search_web", "run_app", "play_music", "stop_music", "close_music",
    "resume_music", "next_music", "previous_music", "volume_up", "volume_down", "speak", "workflow",
}) | BROWSER_ACTIONS | DESKTOP_ACTIONS
TARGETLESS_COMMANDS = frozenset({
    "stop_music", "close_music", "resume_music", "next_music", "previous_music", "volume_up", "volume_down",
    "browser_read", "browser_back", "browser_forward", "browser_screenshot",
    "browser_new_tab", "browser_close_tab", "browser_close",
    "desktop_screenshot", "desktop_active_window",
})


@dataclass(frozen=True)
class AIIntent:
    """Validated model output; raw model JSON is never executed directly."""

    kind: str
    reply: str
    category: str = "question"
    command: str = ""
    target: str = ""

    @property
    def is_command(self) -> bool:
        return (self.kind == "command" and self.command in ALLOWED_COMMANDS
                and (self.command in TARGETLESS_COMMANDS or bool(self.target.strip())))
