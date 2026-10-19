from __future__ import annotations

import json
import os
import time
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from jarvis.intent import AIIntent, ALLOWED_COMMANDS


def _target_text(value: object) -> str:
    """Keep structured action arguments as valid JSON for the executor."""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return "" if value is None else str(value)


class AIError(RuntimeError):
    """A user-safe error raised when the remote AI service cannot answer."""


class AIProvider(Protocol):
    def ask(self, message: str) -> str: ...


SYSTEM_INSTRUCTION = """Sen JARVISsan — foydalanuvchiga o'zbek tilida yordam beradigan,
aniq va samimiy shaxsiy AI-assistent. Qisqa, foydali javob ber. O'zing tashqi
amallarni bajara olaman deb da'vo qilma; xat yuborish, fayl o'chirish, xarid yoki
qurilmaning xavfli sozlamalarini o'zgartirish kabi ishlar tasdiqlanishi va alohida vosita talab qilishini ayt."""

ROUTER_INSTRUCTION = """Sen JARVIS buyruq tahlilchisisan. Faqat valid JSON qaytar.
Savol yoki suhbat: {"type":"answer","category":"question","reply":"o'zbekcha javob"}.
Kompyuter amali: {"type":"command","category":"browser|computer|media|voice|office","command":"amal","target":"qiymat yoki JSON obyekt","reply":"qisqa tasdiq"}.
Aniq bajarish so'rovi bo'lmasa kompyuter buyrug'ini yaratma. Oddiy amallar avtomatik
bajariladi; yuborish, o'chirish, xarid, xavfli yoki ta'siri noma'lum amallar uchun dastur
tasdiq so'raydi. Tasdiq kerakligini o'zing belgilama va amal bajarildi deb oldindan aytma.
Shell/Python kodini command sifatida qaytarma.

Word/Excel/PowerPoint HUJJAT tayyorlash so'rovi bo'lsa desktop_launch yoki dastur ochish emas,
category="office", command="office_create" tanla. target={"format":"docx|xlsx|pptx",
"prompt":"foydalanuvchining TO'LIQ talabi, mavzu, ma'lumotlar, til, slaydlar soni",
"filename":"papka yo'lisiz ixtiyoriy nom"}. Masalan: "AI haqida 8 slaydli taqdimot tayyorla"
-> office_create format=pptx; "oylik budjet Excel jadvali yarat" -> xlsx; "ariza yoz" -> docx.
Hujjat matnini bu router javobida yaratma: Office Agent alohida to'liq mazmun yaratadi.
Manbali qayta ishlashda source faqat foydalanuvchi AYNAN bergan to'liq lokal fayl yo'li
bo'lishi mumkin. Yo'lni taxmin qilma; yo'l yo'q bo'lsa Office bo'limida fayl tanlashni so'ra.
office_convert: {"source":"foydalanuvchi bergan to'liq fayl yo'li","target_format":"pdf|txt|csv|xlsx|docx",
"sheet":"XLSX->CSV uchun ixtiyoriy varaq nomi"}. DOCX/XLSX/PPTX->PDF, CSV<->XLSX,
TXT<->DOCX, DOCX/PPTX/PDF->TXT qo'llanadi; PDF->Word/Excel yoki OCR hozir yo'q.
Konvertatsiya uchun fayl mazmunini AI'ga yuborma. Natijalar lokal Office kutubxonasiga saqlanadi.

Brauzer (Selenium) amallari:
- browser_open: target URL yoki {"url":"https://example.com"}
- browser_click: {"element":"tugma matni yoki css:#selector"}
- browser_set_theme: RoboContest uchun {"theme":"dark|light"}; "to'q ko'k" -> dark.
- browser_type: {"field":"maydon nomi","text":"yoziladigan matn"}
- browser_press: {"key":"enter|tab|escape|backspace|delete|up|down|left|right","element":"ixtiyoriy element"}
- browser_read: target bo'sh yoki {"selector":"CSS"}; sahifa matnini o'qish
- browser_scroll: {"direction":"up|down"}
- browser_new_tab: target bo'sh yoki {"url":"https://..."};
- browser_switch_tab: {"index":1} yoki {"title":"tab nomi"};
- browser_close_tab, browser_back, browser_forward, browser_screenshot, browser_close: target bo'sh.
Oddiy sayt ochish uchun browser_open, internetdan qidirish uchun search_web tanla.
RoboContest mavzusini o'zgartirish so'rovida browser_set_theme ishlat: bu joriy
holatni tekshiradi, noto'g'ri yo'nalishda qayta bosmaydi. Hech qachon sahifadan
ko'rmagan CSS sinfini (masalan, .theme-toggle) taxmin qilib yozma. Element nomi
aniq bo'lmasa browser_read bilan kuzatishni taklif qil.

Kompyuter (PyAutoGUI) amallari:
- desktop_focus: {"title":"oyna sarlavhasi"}
- desktop_click, desktop_move, desktop_drag: {"x":100,"y":200}
- desktop_type: {"text":"yoziladigan matn"}
- desktop_hotkey: {"keys":"ctrl+s"}; desktop_press: {"key":"enter"}
- desktop_scroll: {"direction":"up|down"}
- desktop_launch: {"program":"notepad.exe","args":[]}
- desktop_screenshot, desktop_active_window: target bo'sh.
Ekran koordinatasini bilmasang uni taxmin qilma; avval skrinshotni so'ra.

Bir nechta bosqich kerak bo'lsa command="workflow", category="computer" va target
1-8 ta qadamdan iborat massiv: [{"action":"desktop_launch","target":{"program":"notepad.exe"}},
{"action":"desktop_focus","target":{"title":"Notepad"}},
{"action":"desktop_type","target":{"text":"Salom"}}]. Faqat yuqoridagi browser_/desktop_
amallaridan foydalan. Bitta buyruqda mumkin bo'lsa workflow ishlatma.

Musiqa amallari (category="media"):
- play_music: target qo'shiq yoki ijrochi nomi;
- stop_music: ijroni pauzaga qo'y, Chrome oynasini yopma;
- close_music: JARVIS ochgan musiqa Chrome oynasini butunlay yop;
- resume_music, next_music, previous_music, volume_up, volume_down: target bo'sh.
'Musiqani to'xtat/pauza qil' -> stop_music; 'musiqani o'chir/yop' -> close_music;
'davom ettir' -> resume_music;
'keyingi/oldingi qo'shiq' -> next_music/previous_music;
'ovozni ko'tar/pasaytir' -> volume_up/volume_down.
Ovozli javob uchun speak target aytiladigan matn. Boshqa command nomini ishlatma."""


@dataclass
class GeminiAI:
    """Minimal Gemini REST client; no third-party Python package is required."""

    api_key: str
    model: str = "gemini-2.5-flash"
    history: list[dict[str, object]] = field(default_factory=list)
    max_history_messages: int = 12

    @classmethod
    def from_environment(cls) -> GeminiAI | None:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key or api_key == "bu_yerga_kalitingizni_yozing":
            return None
        return cls(api_key=api_key, model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"))

    def ask(self, message: str) -> str:
        return self.interpret(message).reply

    def complete_json(self, instruction: str, message: str, *, max_tokens: int = 8000, progress: Callable[[str], None] | None = None) -> dict:
        return _complete_json(self, instruction, message, max_tokens, progress)

    def interpret(self, message: str) -> AIIntent:
        contents = [*self.history, {"role": "user", "parts": [{"text": message}]}]
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION + "\n\n" + ROUTER_INSTRUCTION}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1600, "responseMimeType": "application/json"},
        }
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?"
            + urlencode({"key": self.api_key})
        )
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise AIError(f"Gemini API xatosi ({error.code}): {detail[:300]}") from error
        except URLError as error:
            raise AIError("Gemini API'ga ulanib bo'lmadi. Internetni tekshiring.") from error

        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as error:
            raise AIError("Gemini javob bermadi yoki javob xavfsizlik filtri bilan to'xtatildi.") from error
        try:
            parsed = json.loads(text)
            kind = str(parsed.get("type", "answer"))
            reply = str(parsed.get("reply", ""))
            category = str(parsed.get("category", "question"))
            command = str(parsed.get("command", ""))
            target = _target_text(parsed.get("target", ""))
        except (TypeError, ValueError) as error:
            raise AIError("AI kutilgan JSON javobini qaytarmadi. Qayta urinib ko'ring.") from error
        if not reply:
            reply = "Buyruq tahlil qilindi." if kind == "command" else "Javob tayyorlanmadi."
        if kind == "command" and command not in ALLOWED_COMMANDS:
            return AIIntent(kind="answer", reply="Bu amal JARVIS uchun hali ruxsat etilmagan.")
        self.history = (contents + [{"role": "model", "parts": [{"text": text}]}])[-self.max_history_messages :]
        return AIIntent(kind=kind, reply=reply, category=category, command=command, target=target)


@dataclass
class OpenAICompatibleAI:
    """Works with OpenAI, Groq, and OpenRouter's Chat Completions-compatible APIs."""

    api_key: str
    model: str
    base_url: str
    provider_name: str

    def ask(self, message: str) -> str:
        return self.interpret(message).reply

    def complete_json(self, instruction: str, message: str, *, max_tokens: int = 8000, progress: Callable[[str], None] | None = None) -> dict:
        return _complete_json(self, instruction, message, max_tokens, progress)

    def interpret(self, message: str) -> AIIntent:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_INSTRUCTION + "\n\n" + ROUTER_INSTRUCTION},
                {"role": "user", "content": message},
            ],
            "temperature": 0.2,
        }
        request = Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            text = data["choices"][0]["message"]["content"].strip()
            parsed = json.loads(text)
        except HTTPError as error:
            raise AIError(f"{self.provider_name} API xatosi ({error.code}): {error.read().decode('utf-8', errors='replace')[:250]}") from error
        except URLError as error:
            raise AIError(f"{self.provider_name} API'ga ulanib bo'lmadi. Internetni tekshiring.") from error
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as error:
            raise AIError(f"{self.provider_name} kutilgan JSON javobini qaytarmadi.") from error
        kind = str(parsed.get("type", "answer"))
        category = str(parsed.get("category", "question"))
        command = str(parsed.get("command", ""))
        target = _target_text(parsed.get("target", ""))
        reply = str(parsed.get("reply", "Javob tayyorlanmadi."))
        if kind == "command" and command not in ALLOWED_COMMANDS:
            return AIIntent(kind="answer", reply="Bu amal JARVIS uchun hali ruxsat etilmagan.")
        return AIIntent(kind=kind, reply=reply, category=category, command=command, target=target)


OFFICE_ATTEMPTS = 4
TRANSIENT_HTTP = frozenset({408, 429, 500, 502, 503, 504})


def _office_retry_delay(error, attempt: int) -> float | None:
    """Respect Retry-After; defer to the user instead of ignoring a long cooldown."""
    delay = 2. ** attempt
    hint = error.headers.get("Retry-After") if getattr(error, "headers", None) else None
    if hint:
        try:
            try:
                seconds = float(hint)
            except ValueError:
                date = parsedate_to_datetime(hint)
                seconds = (date.replace(tzinfo=date.tzinfo or timezone.utc)-datetime.now(timezone.utc)).total_seconds()
            if math.isfinite(seconds):
                delay = max(delay, seconds)
        except (ValueError, TypeError, OverflowError):
            pass
    return delay if delay <= 30 else None


def _office_http_error(provider: str, code: int, attempts: int) -> AIError:
    prefix = f"{provider} Office API xatosi ({code}). "
    if code in {408, 500, 502, 503, 504}:
        detail = (f"AI xizmati vaqtinchalik band yoki javob bera olmayapti. {attempts} ta urinish bajarildi. "
                  "Birozdan keyin QAYTA URINISHni bosing. Bu xato kalit noto'g'ri degani emas.")
    elif code == 429:
        detail = "So'rovlar limiti yoki kvota cheklovi. Keyinroq qayta urining; davom etsa provayder kvotasini tekshiring."
    elif code in {401, 403}:
        detail = "API kaliti yoki modelga kirish ruxsatini Agentlar bo'limida tekshiring."
    elif code == 404:
        detail = "Tanlangan model topilmadi. Agentlar bo'limida hisobingizda mavjud modelni tanlang."
    elif code == 400:
        detail = "Model bu so'rov yoki JSON rejimini qabul qilmadi. Model imkoniyatlarini tekshiring."
    else:
        detail = "Provayder so'rovni qabul qilmadi. Hisob/model sozlamalarini tekshiring."
    return AIError(prefix + detail)


def _office_response(request: Request, provider: str, progress=None) -> bytes:
    for attempt in range(1, OFFICE_ATTEMPTS+1):
        try:
            with urlopen(request, timeout=100) as response:
                return response.read(2*1024*1024+1)
        except HTTPError as error:
            code = error.code
            delay = _office_retry_delay(error, attempt)
            error.close()  # Never echo error bodies, source text, or key-bearing URLs.
            if code not in TRANSIENT_HTTP or attempt == OFFICE_ATTEMPTS or delay is None:
                raise _office_http_error(provider, code, attempt) from error
            note = f"{provider} HTTP {code}: xizmat vaqtincha javob bermadi. {delay:g} soniyadan keyin {attempt+1}/{OFFICE_ATTEMPTS}-urinish..."
        except (URLError, TimeoutError, ConnectionError) as error:
            if attempt == OFFICE_ATTEMPTS:
                raise AIError(f"{provider} hujjat so'roviga {attempt} urinishda javob olinmadi. Internetni tekshirib QAYTA URINISHni bosing.") from error
            delay = 2. ** attempt
            note = f"{provider} bilan aloqa uzildi. {delay:g} soniyadan keyin {attempt+1}/{OFFICE_ATTEMPTS}-urinish..."
        if progress:
            progress(note)
        time.sleep(delay)
    raise AIError("Office AI so'rovi tugamadi.")


def _complete_json(ai, instruction: str, message: str, max_tokens: int, progress=None) -> dict:
    """Independent structured generation, never an interpreted command or chat history."""
    if isinstance(ai, GeminiAI):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{ai.model}:generateContent?" + urlencode({"key": ai.api_key})
        payload = {"systemInstruction": {"parts": [{"text": instruction}]},
                   "contents": [{"role": "user", "parts": [{"text": message}]}],
                   "generationConfig": {"temperature": .25, "maxOutputTokens": max_tokens, "responseMimeType": "application/json"}}
        headers = {"Content-Type": "application/json"}
        provider = "Gemini"
    else:
        url = ai.base_url.rstrip("/") + "/chat/completions"
        payload = {"model": ai.model, "messages": [{"role": "system", "content": instruction}, {"role": "user", "content": message}],
                   "temperature": .25, "max_tokens": max_tokens, "response_format": {"type": "json_object"}}
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {ai.api_key}"}
        provider = ai.provider_name
    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        raw = _office_response(request, provider, progress)
        if len(raw) > 2*1024*1024:
            raise AIError("AI hujjat javobi juda katta.")
        data = json.loads(raw)
        if isinstance(ai, GeminiAI):
            candidate = data["candidates"][0]
            if candidate.get("finishReason") not in {None, "STOP"}:
                raise AIError("AI hujjatni to'liq tugatmadi. So'rov hajmini kamaytirib qayta urinib ko'ring.")
            text = "".join(part.get("text", "") for part in candidate["content"]["parts"])
        else:
            choice = data["choices"][0]
            if choice.get("finish_reason") not in {None, "stop"}:
                raise AIError("AI hujjat javobi tugallanmagan. Qisqaroq topshiriq bering.")
            text = choice["message"]["content"]
        result = json.loads(text)
        if not isinstance(result, dict):
            raise ValueError("object expected")
        return result
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as error:
        raise AIError(f"{provider} to'liq hujjat JSON obyektini qaytarmadi. Qayta urinib ko'ring.") from error


def ai_from_environment() -> GeminiAI | OpenAICompatibleAI | None:
    provider = os.environ.get("AI_PROVIDER", "gemini").strip().casefold()
    if provider == "gemini":
        return GeminiAI.from_environment()
    api_key = os.environ.get("AI_API_KEY", "").strip()
    settings = {
        "openai": ("OpenAI", "https://api.openai.com/v1", "gpt-6-astra"),
        "groq": ("Groq", "https://api.groq.com/openai/v1", "openai/gpt-oss-20b"),
        "openrouter": ("OpenRouter", "https://openrouter.ai/api/v1", "~openai/gpt-latest"),
    }
    if not api_key or provider not in settings:
        return None
    name, base_url, default_model = settings[provider]
    return OpenAICompatibleAI(api_key, os.environ.get("AI_MODEL", default_model), base_url, name)
