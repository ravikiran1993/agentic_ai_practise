from __future__ import annotations

from pathlib import Path


def load_environment(dotenv_path: str | Path | None = None) -> bool:
    """Load local environment variables from .env when python-dotenv is installed."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False

    path = Path(dotenv_path) if dotenv_path else _default_dotenv_path()
    return bool(load_dotenv(path, override=False))


def _default_dotenv_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"

