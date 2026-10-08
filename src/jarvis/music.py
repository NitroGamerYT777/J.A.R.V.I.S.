from __future__ import annotations

import re
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

@dataclass(frozen=True)
class Video:
    id: str
    title: str


class YouTubeBackgroundPlayer:
    """Play YouTube in a private, minimized Chrome window controlled by Selenium."""

    def __init__(self) -> None:
        self._driver = None
        self._profile = Path("data/music_agent_profile")
        self._lock = threading.RLock()
        self._videos: list[Video] = []
        self._index = -1
        self._volume = 0.7

    def play(self, query: str) -> str:
        try:
            videos = self._find_videos(query)
        except RuntimeError:
            # YouTube occasionally changes its search responses; search in the
            # controlled browser if yt-dlp cannot extract search results.
            with self._lock:
                videos = self._find_videos_in_browser(query)
        with self._lock:
            self._play_video(videos[0])
            self._videos = videos
            self._index = 0
            return f"YouTube'da ijro etilmoqda: {videos[0].title}. Player fon oynasida."

    def pause(self) -> str:
        with self._lock:
            driver = self._active_driver()
            if driver is None or not self._videos:
                return "Hozir JARVIS ijro etayotgan musiqa yo'q."
            paused = driver.execute_script(
                "const v=document.querySelector('video.html5-main-video, video');"
                "if(!v) return null; v.pause(); return v.paused;"
            )
            if paused is not True:
                raise RuntimeError("YouTube videosini pauzaga qo'yib bo'lmadi.")
            return "Musiqa pauzaga qo'yildi. 'Musiqani davom ettir' deb qayta boshlang."

    def stop(self) -> str:
        """Keep the old command name while preserving the tab for resume."""
        return self.pause()

    def resume(self) -> str:
        with self._lock:
            self._start_video(self._require_driver())
            return "Musiqa davom ettirildi."

    def next(self) -> str:
        with self._lock:
            if not self._videos:
                return "Keyingi qo'shiq yo'q. Avval qo'shiqni qo'ying."
            if self._index + 1 >= len(self._videos):
                return "Qidiruvdagi oxirgi qo'shiqqa yetdingiz. Yangi qo'shiq nomini ayting."
            index = self._index + 1
            self._play_video(self._videos[index])
            self._index = index
            return f"Keyingi qo'shiq: {self._videos[index].title}."

    def previous(self) -> str:
        with self._lock:
            if not self._videos:
                return "Oldingi qo'shiq yo'q. Avval qo'shiqni qo'ying."
            index = max(0, self._index - 1)
            self._play_video(self._videos[index])
            self._index = index
            return f"Oldingi qo'shiq: {self._videos[index].title}."

    def volume_up(self) -> str:
        return self._change_volume(0.1)

    def volume_down(self) -> str:
        return self._change_volume(-0.1)

    def _change_volume(self, delta: float) -> str:
        with self._lock:
            driver = self._require_driver()
            volume = round(min(1.0, max(0.0, self._volume + delta)), 2)
            actual = driver.execute_script(
                "const v=document.querySelector('video.html5-main-video, video');"
                "if(!v) return null; v.volume=arguments[0]; v.muted=false; return v.volume;",
                volume,
            )
            if actual is None:
                raise RuntimeError("YouTube video elementi topilmadi; ovozni o'zgartirib bo'lmadi.")
            self._volume = float(actual)
            return f"Musiqa ovozi: {round(self._volume * 100)}%."

    def close(self) -> None:
        """Close only this player's Chrome window, not the user's Chrome."""
        with self._lock:
            driver, self._driver = self._driver, None
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
            self._videos = []
            self._index = -1

    def _play_video(self, video: Video) -> None:
        driver = self._ensure_driver()
        # A normal watch page avoids embedded-player error 153 (missing Referer).
        url = "https://www.youtube.com/watch?" + urlencode({"v": video.id, "autoplay": "1"})
        try:
            driver.get(url)
            driver.minimize_window()
            # Start and verify playback only after Chrome is minimized. A video
            # that advances in the foreground may otherwise stall in the back.
            self._start_video(driver)
        except Exception as error:
            raise RuntimeError(
                "YouTube ijrosi boshlanmadi. Internet, Chrome va YouTube sahifasini tekshiring. "
                f"Tafsilot: {str(error)[:180]}"
            ) from error

    def _start_video(self, driver: object) -> None:
        from selenium.webdriver.support.ui import WebDriverWait

        wait = WebDriverWait(driver, 45)
        try:
            wait.until(lambda session: session.execute_script(
                "const v=document.querySelector('video.html5-main-video, video');"
                "return !!v && v.readyState >= 2;"
            ))
        except Exception as error:
            raise RuntimeError(
                f"YouTube video 45 soniyada yuklanmadi (sahifa: {driver.title}). "
                "Internetni yoki YouTube talab qilayotgan login/rozilik oynasini tekshiring."
            ) from error
        # Explicit play() works in the minimized browser because our dedicated
        # Chrome profile has the no-user-gesture autoplay policy.
        result = driver.execute_async_script(
            "const done=arguments[arguments.length-1];"
            "const v=document.querySelector('video.html5-main-video, video');"
            "if(!v){done('video_not_found');return;}"
            "v.muted=false;v.volume=arguments[0];"
            "Promise.resolve(v.play()).then(()=>done('ok')).catch(e=>done(String(e)));",
            self._volume,
        )
        if result != "ok":
            raise RuntimeError(f"Brauzer ijroga ruxsat bermadi: {result}")
        start_time = driver.execute_script(
            "const v=document.querySelector('video.html5-main-video, video'); return v.currentTime;"
        )
        try:
            wait.until(lambda session: session.execute_script(
                "const v=document.querySelector('video.html5-main-video, video');"
                "return !!v && !v.paused && !v.muted && v.volume > 0 && v.currentTime > arguments[0] + 0.2;",
                start_time,
            ))
        except Exception as error:
            raise RuntimeError("YouTube video vaqt chizig'i yurmayapti; ijro boshlanmadi.") from error

    def _active_driver(self):
        if self._driver is None:
            return None
        try:
            _ = self._driver.current_window_handle
        except Exception:
            self._driver = None
            return None
        return self._driver

    def _require_driver(self):
        driver = self._active_driver()
        if driver is None or not self._videos:
            raise RuntimeError("Hozir JARVIS boshqarayotgan musiqa yo'q. Avval qo'shiqni qo'ying.")
        return driver

    def _ensure_driver(self):
        driver = self._active_driver()
        if driver is not None:
            return driver
        chrome = self._find_chrome()
        if chrome is None:
            raise RuntimeError("Google Chrome topilmadi. Chrome o'rnatilganini tekshiring.")
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service

        data_directory = Path.cwd() / "data"
        data_directory.mkdir(parents=True, exist_ok=True)
        self._profile = data_directory / "music_agent_profile"
        self._profile.mkdir(parents=True, exist_ok=True)
        options = webdriver.ChromeOptions()
        options.binary_location = str(chrome)
        for flag in (
            f"--user-data-dir={self._profile.resolve()}",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-minimized",
            "--autoplay-policy=no-user-gesture-required",
            "--disable-background-media-suspend",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
        ):
            options.add_argument(flag)
        service = Service()
        service.creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        driver = None
        try:
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(30)
            driver.set_script_timeout(15)
            # YouTube can gate playback on document focus. Emulate focus for
            # this tab without activating Chrome's window on the desktop.
            try:
                driver.execute_cdp_cmd("Emulation.setFocusEmulationEnabled", {"enabled": True})
            except Exception:
                pass  # Experimental CDP command is absent on some Chrome builds.
            driver.minimize_window()
        except Exception as error:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
            raise RuntimeError(
                "Chrome avtomatlashtirish ishga tushmadi. Chrome va Selenium o'rnatilganini tekshiring. "
                f"Tafsilot: {str(error)[:180]}"
            ) from error
        self._driver = driver
        return driver

    @staticmethod
    def _find_videos(query: str) -> list[Video]:
        query = query.strip()
        if not query:
            raise ValueError("Ijro qilinadigan qo'shiq nomini kiriting.")
        try:
            from yt_dlp import YoutubeDL
        except ImportError as error:
            raise RuntimeError("YouTube qidiruvi uchun yt-dlp o'rnatilmagan.") from error
        try:
            with YoutubeDL({"quiet": True, "no_warnings": True, "extract_flat": True,
                            "skip_download": True, "socket_timeout": 15}) as ydl:
                results = ydl.extract_info(f"ytsearch8:{query}", download=False)
        except Exception as error:
            raise RuntimeError("YouTube qidiruvi ishlamadi. Internetni tekshiring yoki keyinroq urinib ko'ring.") from error
        entries = results.get("entries", []) if isinstance(results, dict) else []
        videos = [Video(str(item["id"]), str(item.get("title") or query)) for item in entries
                  if isinstance(item, dict) and re.fullmatch(r"[A-Za-z0-9_-]{11}", str(item.get("id", "")))]
        if not videos:
            raise RuntimeError("YouTube'da ijro qilinadigan video topilmadi.")
        return videos

    def _find_videos_in_browser(self, query: str) -> list[Video]:
        from selenium.webdriver.support.ui import WebDriverWait

        driver = self._ensure_driver()
        try:
            driver.get("https://www.youtube.com/results?" + urlencode({"search_query": query}))
            anchors = WebDriverWait(driver, 20).until(
                lambda session: session.find_elements("css selector", "a#video-title[href*='watch']")
            )
            videos: list[Video] = []
            seen: set[str] = set()
            for anchor in anchors:
                address = anchor.get_attribute("href") or ""
                video_id = parse_qs(urlparse(address).query).get("v", [""])[0]
                if re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) and video_id not in seen:
                    seen.add(video_id)
                    videos.append(Video(video_id, anchor.get_attribute("title") or anchor.text or query))
                if len(videos) >= 8:
                    break
            if not videos:
                raise RuntimeError("YouTube qidiruvida ijro qilinadigan video topilmadi.")
            return videos
        except Exception as error:
            raise RuntimeError("YouTube qidiruvi fon Chrome oynasida ham ishlamadi.") from error
        finally:
            try:
                driver.minimize_window()
            except Exception:
                pass

    @staticmethod
    def _find_chrome() -> Path | None:
        discovered = shutil.which("chrome") or shutil.which("chrome.exe")
        if discovered:
            return Path(discovered)
        candidates = (
            Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe",
            Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
            Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        )
        return next((path for path in candidates if path.is_file()), None)


player = YouTubeBackgroundPlayer()
