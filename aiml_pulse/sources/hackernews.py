"""HackerNews via the Algolia API. Primary source.

API limitation: with numericFilters enabled, the HN Algolia API only supports
up to 2 OR terms per query.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from aiml_pulse.http import get_json
from aiml_pulse.models import Item, SourceName

from .base import BaseSource

logger = logging.getLogger(__name__)

API = "https://hn.algolia.com/api/v1/search"

QUERIES: list[tuple[str, list[str]]] = [
    ("AI", ["AI", "LLM", "GPT", "transformer", "BERT"]),
    ("ML", ["machine learning", "deep learning", "neural network"]),
    ("agents", ["agent", "agentic", "AI assistant", "autonomous"]),
    ("RAG", ["RAG", "embeddings", "vector database", "retrieval"]),
    ("MoE", ["mixture of experts", "MoE"]),
    ("diffusion", ["diffusion", "stable diffusion", "text-to-image"]),
    ("open-source-models", ["open source", "open LLM", "llama", "mistral"]),
    ("safety", ["AI safety", "alignment", "RLHF", "interpretability"]),
]


class HackerNewsSource(BaseSource):
    name = SourceName.HACKERNEWS

    def fetch(self, since: date | datetime) -> list[Item]:
        if isinstance(since, datetime):
            cutoff = since.date()
        else:
            cutoff = since

        cutoff_ts = int(datetime.combine(cutoff, datetime.min.time()).timestamp())
        items: dict[str, Item] = {}

        for label, queries in QUERIES:
            for query in queries:
                params = {
                    "query": query,
                    "tags": "story",
                    "numericFilters": f"created_at_i>={cutoff_ts}",
                    "hitsPerPage": 50,
                }
                try:
                    payload = get_json(API, params=params)
                except Exception as exc:
                    logger.warning("[HN] query %r failed: %s", query, exc)
                    continue

                for hit in payload.get("hits", []):
                    obj_id = hit.get("objectID")
                    if not obj_id or obj_id in items:
                        continue
                    title = hit.get("title") or hit.get("story_title")
                    url = hit.get("url") or hit.get("story_url")
                    if not title or not url:
                        continue
                    items[obj_id] = Item(
                        source=self.name,
                        external_id=obj_id,
                        title=title,
                        url=url,
                        author=hit.get("author"),
                        score=hit.get("points"),
                        comments=hit.get("num_comments"),
                        published_at=datetime.fromtimestamp(hit["created_at_i"]),
                        raw={"hn_query": label, "query_used": query},
                    )

        logger.info("[HN] %d unique items collected", len(items))
        return list(items.values())


__all__ = ["HackerNewsSource"]
