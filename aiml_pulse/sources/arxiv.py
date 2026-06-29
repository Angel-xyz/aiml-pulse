"""arXiv API for cs.AI / cs.CL / cs.LG papers."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta

from aiml_pulse.http import get_text
from aiml_pulse.models import Item, SourceName

from .base import BaseSource

API = "http://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivSource(BaseSource):
    name = SourceName.ARXIV

    def fetch(self, since: date | datetime) -> list[Item]:
        if isinstance(since, datetime):
            cutoff = since.date()
        else:
            cutoff = since

        # arXiv rejects date ranges far in the past; cap to last 30 days.
        earliest = (datetime.now().date() - timedelta(days=30))
        window_start = max(cutoff, earliest)

        query = (
            "cat:cs.AI OR cat:cs.CL OR cat:cs.LG "
            f"AND submittedDate:[{window_start.strftime('%Y%m%d')}000000 TO 20991231235959]"
        )

        params = {
            "search_query": query,
            "start": 0,
            "max_results": 40,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        try:
            text = get_text(API, params=params)
        except Exception:
            return []
        root = ET.fromstring(text)
        items: dict[str, Item] = {}
        for entry in root.findall("atom:entry", NS):
            arxiv_id = entry.findtext("atom:id", default="", namespaces=NS)
            arxiv_id = arxiv_id.rsplit("/", 1)[-1]
            if not arxiv_id:
                continue
            title = (entry.findtext("atom:title", default="", namespaces=NS) or "").strip()
            summary = (entry.findtext("atom:summary", default="", namespaces=NS) or "").strip()
            author_el = entry.find("atom:author/atom:name", NS)
            author = author_el.text if author_el is not None else None
            published_el = entry.findtext("atom:published", default="", namespaces=NS)
            try:
                published = datetime.fromisoformat(published_el.replace("Z", "+00:00"))
            except ValueError:
                published = datetime.now()
            items[arxiv_id] = Item(
                source=self.name,
                external_id=arxiv_id,
                title=title,
                url=f"https://arxiv.org/abs/{arxiv_id}",
                summary=summary[:1000],
                author=author,
                score=None,
                comments=None,
                published_at=published,
                raw={"category": "arxiv"},
            )
        return list(items.values())


__all__ = ["ArxivSource"]