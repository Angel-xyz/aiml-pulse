"""HTML digest renderer."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from aiml_pulse import storage, trends
from aiml_pulse.config import DIGESTS_DIR
from aiml_pulse.models import Item, Topic

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _fmt_score(value: float | None) -> str:
    if value is None:
        return "—"
    if value >= 1000:
        return f"{value / 1000:.1f}k"
    return f"{value:.0f}"


def _items_by_source(items: list[Item]) -> dict[str, list[Item]]:
    out: dict[str, list[Item]] = {}
    for item in items:
        out.setdefault(item.source.value, []).append(item)
    return out


def render(
    *,
    days: int = 7,
    top_n: int = 10,
    topics: list[Topic] | None = None,
    trending: list[dict[str, str | int | float]] | None = None,
    items: list[Item] | None = None,
    today: date | None = None,
    output: Path | None = None,
) -> Path:
    today = today or datetime.now().date()
    cutoff = datetime.combine(today, datetime.min.time())

    items = items if items is not None else storage.get_items_since(cutoff)
    items = sorted(items, key=lambda i: (i.score or 0), reverse=True)[:top_n]
    topics = topics if topics is not None else storage.list_topics(min_items=1)
    trending = trending if trending is not None else trends.trending_topics()

    env = _env
    env.filters["fmt_score"] = _fmt_score
    template = env.get_template("digest.html.j2")

    html = template.render(
        today=today,
        days=days,
        items=items,
        items_by_source=_items_by_source(storage.get_items_since(cutoff)),
        topics=topics[:8],
        trending=trending[:10],
    )

    if output is None:
        iso_year, iso_week, _ = today.isocalendar()
        output = DIGESTS_DIR / f"pulse-{iso_year}-W{iso_week:02d}.html"

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output