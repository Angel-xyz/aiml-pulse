"""SQLite storage layer with FTS5 full-text search"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any

from aiml_pulse.config import DB_PATH
from aiml_pulse.models import Item, Source, SourceName, Topic, week_start

SCHEMA = """
CREATE TABLE IF NOT EXISTS source (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    enabled         INTEGER NOT NULL DEFAULT 1,
    last_fetched_at TEXT
);

CREATE TABLE IF NOT EXISTS item (
    id              INTEGER PRIMARY KEY,
    source_id       INTEGER NOT NULL REFERENCES source(id),
    external_id     TEXT NOT NULL,
    title           TEXT NOT NULL,
    url             TEXT NOT NULL,
    summary         TEXT,
    author          TEXT,
    score           REAL,
    comments        INTEGER,
    published_at    TEXT NOT NULL,
    fetched_at      TEXT NOT NULL,
    raw             TEXT,
    UNIQUE (source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_item_published_at ON item(published_at);
CREATE INDEX IF NOT EXISTS idx_item_source       ON item(source_id);

CREATE VIRTUAL TABLE IF NOT EXISTS item_fts USING fts5(
    title, summary, content='item', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS item_ai AFTER INSERT ON item BEGIN
    INSERT INTO item_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary);
END;

CREATE TRIGGER IF NOT EXISTS item_ad AFTER DELETE ON item BEGIN
    INSERT INTO item_fts(item_fts, rowid, title, summary)
        VALUES('delete', old.id, old.title, old.summary);
END;

CREATE TRIGGER IF NOT EXISTS item_au AFTER UPDATE ON item BEGIN
    INSERT INTO item_fts(item_fts, rowid, title, summary)
        VALUES('delete', old.id, old.title, old.summary);
    INSERT INTO item_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary);
END;

CREATE TABLE IF NOT EXISTS topic (
    id           INTEGER PRIMARY KEY,
    label        TEXT NOT NULL UNIQUE,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS item_topic (
    item_id      INTEGER NOT NULL REFERENCES item(id) ON DELETE CASCADE,
    topic_id     INTEGER NOT NULL REFERENCES topic(id) ON DELETE CASCADE,
    weight       REAL NOT NULL,
    PRIMARY KEY (item_id, topic_id)
);

CREATE TABLE IF NOT EXISTS topic_snapshot (
    topic_id     INTEGER NOT NULL REFERENCES topic(id) ON DELETE CASCADE,
    week_start   TEXT NOT NULL,
    count        INTEGER NOT NULL,
    avg_score    REAL,
    PRIMARY KEY (topic_id, week_start)
);
"""

def connect(path: str|None = None) -> sqlite3.Connection:
    """Open a conection with row acces by name"""

def init_db(path: str|None = None) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()

def upsert_source(name: SourceName, enabled: bool = True, path: str|None = None) -> int:
    """ToDo"""

def get_enabled_sources(path: str|None = None) -> list[Source]:
    """ToDO"""
    sources = []
    return sources

def set_source_last_fetched(name: SourceName, when: datetime, path: str|None = None) -> None:
    """ToDo"""

def upsert_item(item: Item, path: str|None = None) -> tuple[int, bool]:
    """Insert or skip (dedupe). Returns (id, inserted)"""

def upsert_many(items: Iterable[Item], path: str|None = None)-> tuple[int, int]:
    """Bulk Upsert. Returns (inserted, skipped)""" 

def get_item_since(since: datetime | date, path: str|None = None) -> list[Item]:
    """ToDo"""

def count_items(path: str|None = None) -> int:
    """ToDO"""
    
def search_items(query: str, limit: int = 25, path: str|None = None) -> list[Item]:
    """ToDo"""

def _to_fts_query(q: str) -> str:
    """ToDo"""

def upsert_topic(label: str, path: str|None = None) -> int:
    """ToDO"""

def link_item_topic(item_id: int, topic_id: int, weight: float, path: str|None = None) -> None:
    """ToDO"""

def record_topic_snapshot(topic_id: int, week: date, count: int, avg_score: float|None, path: str|None = None) -> None:
    """ToDo"""

def list_topics(min_items: int = 1, path: str|None = None) -> list[Topic]:
    """ToDO"""

def items_for_topic(topic_label: str, day: int = 7, path: str|None = None) -> list[Item]:
    """ToDO"""

def topic_weekly_history(topic_label: str, week: int = 12, path: str|None = None) -> list[tuple[date, int]]:
    """ToDO"""

def source_distribution(path: str|None = None) -> list[tuple[str, int]]:
    """ToDo"""

def register_default_sources(path: str|None = None) -> None:
    """ToDo"""

def _row_to_item(row: sqlite3.Row) -> Item:
    """ToDo"""

def bootstrap(path: str|None = None) -> None:
    """ToDo"""

def this_week_start() -> None:
    """Call week start from models"""
    return week_start(datetime.now())