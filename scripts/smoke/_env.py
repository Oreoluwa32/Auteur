"""Shared .env loader for smoke scripts — no external deps required."""

import os
from pathlib import Path


def load_dotenv() -> None:
    """Load .env from the project root into os.environ (setdefault — never overwrites)."""
    root = Path(__file__).parent.parent.parent
    env_file = root / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)
