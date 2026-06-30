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
    target = Path(path) if path else DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(path: str|None = None) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()

def upsert_source(name: SourceName, enabled: bool = True, path: str|None = None) -> int:
    with connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO source (name, enabled) VALUES (?, ?) "
            "ON CONFLICT(name) DO UPDATE SET enabled = excluded.enabled "
            "RETURNING id",
            (name.value, int(enabled)),
        )
        row = cur.fetchone()
        conn.commit()
        assert row is not None
        return int(row["id"])

def get_enabled_sources(path: str|None = None) -> list[Source]:
    """Search for all sources that are enabled and return a list with them"""
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT name, enabled, last_fetched_at FROM source WHERE enabled = 1 ORDER BY name"
        ).fetchall()
    sources: list[Source] = []
    for row in rows:
        last = row["last_fetched_at"]
        sources.append(
            Source(
                name=SourceName(row["name"]),
                enabled=bool(row["enabled"]),
                last_fetched_at=datetime.fromisoformat(last) if last else None,
            )
        )
    return sources

def set_source_last_fetched(name: SourceName, when: datetime, path: str|None = None) -> None:
    with connect(path) as conn:
        conn.execute(
            "UPDATE source SET last_fetched_at = ? WHERE name = ?",
            (when.isoformat(), name.value),
        )
        conn.commit()

def upsert_item(item: Item, path: str|None = None) -> tuple[int, bool]:
    """Insert or skip (dedupe). Returns (id, inserted)"""
    with connect(path) as conn:
        cur = conn.execute(
            "SELECT id FROM source WHERE name = ?",
            (item.source.value,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"source not registered: {item.source}")
        source_id = int(row["id"])

        existing = conn.execute(
            "SELECT id FROM item WHERE source_id = ? AND external_id = ?",
            (source_id, item.external_id),
        ).fetchone()

        if existing is not None:
            return int(existing["id"]), False

        cur = conn.execute(
            "INSERT INTO item (source_id, external_id, title, url, summary, author, "
            "score, comments, published_at, fetched_at, raw) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                source_id,
                item.external_id,
                item.title,
                str(item.url),
                item.summary,
                item.author,
                item.score,
                item.comments,
                item.published_at.isoformat(),
                datetime.now().isoformat(),
                json.dumps(item.raw) if item.raw is not None else None,
            ),
        )
        conn.commit()
        assert cur.lastrowid is not None
        return int(cur.lastrowid), True


def upsert_many(items: Iterable[Item], path: str|None = None)-> tuple[int, int]:
    """Bulk Upsert. Returns (inserted, skipped)"""
    inserted = 0
    skipped = 0
    for item in items:
        _, was_inserted = upsert_item(item, path)
        if was_inserted:
            inserted += 1
        else:
            skipped += 1
    return inserted, skipped

def get_items_since(since: datetime | date, path: str|None = None) -> list[Item]:
    if isinstance(since, datetime):
        since_iso = since.isoformat()
    else:
        since_iso = since.isoformat()

    with connect(path) as conn:
        rows = conn.execute(
            "SELECT i.*, s.name AS source_name FROM item i "
            "JOIN source s ON s.id = i.source_id "
            "WHERE i.published_at >= ? ORDER BY i.published_at DESC",
            (since_iso,),
        ).fetchall()
    return [_row_to_item(r) for r in rows]

def count_items(path: str|None = None) -> int:
    with connect(path) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM item").fetchone()
    return int(row["c"]) if row else 0

def search_items(query: str, limit: int = 25, path: str|None = None) -> list[Item]:
    """FTS5 search over title + summary. Supports bare words, phrases and prefix"""
    if not query.strip():
        return []
    fts_query = _to_fts_query(query)
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT i.*, s.name AS source_name, bm25(item_fts) AS rank "
            "FROM item_fts "
            "JOIN item i    ON i.id = item_fts.rowid "
            "JOIN source s  ON s.id = i.source_id "
            "WHERE item_fts MATCH ? "
            "ORDER BY rank LIMIT ?",
            (fts_query, limit),
        ).fetchall()
    return [_row_to_item(r) for r in rows]

def _to_fts_query(q: str) -> str:
    tokens = [t for t in q.replace('"', " ").split() if t]
    if not tokens:
        return q
    parts = []
    for t in tokens:
        if t.startswith('"') and t.endswith('"') and len(t) > 2:
            parts.append(t)
        else:
            parts.append(f'"{t}"*')
    return " ".join(parts)

def upsert_topic(label: str, path: str|None = None) -> int:
    with connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO topic (label, created_at) VALUES (?, ?) "
            "ON CONFLICT(label) DO UPDATE SET label = excluded.label "
            "RETURNING id",
            (label, datetime.now().isoformat()),
        )
        row = cur.fetchone()
        conn.commit()
        assert row is not None
        return int(row["id"])

def link_item_topic(item_id: int, topic_id: int, weight: float, path: str|None = None) -> None:
    with connect(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO item_topic (item_id, topic_id, weight) VALUES (?, ?, ?)",
            (item_id, topic_id, weight),
        )
        conn.commit()

def record_topic_snapshot(topic_id: int, week: date, count: int, avg_score: float|None, path: str|None = None) -> None:
    with connect(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO topic_snapshot (topic_id, week_start, count, avg_score) "
            "VALUES (?, ?, ?, ?)",
            (topic_id, week.isoformat(), count, avg_score),
        )
        conn.commit()

def list_topics(min_items: int = 1, path: str|None = None) -> list[Topic]:
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT t.id, t.label, "
            "       COALESCE(COUNT(DISTINCT it.item_id), 0) AS cnt, "
            "       AVG(i.score) AS avg_score "
            "FROM topic t "
            "LEFT JOIN item_topic it ON it.topic_id = t.id "
            "LEFT JOIN item i        ON i.id = it.item_id "
            "GROUP BY t.id, t.label "
            "HAVING cnt >= ? "
            "ORDER BY cnt DESC, t.label",
            (min_items,),
        ).fetchall()
    return [
        Topic(
            label=row["label"],
            item_count=int(row["cnt"]),
            avg_score=float(row["avg_score"]) if row["avg_score"] is not None else None,
        )
        for row in rows
    ]

def items_for_topic(topic_label: str, days: int = 7, path: str|None = None) -> list[Item]:
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT i.*, s.name AS source_name "
            "FROM topic t "
            "JOIN item_topic it ON it.topic_id = t.id "
            "JOIN item i        ON i.id = it.item_id "
            "JOIN source s      ON s.id = i.source_id "
            "WHERE t.label = ? AND i.published_at >= datetime('now', ?)",
            (topic_label, f"-{int(days)} days"),
        ).fetchall()
    return [_row_to_item(r) for r in rows]

def topic_weekly_history(topic_label: str, weeks: int = 12, path: str|None = None) -> list[tuple[date, int]]:
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT ts.week_start, ts.count "
            "FROM topic_snapshot ts JOIN topic t ON t.id = ts.topic_id "
            "WHERE t.label = ? "
            "ORDER BY ts.week_start DESC LIMIT ?",
            (topic_label, weeks),
        ).fetchall()
    return [(date.fromisoformat(r["week_start"]), int(r["count"])) for r in rows]

def source_distribution(path: str|None = None) -> list[tuple[str, int]]:
    with connect(path) as conn:
        rows = conn.execute(
            "SELECT s.name AS source, COUNT(i.id) AS cnt "
            "FROM source s LEFT JOIN item i ON i.source_id = s.id "
            "GROUP BY s.name ORDER BY cnt DESC"
        ).fetchall()
    return [(r["source"], int(r["cnt"])) for r in rows]

def register_default_sources(path: str|None = None) -> None:
    for src in SourceName:
        upsert_source(src, path=path)

def _row_to_item(row: sqlite3.Row) -> Item:
    raw: Any = None
    if row["raw"]:
        try:
            raw = json.loads(row["raw"])
        except json.JSONDecodeError:
            raw = None
    return Item(
        source=SourceName(row["source_name"]),
        external_id=row["external_id"],
        title=row["title"],
        url=row["url"],
        summary=row["summary"],
        author=row["author"],
        score=row["score"],
        comments=row["comments"],
        published_at=datetime.fromisoformat(row["published_at"]),
        raw=raw,
    )

def bootstrap(path: str|None = None) -> None:
    """One-shot setups: schema + default source rows"""
    init_db(path)
    register_default_sources(path)

def this_week_start() -> date:
    """Call week start from models"""
    return week_start(datetime.now())