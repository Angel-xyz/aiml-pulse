"""Week-over-week trend scoring and snapshot recording."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from aiml_pulse.models import Topic, week_start
from aiml_pulse import storage


def take_snapshot(
    topics: list[Topic], today: date | None = None, path: str | None = None
) -> dict[str, int]:
    today = today or datetime.now().date()
    week = week_start(today)
    recorded: dict[str, int] = {}
    for topic in topics:
        topic_id = storage.upsert_topic(topic.label, path=path)
        storage.record_topic_snapshot(
            topic_id, week, topic.item_count, topic.avg_score, path=path
        )
        recorded[topic.label] = topic.item_count
    return recorded


def week_over_week_delta(
    topic_label: str, today: date | None = None, path: str | None = None
) -> tuple[int, int]:
    """Return (this_week, last_week) item counts for a topic."""
    today = today or datetime.now().date()
    this_week = week_start(today)
    last_week = this_week - timedelta(days=7)

    history = dict(storage.topic_weekly_history(topic_label, weeks=8, path=path))
    return history.get(this_week, 0), history.get(last_week, 0)


def trending_topics(
    weeks: int = 4, path: str | None = None
) -> list[dict[str, str | int | float]]:
    today = datetime.now().date()
    this_week = week_start(today)
    last_week = this_week - timedelta(days=7)

    rows: list[dict[str, str | int | float]] = []
    for topic in storage.list_topics(min_items=1, path=path):
        history = dict(storage.topic_weekly_history(topic.label, weeks=weeks, path=path))
        this = history.get(this_week, 0)
        prev = history.get(last_week, 0)
        delta = this - prev
        rows.append(
            {
                "label": topic.label,
                "this_week": int(this),
                "last_week": int(prev),
                "delta": int(delta),
            }
        )
    rows.sort(key=lambda r: (r["delta"], r["this_week"]), reverse=True)
    return rows
