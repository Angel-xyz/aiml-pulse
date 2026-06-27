"""Shared pytest fixtures: ephemeral SQLite DB"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from aiml_pulse import storage


@pytest.fixture()
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    db = tmp_path / "pulse.db"
    from aiml_pulse import storage as storage_mod
    monkeypatch.setattr(storage_mod, "DB_PATH", db)
    storage_mod.bootstrap(path=str(db))
    yield str(db)
    if db.exists():
        os.remove(db)