"""Recognize explicit local conversions without sending paths/content to an AI."""
from __future__ import annotations

import json
import re

from jarvis.intent import AIIntent

_PATH = re.compile(r'''(?<![\w/:.\-])((?:[A-Z]:[\\/]|/)[^\r\n<>"|?*]+?\.(docx|xlsx|pptx|pdf|csv|txt))(?=$|[\s"'”’»),;!?])''', re.I)
_TARGET = re.compile(r"\b(word|docx|excel|xlsx|power\s*point|pptx|pdf|txt|csv)(?:ga|da|ni)?\b", re.I)


def local_conversion_intent(message: str) -> AIIntent | None:
    matches = list(_PATH.finditer(message))
    if len(matches) != 1:
        return None  # Never guess which of multiple paths is the input.
    match = matches[0]
    request = (message[:match.start()] + " " + message[match.end():]).casefold()
    request = request.replace("‘", "'").replace("’", "'").replace("ʻ", "'")
    if any(word in request for word in ("qanday", "mumkinmi", "nima uchun", "qayerda")):
        return None
    if not re.search(r"\b(aylantir\w*|o'gir\w*|ogir\w*|convert\w*|konvert\w*|qil\w*|tayyorla\w*|ber\w*)\b", request):
        return None
    targets = set()
    for target in _TARGET.finditer(request):
        name = re.sub(r"\s+", "", target.group(1).casefold())
        targets.add({"word": "docx", "excel": "xlsx", "powerpoint": "pptx"}.get(name, name))
    if len(targets) != 1:
        return None
    target = targets.pop()
    extension = "." + match.group(2).casefold()
    from jarvis.office.converters import supported_conversions
    if "."+target not in supported_conversions().get(extension, ()):
        return AIIntent("answer", f"{extension.upper()} → {target.upper()} konvertatsiyasi hozircha qo'llanmaydi. Office Studio'dagi formatlar ro'yxatini tanlang.")
    data = {"source": match.group(1), "target_format": target}
    from jarvis.office.destinations import wants_desktop
    if wants_desktop(request):
        data["save_to"] = "desktop"
    return AIIntent("command", f"Fayl lokal ravishda {target.upper()} formatiga aylantiriladi; AI'ga yuborilmaydi.",
                    "office", "office_convert", json.dumps(data, ensure_ascii=False))
