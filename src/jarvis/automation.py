"""Approved browser and desktop actions for the JARVIS task queue.

The language model chooses a named action and parameters. This module alone
performs it, keeping the browser session and desktop controls auditable.
"""

from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlparse


BROWSER_ACTIONS = frozenset({
    "browser_open", "browser_click", "browser_type", "browser_press", "browser_read", "browser_set_theme",
    "browser_scroll", "browser_back", "browser_forward", "browser_screenshot",
    "browser_new_tab", "browser_switch_tab", "browser_close_tab", "browser_close",
})
DESKTOP_ACTIONS = frozenset({
    "desktop_click", "desktop_type", "desktop_hotkey", "desktop_press",
    "desktop_scroll", "desktop_move", "desktop_drag", "desktop_screenshot", "desktop_active_window", "desktop_focus", "desktop_launch",
})


def parse_target(value: str) -> dict[str, object]:
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {"value": value}
    return parsed if isinstance(parsed, dict) else {"value": value}


def _value(data: dict[str, object], key: str = "value") -> str:
    return str(data.get(key, "")).strip()


def _coordinate(data: dict[str, object], name: str) -> int:
    try:
        return int(data[name])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"'{name}' koordinatasi kerak.") from error


class BrowserAutomation:
    """A dedicated Selenium Chrome session; it does not attach to personal tabs."""

    def __init__(self, profile: Path = Path("data/browser_agent")) -> None:
        self.profile = profile
        self.driver = None
        self.lock = threading.RLock()

    def _get_driver(self):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        if self.driver is not None:
            try:
                _ = self.driver.window_handles
                return self.driver
            except Exception:
                self.driver = None
        self.profile.mkdir(parents=True, exist_ok=True)
        options = Options()
        options.add_argument(f"--user-data-dir={self.profile.resolve()}")
        options.add_argument("--no-first-run")
        options.add_argument("--disable-notifications")
        self.driver = webdriver.Chrome(options=options)
        self.driver.set_page_load_timeout(25)
        return self.driver

    def execute(self, action: str, data: dict[str, object]) -> str:
        with self.lock:
            if action == "browser_close":
                if self.driver is None:
                    return "Browser Agent sessiyasi ochiq emas."
                self.driver.quit()
                self.driver = None
                return "Browser Agent sessiyasi yopildi."
            address = None
            if action in {"browser_open", "browser_new_tab"}:
                raw_address = _value(data, "url") or _value(data)
                if raw_address:
                    address = self._web_url(raw_address)
                elif action == "browser_open":
                    raise ValueError("Sayt manzili kerak.")
            if action not in {"browser_open", "browser_new_tab", "browser_set_theme"}:
                if self.driver is not None:
                    try:
                        _ = self.driver.window_handles
                    except Exception:
                        self.driver = None
                if self.driver is None:
                    raise ValueError("JARVIS Browser Agent sahifasi ochiq emas. Avval saytni JARVIS orqali oching.")
            driver = self._get_driver()
            if action == "browser_new_tab":
                driver.switch_to.new_window("tab")
                if address:
                    driver.get(address)
                    return f"Yangi tab ochildi: {driver.title} — {driver.current_url}"
                return f"Yangi brauzer tab ochildi. Jami: {len(driver.window_handles)}"
            if action == "browser_switch_tab":
                handles = driver.window_handles
                raw_index = data.get("index")
                if raw_index is not None:
                    try:
                        index = int(raw_index) - 1
                    except (TypeError, ValueError) as error:
                        raise ValueError("Tab raqami butun son bo'lishi kerak.") from error
                    if not 0 <= index < len(handles):
                        raise ValueError(f"Tab raqami 1 dan {len(handles)} gacha bo'lishi kerak.")
                    driver.switch_to.window(handles[index])
                    return f"{index + 1}-tab: {driver.title} — {driver.current_url}"
                label = _value(data, "title") or _value(data)
                if not label:
                    raise ValueError("Tab raqami yoki sarlavhasi kerak.")
                current_handle = driver.current_window_handle
                for index, handle in enumerate(handles, 1):
                    driver.switch_to.window(handle)
                    if label.casefold() in driver.title.casefold():
                        return f"{index}-tab: {driver.title} — {driver.current_url}"
                driver.switch_to.window(current_handle)
                raise ValueError(f"'{label}' nomli tab topilmadi.")
            if action == "browser_close_tab":
                handles = driver.window_handles
                closing_handle = driver.current_window_handle
                driver.close()
                if len(handles) == 1:
                    try:
                        driver.quit()
                    except Exception:
                        pass  # Closing the last tab may have ended the session already.
                    self.driver = None
                    return "Oxirgi brauzer tab yopildi."
                driver.switch_to.window(next(handle for handle in handles if handle != closing_handle))
                return f"Tab yopildi. Qolgan tablar: {len(driver.window_handles)}"
            if action == "browser_open":
                assert address is not None
                driver.get(address)
                return f"Sahifa ochildi: {driver.title} — {driver.current_url}"
            if action == "browser_set_theme":
                return self._set_theme(driver, data)
            if action == "browser_click":
                label = _value(data, "element") or _value(data)
                element = self._find_element(driver, label)
                try:
                    element.click()
                except Exception as error:
                    raise ValueError(
                        f"'{label}' elementi ko'rindi, lekin bosib bo'lmadi. "
                        "U boshqa oyna ostida yoki ekrandan tashqarida bo'lishi mumkin."
                    ) from error
                return f"Sahifadagi '{label}' elementi bosildi. Hozir: {driver.current_url}"
            if action == "browser_type":
                field = _value(data, "field")
                typed = _value(data, "text")
                if not field or not typed:
                    raise ValueError("browser_type uchun target: {\"field\":\"...\",\"text\":\"...\"} kerak.")
                element = self._find_element(driver, field, inputs_only=True)
                element.click()
                element.clear()
                element.send_keys(typed)
                return f"'{field}' maydoniga matn yozildi."
            if action == "browser_press":
                from selenium.webdriver.common.keys import Keys

                keys = {
                    "enter": Keys.ENTER, "tab": Keys.TAB, "escape": Keys.ESCAPE,
                    "backspace": Keys.BACKSPACE, "delete": Keys.DELETE,
                    "up": Keys.ARROW_UP, "down": Keys.ARROW_DOWN,
                    "left": Keys.ARROW_LEFT, "right": Keys.ARROW_RIGHT,
                }
                key = (_value(data, "key") or _value(data)).casefold()
                if key not in keys:
                    raise ValueError("Brauzer klavishi ruxsat etilmagan.")
                label = _value(data, "element")
                element = self._find_element(driver, label) if label else driver.switch_to.active_element
                element.send_keys(keys[key])
                return f"Brauzerda {key} bosildi."
            if action == "browser_read":
                selector = _value(data, "selector")
                content = driver.find_element("css selector", selector).text if selector else driver.find_element("tag name", "body").text
                return f"{driver.title} ({driver.current_url})\n{content[:8000]}"
            if action == "browser_scroll":
                raw = _value(data, "direction") or _value(data) or "down"
                pixels = -600 if raw.casefold() in {"up", "yuqoriga"} else 600
                driver.execute_script("window.scrollBy(0, arguments[0]);", pixels)
                return "Sahifa yuqoriga surildi." if pixels < 0 else "Sahifa pastga surildi."
            if action == "browser_back":
                driver.back()
                return f"Oldingi sahifa: {driver.current_url}"
            if action == "browser_forward":
                driver.forward()
                return f"Keyingi sahifa: {driver.current_url}"
            if action == "browser_screenshot":
                path = self._screenshot_path("browser")
                driver.save_screenshot(str(path))
                return f"Brauzer skrinshoti saqlandi: {path.resolve()}"
            raise ValueError(f"Browser Agent noma'lum amal: {action}")

    @staticmethod
    def _web_url(address: str) -> str:
        if "://" in address and not re.match(r"^https?://", address, re.I):
            raise ValueError("Faqat http/https sayt manzili qabul qilinadi.")
        if not re.match(r"^https?://", address, re.I):
            address = "https://" + address
        parsed = urlparse(address)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or " " in address:
            raise ValueError("Faqat http/https sayt manzili qabul qilinadi.")
        return address

    @staticmethod
    def _set_theme(driver, data: dict[str, object]) -> str:
        """Set RoboContest's observed light/dark preference without blind toggling."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait

        requested = (_value(data, "theme") or _value(data)).casefold()
        if requested in {"dark", "to'q ko'k", "to‘q ko‘k", "qorong'i", "qorong‘i"}:
            desired = "dark"
        elif requested in {"light", "yorug'", "yorug‘", "oq"}:
            desired = "light"
        else:
            raise ValueError("Mavzu 'dark' yoki 'light' bo'lishi kerak.")

        original = driver.current_window_handle
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            host = urlparse(driver.current_url).hostname or ""
            if host == "robocontest.uz":
                break
        else:
            driver.switch_to.window(original)
            if driver.current_url not in {"about:blank", "data:,"}:
                driver.switch_to.new_window("tab")
            driver.get("https://robocontest.uz/")

        current = driver.execute_script("return localStorage.getItem('theme')")
        if current == desired:
            return f"RoboContest mavzusi allaqachon {desired}. Sahifa: {driver.current_url}"
        if current not in {"light", "dark"}:
            raise ValueError(f"RoboContest mavzu holati noma'lum ({current!r}); tugmani taxminan bosmadim.")

        viewport_width = driver.execute_script("return window.innerWidth")
        viewport_height = driver.execute_script("return window.innerHeight")
        controls = driver.find_elements(By.CSS_SELECTOR, "button[aria-pressed]")
        toggle = next((item for item in controls
                       if item.is_displayed()
                       and item.find_elements(By.CSS_SELECTOR, "svg.lucide-sun, svg.lucide-moon")
                       and item.rect["x"] >= 0 and item.rect["x"] < viewport_width
                       and item.rect["y"] >= 0 and item.rect["y"] < viewport_height), None)
        if toggle is None:
            raise ValueError("RoboContest mavzu tugmasi topilmadi; sayt interfeysi o'zgargan bo'lishi mumkin.")
        toggle.click()
        try:
            WebDriverWait(driver, 5).until(
                lambda session: session.execute_script("return localStorage.getItem('theme')") == desired
            )
        except Exception as error:
            raise RuntimeError("RoboContest mavzusi o'zgarganini tasdiqlab bo'lmadi.") from error
        return f"RoboContest mavzusi {desired} holatiga o'tkazildi. Sahifa: {driver.current_url}"

    @staticmethod
    def _find_element(driver, label: str, *, inputs_only: bool = False):
        from selenium.webdriver.common.by import By

        if not label:
            raise ValueError("Sahifadagi element nomini yozing.")
        if label.startswith("css:"):
            selector = label[4:].strip()
            try:
                matches = driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception as error:
                raise ValueError(f"CSS selektor yaroqsiz: {selector}") from error
            viewport_width = driver.execute_script("return window.innerWidth")
            visible = next((element for element in matches
                            if element.is_displayed()
                            and element.rect["x"] >= 0
                            and element.rect["x"] < viewport_width), None)
            if visible is None:
                raise ValueError(
                    f"Joriy sahifada ({driver.current_url}) '{selector}' elementi topilmadi. "
                    "AI taxmin qilgan CSS selektori eskirgan bo'lishi mumkin."
                )
            return visible
        selector = "input,textarea,[contenteditable='true']" if inputs_only else "button,a,input,textarea,select,[role='button'],[contenteditable='true']"
        candidates = driver.find_elements(By.CSS_SELECTOR, selector)[:300]
        needle = label.casefold()
        for exact in (True, False):
            for element in candidates:
                if not element.is_displayed():
                    continue
                names = [element.text, element.get_attribute("aria-label"), element.get_attribute("placeholder"), element.get_attribute("name"), element.get_attribute("title")]
                if any((str(name).casefold() == needle if exact else needle in str(name).casefold()) for name in names if name):
                    return element
        raise ValueError(f"Sahifada '{label}' elementi topilmadi. Sahifani o'qib, nomini aniqlang.")

    @staticmethod
    def _screenshot_path(prefix: str) -> Path:
        from datetime import datetime

        folder = Path("data/screenshots")
        folder.mkdir(parents=True, exist_ok=True)
        return folder / f"{prefix}-{datetime.now():%Y%m%d-%H%M%S-%f}.png"

    def close(self) -> None:
        with self.lock:
            if self.driver is not None:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self.driver = None


class DesktopAutomation:
    """Explicit foreground UI actions with PyAutoGUI's emergency corner stop."""

    lock = threading.RLock()

    def __init__(self) -> None:
        self.target_window_title = ""

    def execute(self, action: str, data: dict[str, object]) -> str:
        import pyautogui as gui

        gui.FAILSAFE = True
        gui.PAUSE = 0.1
        with self.lock:
            if action == "desktop_focus":
                title = _value(data, "title") or _value(data)
                if not title:
                    raise ValueError("Fokuslanadigan oyna nomini yozing.")
                # Newly launched applications need a moment to create a window.
                matches = []
                deadline = time.monotonic() + 5
                while not matches and time.monotonic() < deadline:
                    matches = gui.getWindowsWithTitle(title)
                    if not matches:
                        time.sleep(0.2)
                if not matches:
                    raise ValueError(f"'{title}' nomli oyna topilmadi.")
                matches[0].activate()
                self.target_window_title = matches[0].title
                return f"Faol oyna: {self.target_window_title}"
            if action == "desktop_launch":
                program = _value(data, "program") or _value(data)
                args = data.get("args", [])
                if not program or not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
                    raise ValueError("desktop_launch uchun program va args ro'yxati kerak.")
                subprocess.Popen([program, *args], shell=False)
                return f"{program} ishga tushirildi."
            if action in {"desktop_type", "desktop_hotkey", "desktop_press", "desktop_scroll"} and self.target_window_title:
                matches = gui.getWindowsWithTitle(self.target_window_title)
                if matches:
                    matches[0].activate()
            if action == "desktop_click":
                x, y = _coordinate(data, "x"), _coordinate(data, "y")
                self._check_point(gui, x, y)
                gui.click(x, y)
                return f"Ekranda ({x}, {y}) nuqta bosildi."
            if action == "desktop_move":
                x, y = _coordinate(data, "x"), _coordinate(data, "y")
                self._check_point(gui, x, y)
                gui.moveTo(x, y, duration=0.2)
                return f"Sichqoncha ({x}, {y}) nuqtaga o'tdi."
            if action == "desktop_drag":
                x, y = _coordinate(data, "x"), _coordinate(data, "y")
                self._check_point(gui, x, y)
                gui.dragTo(x, y, duration=0.5)
                return f"Obyekt ({x}, {y}) nuqtaga tortildi."
            if action == "desktop_type":
                typed = _value(data, "text") or _value(data)
                if not typed:
                    raise ValueError("Yoziladigan matn bo'sh.")
                import pyperclip

                previous = pyperclip.paste()
                try:
                    pyperclip.copy(typed)
                    gui.hotkey("ctrl", "v")
                finally:
                    pyperclip.copy(previous)
                return "Matn faol oynaga yozildi."
            if action == "desktop_hotkey":
                raw = _value(data, "keys") or _value(data)
                keys = [part.strip().casefold() for part in raw.split("+") if part.strip()]
                if not 2 <= len(keys) <= 4 or any(key not in gui.KEYBOARD_KEYS for key in keys):
                    raise ValueError("Klaviatura kombinatsiyasi yaroqsiz. Masalan: ctrl+s")
                gui.hotkey(*keys)
                return f"{'+'.join(keys)} klavishlari bosildi."
            if action == "desktop_press":
                key = (_value(data, "key") or _value(data)).casefold()
                if key not in gui.KEYBOARD_KEYS:
                    raise ValueError("Klaviatura tugmasi yaroqsiz.")
                gui.press(key)
                return f"{key} klavishi bosildi."
            if action == "desktop_scroll":
                direction = (_value(data, "direction") or _value(data)).casefold()
                count = -5 if direction in {"down", "pastga"} else 5
                gui.scroll(count)
                return "Ekran pastga surildi." if count < 0 else "Ekran yuqoriga surildi."
            if action == "desktop_screenshot":
                path = BrowserAutomation._screenshot_path("desktop")
                gui.screenshot().save(path)
                return f"Ekran surati saqlandi: {path.resolve()}"
            if action == "desktop_active_window":
                window = gui.getActiveWindow()
                return f"Faol oyna: {window.title if window else 'aniqlanmadi'}"
            raise ValueError(f"Desktop Agent noma'lum amal: {action}")

    @staticmethod
    def _check_point(gui, x: int, y: int) -> None:
        width, height = gui.size()
        if not 0 <= x < width or not 0 <= y < height:
            raise ValueError(f"Koordinata ekran tashqarisida: {x}, {y}. Ekran: {width}×{height}.")


browser = BrowserAutomation()
desktop = DesktopAutomation()


def execute_automation(action: str, payload: str) -> str:
    if action == "workflow":
        try:
            steps = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ValueError("Workflow JSON shaklida bo'lishi kerak.") from error
        if not isinstance(steps, list) or not 1 <= len(steps) <= 8:
            raise ValueError("Workflow 1 tadan 8 tagacha amalni o'z ichiga olishi kerak.")
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                raise ValueError(f"{index}-amal noto'g'ri shaklda.")
            name = step.get("action")
            target = step.get("target", {})
            if name not in BROWSER_ACTIONS | DESKTOP_ACTIONS or not isinstance(target, (dict, str)):
                raise ValueError(f"{index}-amal ruxsat etilmagan: {name}")
        results = []
        for index, step in enumerate(steps, start=1):
            name = step["action"]
            target = step.get("target", {})
            encoded = json.dumps(target, ensure_ascii=False) if isinstance(target, dict) else target
            try:
                results.append(execute_automation(str(name), encoded))
            except Exception as error:
                raise RuntimeError(f"Workflow {index}-amalda to'xtadi: {error}") from error
        return "\n".join(f"{index}. {result}" for index, result in enumerate(results, start=1))
    data = parse_target(payload)
    if action in BROWSER_ACTIONS:
        return browser.execute(action, data)
    if action in DESKTOP_ACTIONS:
        return desktop.execute(action, data)
    raise ValueError(f"Ruxsat etilmagan avtomatlashtirish amali: {action}")
