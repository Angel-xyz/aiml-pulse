"""Storage layer tests: schema, dedupe, FTS5 search. (AI_DONE_TEST)"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from aiml_pulse import storage
from aiml_pulse.models import Item, SourceName


def _make_item(ext: str, title: str, summary: str | None = None, days_ago: int = 1) -> Item:
    return Item(
        source=SourceName.HACKERNEWS,
        external_id=ext,
        title=title,
        url=f"https://example.com/{ext}",
        summary=summary,
        author="someone",
        score=10.0,
        comments=1,
        published_at=datetime.now() - timedelta(days=days_ago),
        raw=None,
    )


def test_bootstrap_creates_schema(tmp_db: str) -> None:
    with storage.connect(tmp_db) as conn:
        tables = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' OR type='view'"
            ).fetchall()
        }
    assert "item" in tables
    assert "item_fts" in tables
    assert "topic" in tables
    assert "topic_snapshot" in tables


def test_upsert_item_inserts_then_skips(tmp_db: str) -> None:
    storage.upsert_source(SourceName.HACKERNEWS, path=tmp_db)
    item = _make_item("abc", "Mixture of experts paper")
    id1, inserted1 = storage.upsert_item(item, path=tmp_db)
    assert inserted1 is True
    id2, inserted2 = storage.upsert_item(item, path=tmp_db)
    assert inserted2 is False
    assert id1 == id2
    assert storage.count_items(path=tmp_db) == 1


def test_fts5_search_finds_match(tmp_db: str) -> None:
    storage.upsert_source(SourceName.HACKERNEWS, path=tmp_db)
    storage.upsert_item(
        _make_item("a", "RAG pipelines are everywhere", "Retrieval augmented generation tutorial"),
        path=tmp_db,
    )
    storage.upsert_item(
        _make_item("b", "LoRA fine-tuning on consumer GPUs", "parameter efficient fine tuning"),
        path=tmp_db,
    )
    results = storage.search_items("retrieval", path=tmp_db)
    assert len(results) == 1
    assert "RAG" in results[0].title


def test_search_supports_prefix_matching(tmp_db: str) -> None:
    storage.upsert_source(SourceName.HACKERNEWS, path=tmp_db)
    storage.upsert_item(
        _make_item("c", "Diffusion models keep improving"),
        path=tmp_db,
    )
    results = storage.search_items("diffus", path=tmp_db)
    assert len(results) >= 1


def test_get_items_since_respects_window(tmp_db: str) -> None:
    storage.upsert_source(SourceName.HACKERNEWS, path=tmp_db)
    storage.upsert_item(_make_item("recent", "Fresh paper", days_ago=1), path=tmp_db)
    storage.upsert_item(_make_item("old", "Ancient paper", days_ago=30), path=tmp_db)
    cutoff = datetime.now() - timedelta(days=7)
    items = storage.get_items_since(cutoff, path=tmp_db)
    ext_ids = {i.external_id for i in items}
    assert "recent" in ext_ids
    assert "old" not in ext_ids


def test_topic_snapshot_round_trip(tmp_db: str) -> None:
    storage.upsert_source(SourceName.HACKERNEWS, path=tmp_db)
    storage.upsert_item(_make_item("z", "agentic workflows are the future"), path=tmp_db)
    topic_id = storage.upsert_topic("agents", path=tmp_db)
    item_id, _ = storage.upsert_item(
        _make_item("y", "agentic workflows are the future v2"), path=tmp_db
    )
    storage.link_item_topic(item_id, topic_id, 1.0, path=tmp_db)
    storage.record_topic_snapshot(topic_id, datetime.now().date(), count=2, avg_score=42.0, path=tmp_db)

    history = storage.topic_weekly_history("agents", path=tmp_db)
    assert len(history) == 1
    assert history[0][1] == 2


def test_source_distribution(tmp_db: str) -> None:
    storage.upsert_source(SourceName.HACKERNEWS, path=tmp_db)
    storage.upsert_source(SourceName.GITHUB, path=tmp_db)
    storage.upsert_item(_make_item("hn1", "hn one"), path=tmp_db)
    storage.upsert_item(_make_item("hn2", "hn two"), path=tmp_db)
    dist = dict(storage.source_distribution(path=tmp_db))
    assert dist.get("hackernews") == 2
    assert "github" in dist
