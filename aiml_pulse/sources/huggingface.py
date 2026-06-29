"""HuggingFace Hub API for new models and papers."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from aiml_pulse.http import get_json
from aiml_pulse.models import Item, SourceName

from .base import BaseSource

MODELS_API = "https://huggingface.co/api/models"
PAPERS_API = "https://huggingface.co/api/papers"


class HuggingFaceSource(BaseSource):
    name = SourceName.HUGGINGFACE

    def fetch(self, since: date | datetime) -> list[Item]:
        if isinstance(since, datetime):
            cutoff = since.date()
        else:
            cutoff = since
        items: dict[str, Item] = {}

        try:
            models = get_json(
                MODELS_API,
                params={"full": "true", "limit": 30, "direction": "-1", "sort": "created"},
            )
        except Exception:
            models = []
        for m in models:
            model_id = m.get("modelId") or m.get("id")
            if not model_id:
                continue
            if model_id in items:
                continue
            created = m.get("createdAt")
            try:
                published = datetime.fromisoformat(created.replace("Z", "+00:00")) if created else datetime.now()
            except ValueError:
                published = datetime.now()
            items[model_id] = Item(
                source=self.name,
                external_id=model_id,
                title=model_id,
                url=f"https://huggingface.co/{model_id}",
                summary=(m.get("pipeline_tag") or ""),
                author=model_id.split("/")[0] if "/" in model_id else None,
                score=float(m.get("downloads") or 0),
                comments=m.get("likes"),
                published_at=published,
                raw={"kind": "model"},
            )

        try:
            papers = get_json(PAPERS_API)
        except Exception:
            papers = []
        for p in papers:
            paper_id = str(p.get("id") or p.get("paperId"))
            if not paper_id or paper_id in items:
                continue
            title = p.get("title", "Untitled paper")
            items[paper_id] = Item(
                source=self.name,
                external_id=paper_id,
                title=title,
                url=f"https://huggingface.co/papers/{paper_id}",
                summary=p.get("summary"),
                author=(p.get("authors") or [{}])[0].get("name") if p.get("authors") else None,
                score=float(p.get("upvotes") or 0),
                comments=None,
                published_at=datetime.now(),
                raw={"kind": "paper"},
            )
        return list(items.values())


__all__ = ["HuggingFaceSource"]
