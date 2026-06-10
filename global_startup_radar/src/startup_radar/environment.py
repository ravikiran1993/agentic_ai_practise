from __future__ import annotations

import os
from pathlib import Path
from collections.abc import Mapping


def load_environment(dotenv_path: str | Path | None = None) -> bool:
    """Load local environment variables from .env when python-dotenv is installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False

    path = Path(dotenv_path) if dotenv_path else _default_dotenv_path()
    return bool(load_dotenv(path, override=False))


def apply_runtime_secrets(secrets: Mapping) -> None:
    """Copy Streamlit/runtime secrets into os.environ without overwriting local values."""
    for key, value in secrets.items():
        if key not in os.environ and isinstance(value, (str, int, float, bool)):
            os.environ[key] = str(value)


def _default_dotenv_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"
