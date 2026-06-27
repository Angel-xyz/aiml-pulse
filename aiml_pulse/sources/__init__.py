"""Source adapters: one module per upstream.

Every source implements `BaseSource.fetch(since) -> list[Item]` and is
registered in `SOURCES` so the CLI can iterate by source name.
Only HackerNews is fully implemented in v1.
"""

from __future__ import annotations

from aiml_pulse.models import SourceName

from .base import BaseSource
from .hackernews import HackerNewsSource

SOURCES: dict[SourceName, type[BaseSource]] = {
    SourceName.HACKERNEWS: HackerNewsSource,
    # Stubs — implement their .fetch() before adding here:
    # SourceName.GITHUB:       GitHubSource,
    # SourceName.HUGGINGFACE:  HuggingFaceSource,
    # SourceName.ARXIV:        ArxivSource,
    # SourceName.NEWSLETTERS:  NewsletterSource,
}


def get_source(name: SourceName) -> BaseSource:
    cls = SOURCES[name]
    return cls()


__all__ = ["BaseSource", "SOURCES", "get_source"]
