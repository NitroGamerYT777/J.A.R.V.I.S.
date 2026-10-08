from __future__ import annotations

import tempfile
import queue
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from jarvis.intent import AIIntent
from jarvis.music import Video, YouTubeBackgroundPlayer
from jarvis.tasks import TaskPlanner, TaskStore, execute
from jarvis.ui.app import JarvisApp


class FakeDriver:
    current_window_handle = "jarvis-player"

    def __init__(self) -> None:
        self.urls: list[str] = []
        self.minimized = False
        self.paused = False
        self.volume = 0.7
        self.quit_called = False

    def get(self, url: str) -> None:
        self.urls.append(url)

    def minimize_window(self) -> None:
        self.minimized = True

    def execute_script(self, script: str, *args):
        if "v.pause()" in script:
            self.paused = True
            return True
        if "v.volume=arguments[0]" in script:
            self.volume = args[0]
            return self.volume
        return None

    def quit(self) -> None:
        self.quit_called = True


class MusicControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.player = YouTubeBackgroundPlayer()
        self.driver = FakeDriver()
        self.player._driver = self.driver
        self.player._find_videos = lambda _query: [Video("aaaaaaaaaaa", "First"), Video("bbbbbbbbbbb", "Second")]
        self.player._start_video = lambda _driver: None

    def test_play_pause_resume_next_previous_and_volume(self) -> None:
        self.player._start_video = lambda _driver: self.assertTrue(self.driver.minimized)
        self.assertIn("First", self.player.play("some song"))
        self.assertIn("youtube.com/watch", self.driver.urls[0])
        self.assertIn("v=aaaaaaaaaaa", self.driver.urls[0])
        self.assertTrue(self.driver.minimized)

        self.assertIn("pauzaga", self.player.stop())
        self.assertTrue(self.driver.paused)
        self.assertFalse(self.driver.quit_called)
        self.assertIn("davom", self.player.resume())

        self.assertIn("Second", self.player.next())
        self.assertIn("v=bbbbbbbbbbb", self.driver.urls[-1])
        self.assertIn("First", self.player.previous())
        self.assertIn("v=aaaaaaaaaaa", self.driver.urls[-1])

        self.assertIn("80%", self.player.volume_up())
        self.assertIn("70%", self.player.volume_down())
        self.assertFalse(self.driver.quit_called)

    def test_search_falls_back_to_private_browser(self) -> None:
        self.player._find_videos = lambda _query: (_ for _ in ()).throw(RuntimeError("search changed"))
        self.player._find_videos_in_browser = lambda _query: [Video("ccccccccccc", "Fallback")]
        self.assertIn("Fallback", self.player.play("some song"))
        self.assertIn("v=ccccccccccc", self.driver.urls[-1])

    def test_targetless_music_commands_are_planned_and_executed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory) / "tasks.db")
            planner = TaskPlanner(store)
            try:
                for command, method in (
                    ("stop_music", "pause"), ("resume_music", "resume"),
                    ("next_music", "next"), ("previous_music", "previous"),
                    ("volume_up", "volume_up"), ("volume_down", "volume_down"),
                ):
                    intent = AIIntent("command", "OK", "media", command, "")
                    self.assertTrue(intent.is_command, command)
                    task = planner.plan_ai_command(command, "")
                    self.assertIsNotNone(task)
                    self.assertFalse(task.requires_approval)
                    with patch("jarvis.music.player") as music_player:
                        getattr(music_player, method).return_value = "done"
                        self.assertEqual(execute(task), "done")
                        getattr(music_player, method).assert_called_once_with()
            finally:
                store.close()

    def test_music_phrases_have_a_local_outage_fallback(self) -> None:
        for phrase, expected in (
            ("musiqani to'xtat", "stop_music"),
            ("to'xtat", "stop_music"),
            ("musiqani o'chir", "close_music"),
            ("keyingi qo'shiq", "next_music"),
            ("ovozni pasaytir", "volume_down"),
        ):
            intent = JarvisApp._local_intent(None, phrase)
            self.assertIsNotNone(intent)
            self.assertEqual(intent.command, expected)

    def test_close_music_only_closes_owned_player(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory) / "tasks.db")
            try:
                task = TaskPlanner(store).plan_ai_command("close_music", "")
                self.assertIsNotNone(task)
                self.assertFalse(task.requires_approval)
                with patch("jarvis.music.player") as music_player:
                    self.assertIn("yopildi", execute(task))
                    music_player.close.assert_called_once_with()
            finally:
                store.close()

    def test_ui_starts_pause_without_approval_click(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TaskStore(Path(directory) / "tasks.db")
            try:
                app = MagicMock()
                app.tasks = store
                app.planner = TaskPlanner(store)
                app.events = queue.Queue()
                app.events.put(("intent", AIIntent("command", "Pauza", "media", "stop_music", "")))
                app.voice_enabled = False
                JarvisApp._read_events(app)
                app._approve_task.assert_called_once_with(1)
                self.assertFalse(store.get(1).requires_approval)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
