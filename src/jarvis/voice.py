from __future__ import annotations

import base64
import subprocess


def speak(text: str) -> None:
    """Use Windows' installed voice in a detached background process, without extra packages."""
    clean = " ".join(text.split())[:1200]
    if not clean:
        return
    text_payload = base64.b64encode(clean.encode("utf-8")).decode("ascii")
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$voice = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$voice.Rate = 0; "
        f"$text = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{text_payload}')); "
        "$voice.Speak($text)"
    )
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-EncodedCommand", encoded],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
