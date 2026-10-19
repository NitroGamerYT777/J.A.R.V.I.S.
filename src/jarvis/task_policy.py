"""Conservative local risk rules; an LLM cannot declare its own action safe."""
from __future__ import annotations

import json
import re
from pathlib import Path, PureWindowsPath
from urllib.parse import unquote_plus, urlparse

from jarvis.automation import BROWSER_ACTIONS, DESKTOP_ACTIONS


def _normalized(value: object) -> str:
    return str(value).casefold().replace("‘", "'").replace("’", "'").replace("ʻ", "'")


def _data(payload: str) -> dict:
    try:
        value = json.loads(payload)
    except (ValueError, TypeError):
        return {"value": payload}
    return value if isinstance(value, dict) else {"value": payload}


def _important(value: object) -> bool:
    return bool(re.search(
        r"\b(delete|remove|erase|format|send|submit|publish|post|upload|buy|purchase|pay|checkout|"
        r"transfer|install|uninstall|shutdown|restart|password|permission|confirm|authorize|"
        r"o'chir\w*|ochir\w*|yubor\w*|jo'nat\w*|jonat\w*|to'la\w*|tolov\w*|"
        r"sotib|tasdiq\w*|o'rnat\w*|parol\w*|удал\w*|отправ\w*|оплат\w*|купить)\b",
        _normalized(value)))


def approval_reason(action: str, payload: str = "", *, _depth: int = 0) -> str:
    """Empty means automatic. Unknown/opaque actions require review, not guesses."""
    if not isinstance(action, str):
        return "Amal nomi noto'g'ri shaklda."
    data = _data(payload)
    value = lambda key: str(data.get(key, data.get("value", ""))).strip()
    if action in {"office_create", "office_convert"}:
        from jarvis.office.service import validate_request
        try:
            request = validate_request(action, data)
        except (ValueError, TypeError):
            return "Office topshirig'ining parametrlari tekshirilishi kerak."
        if action == "office_create" and request.get("source"):
            return "Tanlangan manba fayldan 24000 belgigacha matn Office agentiga ulangan AI provayderiga yuboriladi: " + request["source"]
        return ""
    if action == "workflow":
        if _depth >= 2:
            return "Ichma-ich workflow tekshirilishi kerak."
        try:
            steps = json.loads(payload)
        except (ValueError, TypeError):
            return "Workflow shakli tekshirilishi kerak."
        if not isinstance(steps, list) or not 1 <= len(steps) <= 8:
            return "Workflow 1–8 ta amaldan iborat bo'lishi kerak."
        for index, step in enumerate(steps, 1):
            if not isinstance(step, dict) or not isinstance(step.get("target", {}), (dict, str)):
                return f"{index}-qadam tushunarsiz."
            if not isinstance(step.get("action"), str) or step["action"] not in BROWSER_ACTIONS | DESKTOP_ACTIONS:
                return f"{index}-qadam ruxsat etilgan avtomatlashtirish amali emas."
            target = step.get("target", {})
            reason = approval_reason(step.get("action", ""), json.dumps(target) if isinstance(target, dict) else target, _depth=_depth + 1)
            if reason:
                return f"{index}-qadam: {reason}"
        return ""
    if action == "open_folder":
        return "" if Path(payload).is_dir() else "Ochish so'ralgan nishon papka ekanligi tekshirilmadi."
    if action in {"manual", "search_web", "play_music", "stop_music", "close_music",
                  "resume_music", "next_music", "previous_music", "volume_up", "volume_down", "speak",
                  "browser_read", "browser_scroll", "browser_back", "browser_forward", "browser_screenshot",
                  "browser_switch_tab", "browser_set_theme", "browser_close_tab", "browser_close",
                  "desktop_scroll", "desktop_move", "desktop_screenshot", "desktop_active_window", "desktop_focus"}:
        return ""
    if action in {"open_url", "browser_open", "browser_new_tab"}:
        address = value("url")
        if action == "browser_new_tab" and not address:
            return ""
        try:
            parsed = urlparse(address if "://" in address else "https://" + address)
            hostname = parsed.hostname
        except ValueError:
            return "Manzil shakli tekshirilishi kerak."
        if parsed.scheme not in {"http", "https"} or not hostname:
            return "Oddiy HTTP/HTTPS bo'lmagan manzilni ochish."
        if parsed.username or parsed.password or _important(unquote_plus(parsed.path).replace("_", " ")):
            return "Manzil kirish ma'lumoti yoki muhim amalni o'z ichiga oladi."
        if parsed.query:
            # Search and normal navigation queries are fine; action-like parameters are not.
            if _important(unquote_plus(parsed.query).replace("_", " ")):
                return "Manzil parametrlari tashqi o'zgarish keltirishi mumkin."
        return ""
    if action in {"run_app", "desktop_launch"}:
        program = value("program").casefold()
        safe = {"notepad", "notepad.exe", "bloknot", "calc", "calc.exe", "calculator", "kalkulyator",
                "explorer", "explorer.exe", "fayl menejeri", "settings", "sozlamalar", "ms-settings:"}
        if program not in safe or PureWindowsPath(program).name != program:
            return "Tekshirilmagan dastur yoki terminalni ishga tushirish."
        if data.get("args"):
            return "Dasturni qo'shimcha argumentlar bilan ishga tushirish."
        return ""
    if action in {"desktop_type", "browser_type"}:
        text = str(data.get("text", data.get("value", "")))
        if any(character in text for character in ("\r", "\n", "\x00")):
            return "Ko'p qatorli matn terminal buyrug'i yoki yuborishni ishga tushirishi mumkin."
        if action == "browser_type" and _important(value("field")):
            return "Maxfiy yoki muhim maydonga ma'lumot kiritish."
        if re.search(r"(?i)(powershell|cmd\.exe|remove-item|rm\s+-|del\s+|shutdown|format\s+|curl\s+|invoke-expression|iex\s)", text):
            return "Bajariladigan yoki tizimni o'zgartiradigan buyruq matni."
        return ""
    if action == "browser_click":
        label = value("element")
        if _important(label):
            return "Yuborish, o'chirish, to'lov yoki boshqa muhim tugmani bosish."
        # Raw selectors do not describe the effect of clicking their target.
        if not label or label.casefold().startswith(("css:", "xpath:", "#", ".", "/")):
            return "Bosiladigan element ta'siri nomidan aniqlanmadi."
        if re.search(r"\b(search|qidir\w*|izla\w*|next|previous|back|home|menu|close|cancel|"
                     r"play|pause|theme|dark|light|mavzu|keyingi|oldingi|orqaga|yopish|bekor)\b", _normalized(label)):
            return ""
        return "Tugma tashqi o'zgarish qilmasligi tekshirilishi kerak."
    if action in {"desktop_press", "browser_press"}:
        key = value("key").casefold()
        if key in {"tab", "esc", "escape", "left", "right", "up", "down", "home", "end", "pageup", "pagedown", "backspace"}:
            return ""
        return "Bu klavish yuborish, o'chirish yoki buyruqni bajarishi mumkin."
    if action == "desktop_hotkey":
        keys = "+".join(part.strip().casefold() for part in value("keys").split("+"))
        if keys in {"ctrl+c", "ctrl+a", "ctrl+f", "ctrl+l", "ctrl+z", "ctrl+y", "alt+tab", "alt+shift+tab", "win+d", "ctrl+plus", "ctrl+-"}:
            return ""
        return "Saqlash, yopish, yuborish yoki noma'lum klavish kombinatsiyasi."
    if action in {"desktop_click", "desktop_drag"}:
        return "Ekran koordinatasi qaysi amalni bajarishi tekshirilmagan."
    return "Noma'lum yoki muhim amalni tekshirish kerak."
