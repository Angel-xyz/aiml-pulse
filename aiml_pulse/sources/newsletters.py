"""RSS / Atom newsletter ingestion (The Batch, Import AI, Latent Space)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import feedparser

from aiml_pulse.http import get_text
from aiml_pulse.models import Item, SourceName

from .base import BaseSource

FEEDS: list[tuple[str, str]] = [
    ("the-batch", "https://www.deeplearning.ai/the-batch/feed/"),
    ("import-ai", "https://importai.substack.com/feed"),
    ("latent-space", "https://www.latent.space/feed"),
]


class NewslettersSource(BaseSource):
    name = SourceName.NEWSLETTERS

    def fetch(self, since: date | datetime) -> list[Item]:
        if isinstance(since, datetime):
            cutoff = since
        else:
            cutoff = datetime.combine(since, datetime.min.time())

        items: dict[str, Item] = {}
        for feed_id, url in FEEDS:
            try:
                text = get_text(url)
            except Exception:
                continue
            feed = feedparser.parse(text)
            for entry in feed.entries:
                published_struct = getattr(entry, "published_parsed", None) or getattr(
                    entry, "updated_parsed", None
                )
                if not published_struct:
                    continue
                published = datetime(*published_struct[:6])
                if published < cutoff:
                    continue
                link = getattr(entry, "link", None)
                title = getattr(entry, "title", None)
                if not link or not title:
                    continue
                ext_id = f"{feed_id}:{link}"
                if ext_id in items:
                    continue
                items[ext_id] = Item(
                    source=self.name,
                    external_id=ext_id,
                    title=title,
                    url=link,
                    summary=getattr(entry, "summary", None),
                    author=getattr(entry, "author", None),
                    score=None,
                    comments=None,
                    published_at=published,
                    raw={"feed": feed_id},
                )
        return list(items.values())


__all__ = ["NewslettersSource"]
