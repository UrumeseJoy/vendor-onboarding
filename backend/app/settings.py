"""Settings read from backend/.env (real environment variables win).

Each setting is a function, read at call time, so tests can change it with monkeypatch.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).parent.parent
load_dotenv(BACKEND_DIR / ".env")

DEFAULT_FRONTEND_ORIGIN = "http://localhost:5173"


def extractor_mode() -> str:
    return os.getenv("EXTRACTOR_MODE", "mock").strip() or "mock"


def storage_dir() -> Path:
    """Where uploads are saved. A relative path is relative to the backend folder, not the cwd."""
    path = Path(os.getenv("STORAGE_DIR", "").strip() or "storage")
    return path if path.is_absolute() else BACKEND_DIR / path


def stage_delay_ms() -> int:
    """Pause after each stage so the live view is watchable. 0 in tests."""
    try:
        return max(0, int(os.getenv("STAGE_DELAY_MS", "400")))
    except ValueError:
        return 400


def frontend_origins() -> list[str]:
    extra = [o.strip() for o in os.getenv("FRONTEND_ORIGINS", "").split(",") if o.strip()]
    return [DEFAULT_FRONTEND_ORIGIN, *extra]


def demo_mode() -> bool:
    """Admin demo endpoints (like reset) only work when DEMO_MODE=true. Off when unset."""
    return os.getenv("DEMO_MODE", "false").strip().lower() == "true"


def cache_dir() -> Path:
    """Extraction cache. CACHE_DIR overrides the default (used by tests)."""
    path = Path(os.getenv("CACHE_DIR", "").strip() or ".cache/extraction")
    return path if path.is_absolute() else BACKEND_DIR / path
