from __future__ import annotations

import os
from pathlib import Path


def load_local_env(path: Path = Path(".env")) -> None:
    """Load only simple KEY=VALUE pairs without overwriting real environment values."""
    if not path.is_file():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def save_local_env(values: dict[str, str], path: Path = Path(".env")) -> None:
    """Persist user-provided local settings without exposing them in source control."""
    existing: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", maxsplit=1)
                existing[key.strip()] = value.strip()
    existing.update({key: value.strip() for key, value in values.items() if value.strip()})
    path.write_text("\n".join(f"{key}={value}" for key, value in existing.items()) + "\n", encoding="utf-8")
    os.environ.update(existing)
