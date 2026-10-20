"""Only named destinations, never arbitrary model-provided output paths."""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import re
import uuid


def wants_desktop(message: str) -> bool:
    text = message.casefold()
    text = text.replace('‘', "'").replace('’', "'").replace('ʻ', "'")
    # A phrase inside a source filename is not permission to copy to Desktop.
    text = re.sub(r'''(?:[a-z]:[\\/]|/)[^\r\n<>"|?*]+?\.(?:docx|xlsx|pptx|pdf|csv|txt)(?=$|[\s"'”’»),;!?])''', " ", text)
    return bool(re.search(r"\b(?:desktop(?:da|ga)?|ish stol(?:ida|iga|i)?)\s+(?:ham\s+)?(?:\.?(?:txt|docx|xlsx|pptx|pdf|csv)\s+(?:qilib|formatida|ko'rinishida)\s+)?saqla(?:b|ng)?\b", text)
                or re.search(r"\bsave\s+(?:to\s+)?(?:the\s+)?desktop\b", text))


def desktop_directory() -> Path:
    if os.name != "nt":
        raise ValueError("Desktop manzilini avtomatik aniqlash hozircha Windows uchun.")
    # Known Folder API respects OneDrive redirection and localized Desktop names.
    folder_id = (ctypes.c_ubyte * 16).from_buffer_copy(uuid.UUID("B4BFCC3A-DB2C-424C-B029-7FE99A87C641").bytes_le)
    pointer = ctypes.c_void_p()
    function = ctypes.windll.shell32.SHGetKnownFolderPath
    function.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    function.restype = ctypes.c_long
    if function(ctypes.byref(folder_id), 0, None, ctypes.byref(pointer)) != 0:
        raise ValueError("Windows Desktop papkasini aniqlab bo'lmadi.")
    try:
        path = Path(ctypes.wstring_at(pointer))
    finally:
        free = ctypes.windll.ole32.CoTaskMemFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = None
        free(pointer)
    if not path.is_dir():
        raise ValueError("Desktop papkasi mavjud emas yoki unga kirish imkoni yo'q.")
    return path
