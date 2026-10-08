from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from jarvis.automation import BrowserAutomation, DesktopAutomation, parse_target
from jarvis.intent import AIIntent
from jarvis.ui.app import JarvisApp


class FakeDriver:
    def __init__(self) -> None:
        self.opened: list[str] = []
        self.title = "Example"
        self.current_url = ""

    def get(self, url: str) -> None:
        self.opened.append(url)
        self.current_url = url


class BrowserAutomationTests(unittest.TestCase):
    def test_structured_target_is_preserved(self) -> None:
        self.assertEqual(parse_target('{"field":"Search","text":"Jarvis"}'), {"field": "Search", "text": "Jarvis"})

    def test_only_web_urls_are_opened(self) -> None:
        driver = FakeDriver()
        agent = BrowserAutomation()
        agent._get_driver = lambda: driver  # type: ignore[method-assign]
        self.assertIn("example.com", agent.execute("browser_open", {"url": "example.com"}))
        self.assertEqual(driver.opened, ["https://example.com"])
        with self.assertRaises(ValueError):
            agent.execute("browser_open", {"url": "file:///C:/secret.txt"})

    def test_browser_tab_controls(self) -> None:
        driver = MagicMock()
        driver.window_handles = ["first", "second"]
        driver.current_window_handle = "second"
        driver.title = "Example"
        driver.current_url = "https://example.com"
        agent = BrowserAutomation()
        agent.driver = driver
        agent._get_driver = lambda: driver  # type: ignore[method-assign]
        self.assertIn("1-tab", agent.execute("browser_switch_tab", {"index": 1}))
        driver.switch_to.window.assert_called_with("first")
        self.assertIn("Tab yopildi", agent.execute("browser_close_tab", {}))
        driver.close.assert_called_once()
        driver.switch_to.window.assert_called_with("first")

    def test_missing_css_selector_has_useful_error(self) -> None:
        driver = MagicMock()
        driver.find_elements.return_value = []
        driver.current_url = "https://robocontest.uz/"
        with self.assertRaisesRegex(ValueError, "AI taxmin qilgan CSS"):
            BrowserAutomation._find_element(driver, "css:.theme-toggle")

    def test_click_does_not_open_a_blank_browser_without_session(self) -> None:
        agent = BrowserAutomation()
        agent._get_driver = MagicMock()  # type: ignore[method-assign]
        with self.assertRaisesRegex(ValueError, "Avval saytni JARVIS orqali oching"):
            agent.execute("browser_click", {"element": "css:.theme-toggle"})
        agent._get_driver.assert_not_called()

    def test_robo_theme_intent_replaces_guessed_click(self) -> None:
        guessed = AIIntent("command", "Tugmani bosaman", "browser", "browser_click", '{"element":"css:.theme-toggle"}')
        repaired = JarvisApp._ground_theme_intent("robocontestda ochgan sahifangni mavzusini to'q ko'k qil", guessed)
        self.assertEqual(repaired.command, "browser_set_theme")
        self.assertEqual(parse_target(repaired.target), {"theme": "dark"})


class DesktopAutomationTests(unittest.TestCase):
    def test_hotkey_uses_allowlisted_keys(self) -> None:
        calls: list[tuple[str, ...]] = []
        fake_gui = types.SimpleNamespace(
            FAILSAFE=False, PAUSE=0, KEYBOARD_KEYS=["ctrl", "s"],
            hotkey=lambda *keys: calls.append(keys),
        )
        with patch.dict(sys.modules, {"pyautogui": fake_gui}):
            result = DesktopAutomation().execute("desktop_hotkey", {"keys": "ctrl+s"})
            self.assertIn("ctrl+s", result)
            with self.assertRaises(ValueError):
                DesktopAutomation().execute("desktop_hotkey", {"keys": "ctrl+unknown"})
        self.assertEqual(calls, [("ctrl", "s")])
        self.assertTrue(fake_gui.FAILSAFE)


if __name__ == "__main__":
    unittest.main()
