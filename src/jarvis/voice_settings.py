"""Local Azure settings; secrets are protected with Windows DPAPI."""
from __future__ import annotations

import base64
import ctypes
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

VOICES = ("uz-UZ-SardorNeural", "uz-UZ-MadinaNeural")


def protect(value: str, decrypt: bool = False) -> str:
    if os.name != "nt":
        raise ValueError("Kalitni saqlash Windows DPAPI talab qiladi.")
    class Blob(ctypes.Structure):
        _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_ubyte))]
    raw = base64.b64decode(value) if decrypt else value.encode()
    buffer = ctypes.create_string_buffer(raw)
    source = Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    result = Blob()
    function = getattr(ctypes.windll.crypt32, "CryptUnprotectData" if decrypt else "CryptProtectData")
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise ValueError("Azure kalitini Windows himoyasida o'qish/saqlash amalga oshmadi.")
    try:
        output = ctypes.string_at(result.data, result.size)
        return output.decode() if decrypt else base64.b64encode(output).decode()
    finally:
        free = ctypes.windll.kernel32.LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(result.data)


@dataclass
class VoiceSettings:
    key: str = field(default="", repr=False)
    region: str = ""
    voice: str = VOICES[0]
    continuous: bool = False
    auto_send: bool = True
    output_enabled: bool = True

    @property
    def configured(self) -> bool:
        return bool(self.key and self.region)

    def validate(self) -> None:
        if not self.key or not re.fullmatch(r"[a-z0-9-]{2,40}", self.region):
            raise ValueError("Azure Speech kaliti va regionini kiriting (masalan: eastus).")
        if self.voice not in VOICES:
            raise ValueError("Sardor yoki Madina ovozini tanlang.")


class VoiceSettingsStore:
    def __init__(self, path: Path = Path("data/voice.json")) -> None:
        self.path = path
        self.error = ""

    def load(self) -> VoiceSettings:
        settings = VoiceSettings(key=os.getenv("AZURE_SPEECH_KEY", os.getenv("SPEECH_KEY", "")),
                                 region=os.getenv("AZURE_SPEECH_REGION", os.getenv("SPEECH_REGION", "")))
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                for name in ("region", "voice", "continuous", "auto_send", "output_enabled"):
                    if name in data:
                        if not isinstance(data[name], type(getattr(settings, name))):
                            raise ValueError("Sozlama turi noto'g'ri")
                        setattr(settings, name, data[name])
                if data.get("key_protected"):
                    settings.key = protect(data["key_protected"], decrypt=True)
            except Exception:
                self.error = "Azure sozlamalarini o'qib bo'lmadi. Ovoz sozlamalarini qayta saqlang."
        return settings

    def save(self, settings: VoiceSettings) -> None:
        settings.validate()
        data = asdict(settings)
        data.pop("key")
        data["key_protected"] = protect(settings.key)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
        temporary.replace(self.path)
        self.error = ""
