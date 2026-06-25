"""Pydantic schemas for items, topics, sources, and fetch results."""

from __future__ import annotations

from datetime import datetime, date
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl

class SourceName(str, Enum):
    HACKERNEWS = "hackernews"
    GITHUB = "github"
    HUGGINGFACE = "huggingface"
    ARXIV = "arxiv"
    NEWSLETTERS = "newsletters"

class Source(BaseModel):
    name: SourceName
    enabled: bool = True
    last_fetched_at: datetime | None = None

class Item(BaseModel):
    """A single piece of content from a source"""
    source: SourceName
    external_id: str = Field(..., description="Source-native identifier, dedupe key")
    title: str
    url: HttpUrl
    summary: str | None = None
    author: str | None = None
    score: float | None = None
    comments: int | None = None
    published_at: datetime
    raw: dict | None = Field(default=None, description="Original payload, for debbuging.")

class Topic(BaseModel):
    label: str
    keywords: list[str] = Field(default_factory=list)
    item_count: int = 0
    avrg_score: float | None = None

class FetchResult(BaseModel):
    source: SourceName
    fetched: int
    inserted: int
    skipped: int
    errors: int
    started_at: datetime
    finished_at: datetime | None = None

    @property
    def duration_seconds(self) -> float | None:
        if self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()
    
def week_start(d: date|datetime) -> date:
    """return the monday of the ISO week containing 'd'"""
    if isinstance(d, datetime):
        d = d.date
    return d.fromordinal(d.toordinal() - d.weekday())