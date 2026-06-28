from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from aiml_pulse.models import SourceName

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "pulse.db"
DIGESTS_DIR = DATA_DIR / "digests"
CACHE_DIR = DATA_DIR / "cache"

class Settings(BaseModel):
    user_agent: str = "aiml-pulse/0.1 (+https://github.com/local/aiml-pulse)"
    request_timeout_seconds: float = 20.0
    max_retries: int = 3
    enabled_sources: list[SourceName] = Field(default_factory=lambda: list(SourceName))
    default_window_days: int = 7

def load_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return Settings()