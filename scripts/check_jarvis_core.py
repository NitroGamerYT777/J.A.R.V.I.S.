"""Load both GLBs in Chrome/WebGL and save review images of the real geometry.

Start preview_jarvis_core.py first. No personal Chrome profile is used.
"""
from __future__ import annotations

import json
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[1]


def main():
    folder = ROOT / "assets" / "3d" / "previews"
    folder.mkdir(parents=True, exist_ok=True)
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--enable-unsafe-swiftshader")
    options.add_argument("--use-angle=swiftshader")
    options.add_argument("--hide-scrollbars")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    driver = webdriver.Chrome(options=options)
    try:
        driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
            "width":1200,"height":1000,"deviceScaleFactor":1,"mobile":False,
        })
        driver.get("http://127.0.0.1:8766/?capture=1&view=front")
        WebDriverWait(driver, 45).until(lambda d: d.execute_script("return !!(window.jarvisPreview?.ready || window.jarvisPreview?.error)"))
        assert driver.execute_script("return !window.jarvisPreview.error"), driver.execute_script("return window.jarvisPreview.error")
        report = driver.execute_script("return window.jarvisPreview.stats")
        for view in ("front", "angle", "side", "back"):
            driver.execute_script("jarvisPreview.setView(arguments[0]); jarvisPreview.renderAt(0);", view)
            # Wait for a completed presentation, rather than taking a half-frame.
            driver.execute_async_script("requestAnimationFrame(()=>requestAnimationFrame(arguments[0]));")
            driver.save_screenshot(str(folder / f"{view}.png"))
        motion = driver.execute_script("""
            jarvisPreview.renderAt(0);
            const parts=['OuterRing','InnerRing','Core'];
            const before=parts.map(n=>jarvisPreview.root.getObjectByName(n).quaternion.toArray());
            jarvisPreview.renderAt(5);
            const after=parts.map(n=>jarvisPreview.root.getObjectByName(n).quaternion.toArray());
            return {before,after};
        """)
        assert all(a != b for a, b in zip(motion["before"], motion["after"])), "A model part did not animate."
        driver.get("http://127.0.0.1:8766/?capture=1&model=animated")
        WebDriverWait(driver, 45).until(lambda d: d.execute_script("return !!window.jarvisPreview?.ready"))
        report["animationClips"] = driver.execute_script("return jarvisPreview.stats.animations")
        assert report["animationClips"] == ["Idle_24s"]
        for state in ("idle", "listening", "thinking", "speaking"):
            driver.execute_script("jarvisPreview.setState(arguments[0]); jarvisPreview.renderAt(4);", state)
        driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
            "width":1440,"height":1000,"deviceScaleFactor":1,"mobile":False,
        })
        driver.get("http://127.0.0.1:8766/")
        WebDriverWait(driver, 45).until(lambda d: d.execute_script("return !!window.jarvisPreview?.ready"))
        driver.find_element("id", "pause").click()
        driver.save_screenshot(str(folder / "interface.png"))
        report["browserErrors"] = [item["message"] for item in driver.get_log("browser")
                                   if item["level"] == "SEVERE" and "favicon.ico" not in item["message"]]
        assert not report["browserErrors"], report["browserErrors"]
        report["independentMotionVerified"] = True
        (folder / "verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
    except Exception:
        print(json.dumps(driver.get_log("browser"), indent=2))
        driver.save_screenshot(str(folder / "load-error.png"))
        raise
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
