"""GitHub repos via the unauthenticated Search API.

Rate limit: 60 req/hr for unauthenticated. One request per topic — fine for v1.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

from aiml_pulse.http import get_json
from aiml_pulse.models import Item, SourceName

from .base import BaseSource

logger = logging.getLogger(__name__)

API = "https://api.github.com/search/repositories"

# Topics to track, each becomes a separate API call.
TOPICS = (
    "machine-learning",
    "deep-learning",
    "llm",
    "pytorch",
    "tensorflow",
    "generative-ai",
    "rag",
)

# Base query applied to every call. repos with 0 stars are noise.
BASE_QUERY = "is:public stars:>10"


class GitHubSource(BaseSource):
    name = SourceName.GITHUB

    def fetch(self, since: date | datetime) -> list[Item]:
        if isinstance(since, datetime):
            cutoff = since.date()
        else:
            cutoff = since

        since_str = cutoff.isoformat()
        items: dict[str, Item] = {}

        for topic in TOPICS:
            query = f"{BASE_QUERY} topic:{topic} pushed:>={since_str}"
            params = {
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": 30,
            }
            try:
                payload = get_json(API, params=params)
            except Exception as exc:
                logger.warning("[GH] topic %s failed: %s", topic, exc)
                continue

            for repo in payload.get("items", []):
                full_name = repo["full_name"]
                if full_name in items:
                    continue

                items[full_name] = Item(
                    source=self.name,
                    external_id=full_name,
                    title=full_name,
                    url=repo["html_url"],
                    summary=repo.get("description"),
                    author=repo["owner"]["login"],
                    score=float(repo["stargazers_count"]),
                    comments=int(repo.get("open_issues_count", 0)),
                    published_at=datetime.fromisoformat(repo["pushed_at"].rstrip("Z")),
                    raw={
                        "topic": topic,
                        "language": repo.get("language"),
                        "stars": repo["stargazers_count"],
                    },
                )

        logger.info("[GH] %d repos from %d topics", len(items), len(TOPICS))
        return list(items.values())


__all__ = ["GitHubSource"]