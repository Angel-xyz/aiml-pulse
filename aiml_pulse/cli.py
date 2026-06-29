from __future__ import annotations

import sys
import json
import webbrowser
from datetime import date, datetime, timedelta
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from aiml_pulse import digest, storage, trends
from aiml_pulse.config import DIGESTS_DIR, load_settings
from aiml_pulse.models import FetchResult, Item, SourceName
from aiml_pulse.nlp.tfidf import build_corpus, fit_tfidf
from aiml_pulse.nlp.clustering import choose_k, cluster
from aiml_pulse.nlp.topics import aggregate_topics, name_topics
from aiml_pulse.sources import get_source

app = typer.Typer(add_completion=False, help="AI/ML Pulse, local AI/ML field-trends aggregator.")
console = Console()

def _parse_since(value: str) -> datetime:
    s = value.strip().lower()
    if s.endswith("d") and s[:-1].isdigit():
        return datetime.now() - timedelta(days=int(s[:-1]))
    if s.endswith("w") and s[:-1].isdigit():
        return datetime.now() - timedelta(weeks=int(s[:-1]))
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        raise typer.BadParameter(f"unrecognized --since={value!r}") from None

def _emit_json(payload: object) -> None:
    typer.echo(json.dumps(payload, indent=2, default=str))

def _print_summary(results: list[FetchResult]) -> None:
    table = Table(title="Fetch Summary",show_lines=False)
    table.add_column("Source")
    table.add_column("Fetched", justify="right")
    table.add_column("Inserted", justify="right")
    table.add_column("Skipped", justify="right")
    table.add_column("Error", justify="right")
    table.add_column("Seconds", justify="right")
    total_inserted = 0
    total_skipped = 0
    for result in results:
        table.add_row(
            result.source.value,
            str(result.fetched),
            str(result.inserted),
            str(result.skipped),
            str(result.errors),
            f"{result.duration_seconds:.1f}" if result.duration_seconds is not None else "--"
        )
        total_inserted += result.inserted
        total_skipped += result.skipped
    console.print(table)
    console.print(f"[bold]Total inserted:[/bold] {total_inserted} * Skipped: {total_skipped}")

def _items_to_json(items: list[Item]) -> list[dict]:
    return [
        {
            "id": item.external_id,
            "source": item.source,
            "title": item.title,
            "url": item.url,
            "summary": item.summary,
            "author": item.author,
            "score": item.score,
            "published_at": item.published_at.isoformat()
        } for item in items
    ]

def _item_id(item: Item) -> int | None:
    rows = storage.search_items(f'"{item.external_id}"', limit=1)
    for r in rows:
        if r.external_id == item.external_id and r.source == item.source:
            with storage.connect() as conn:
                row = conn.execute(
                    "SELECT id FROM item WHERE external_id = ? AND source_id = "
                    "(SELECT id FROM source WHERE name = ?)",
                    (item.external_id, item.source.value),
                ).fetchone()
                if row:
                    return int(row["id"])
    return None

@app.command()
def fetch(
    since: str = typer.Option("7d", help="Window like 7d or 2w"),
    sources: str = typer.Option("", help="Comma-separated source names (Default: all enabled)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="dry run"),
    json_output: bool = typer.Option(False, "--json", help="json as stdout")
) -> None:
    """Scrape all configured sources, persist to SQLite while caching"""
    storage.bootstrap()
    cutoff = _parse_since(since)

    if sources.strip():
        wanted = {s.strip() for s in sources.split(",") if s.strip()}
        source_names = [SourceName(s) for s in wanted]
    else:
        source_names = list(load_settings().enabled_sources)

    console.print(
        Panel.fit(
            f"[bold]pulse fetch[/bold] · since={cutoff.date().isoformat()}\n"
            f"sources: {', '.join(s.value for s in source_names)}\n"
            f"dry-run: {dry_run}",
            border_style="cyan",
        )
    )

    results: list[FetchResult] = []
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console, transient=True) as progress:
        for src_name in source_names:
            task = progress.add_task(f"Fetching {src_name.value}…", total=None)
            started = datetime.now()
            try:
                source = get_source(src_name)
                items = source.fetch(cutoff)
                inserted = 0
                skipped = 0
                if not dry_run:
                    inserted, skipped = storage.upsert_many(items)
                    storage.set_source_last_fetched(src_name, started)
                else:
                    inserted = len(items)
                results.append(
                    FetchResult(
                        source=src_name,
                        fetched=len(items),
                        inserted=inserted,
                        skipped=skipped,
                        errors=0,
                        started_at=started,
                        finished_at=datetime.now(),
                    )
                )
            except Exception as exc:
                console.print(f"[red]Error fetching {src_name.value}:[/red] {exc}")
                results.append(
                    FetchResult(
                        source=src_name,
                        fetched=0,
                        inserted=0,
                        skipped=0,
                        errors=1,
                        started_at=started,
                        finished_at=datetime.now(),
                    )
                )
            finally:
                progress.update(task, completed=True)

    if json_output:
        _emit_json([r.model_dump() for r in results])
    else:
        _print_summary(results)

    if any(r.errors for r in results):
        sys.exit(1)

@app.command()
def top(
    days: int = typer.Option(7, help="Limit of days for the top (Default: 7)"),
    limit: int = typer.Option(20, help="Limit of elements (Default: 20)"),
    json_output: bool = typer.Option(False, "--json")
) -> None:
    """Top paper/repos/discussions of the week"""
    storage.bootstrap()
    cutoff = datetime.now() - timedelta(days=days)
    items = storage.get_items_since(cutoff)
    items = sorted(items, key=lambda i: (i.score or 0), reverse=True)[:limit]

    if json_output:
        _emit_json(_items_to_json(items))
        return

    table = Table(title=f"Top {limit} items · last {days} days", show_lines=False)
    table.add_column("Score", justify="right")
    table.add_column("Source")
    table.add_column("Title")
    for item in items:
        score = f"{item.score:.0f}" if item.score is not None else "—"
        title = item.title if len(item.title) <= 80 else item.title[:77] + "…"
        table.add_row(score, item.source.value, f"[link={item.url}]{title}[/link]")
    console.print(table)

@app.command()
def trending(
    days: int = typer.Option(7, help="Limit of days for the top (Default: 7)"),
    limit: int = typer.Option(20, help="Limit of elements (Default: 20)"),
    json_output: bool = typer.Option(False, "--json")
) -> None:
    """Scrape trending repos with the tag AI/ML (ranked by weekly stars)"""
    storage.bootstrap()
    cutoff = datetime.now() - timedelta(days=days)
    items = storage.get_items_since(cutoff)
    gh_items = [i for i in items if i.source == SourceName.GITHUB]
    gh_items = sorted(gh_items, key=lambda i: (i.score or 0), reverse=True)[:limit]

    if json_output:
        _emit_json(_items_to_json(gh_items))
        return

    if not gh_items:
        console.print("No GitHub items yet. Run `pulse fetch --sources github`.")
        return
    table = Table(title=f"Trending GitHub repos · last {days} days", show_lines=False)
    table.add_column("★/day", justify="right")
    table.add_column("Repo")
    for item in gh_items:
        score = f"{item.score:.0f}" if item.score is not None else "—"
        table.add_row(score, f"[link={item.url}]{item.title}[/link]")
    console.print(table)

@app.command()
def topics(
    days: int = typer.Option(7, help="window in days (Default 7)"),
    k: int = typer.Option(0, help="Number of clusters (0 = auto)"),
    json_output: bool = typer.Option(False, "--json")
) -> None:
    """Auto extract trending topics (TF-IDF + K-means)"""
    storage.bootstrap()
    cutoff = datetime.now() - timedelta(days=days)
    items = storage.get_items_since(cutoff)

    if len(items) < 5:
        console.print("[yellow]Not enough items to cluster.[/yellow] Run `pulse fetch` first.")
        return

    docs = build_corpus(items)
    vectorizer, matrix = fit_tfidf(docs)
    cluster_k = k if k > 0 else choose_k(len(items))
    model = cluster(matrix, cluster_k)
    names = name_topics(vectorizer, model)
    name_by_id = {cid: label for cid, label in names}

    assignments: list[tuple[Item, str, float]] = []
    for item, cid in zip(items, model.labels_, strict=True):
        label = name_by_id.get(int(cid))
        if label:
            assignments.append((item, label, 1.0))

    aggregated = aggregate_topics(assignments)
    trends.take_snapshot(aggregated)

    for item, label in zip(items, model.labels_, strict=True):
        topic_label = name_by_id.get(int(label))
        if topic_label is None:
            continue
        topic_id = storage.upsert_topic(topic_label)
        item_id = _item_id(item)
        if item_id is not None:
            storage.link_item_topic(item_id, topic_id, 1.0)

    if json_output:
        _emit_json([t.model_dump() for t in aggregated])
        return

    table = Table(title=f"Topics · last {days} days · k={cluster_k}", show_lines=False)
    table.add_column("#", justify="right")
    table.add_column("Topic")
    table.add_column("Items", justify="right")
    table.add_column("Avg score", justify="right")
    for idx, topic in enumerate(aggregated, start=1):
        avg = f"{topic.avg_score:.1f}" if topic.avg_score is not None else "—"
        table.add_row(str(idx), topic.label, str(topic.item_count), avg)
    console.print(table)

@app.command()
def search(
    query: str = typer.Argument(..., help="Search query."),
    limit: int = typer.Option(25),
    json_output: bool = typer.Option(False, "--json", help="json as stdout")
) -> None:
    """Full-text search across all ingested items (FTS5)"""
    storage.bootstrap()
    items = storage.search_items(query, limit=limit)

    if json_output:
        _emit_json(_items_to_json(items))
        return

    if not items:
        console.print(f"No matches for [bold]{query}[/bold].")
        return
    table = Table(title=f"Search · {query} · {len(items)} hits", show_lines=False)
    table.add_column("Source")
    table.add_column("Title")
    table.add_column("Published")
    for item in items:
        title = item.title if len(item.title) <= 80 else item.title[:77] + "…"
        table.add_row(
            item.source.value,
            f"[link={item.url}]{title}[/link]",
            item.published_at.strftime("%Y-%m-%d"),
        )
    console.print(table)

@app.command(name="digest")
def digest_cmd(
    days: int = typer.Option(7, help="Limit of days for the top (Default: 7)"),
    out: Path = typer.Option(None, "--out", help="Output path."),
    open_browser: bool = typer.Option(False, "--open", help="Open the file in your browser")
) -> None:
    """Generate a beatiful HTML digest for the week"""
    storage.bootstrap()
    output = digest.render(days=days, output=out)
    console.print(f"[green]Wrote[/green] {output}")
    if open_browser:
        webbrowser.open(output.as_uri())

@app.command()
def dashboard(
    port: int = typer.Option(8051, help="Streamlit Port")
) -> None:
    """Launch the streamlit dashboard"""

@app.command()
def follow(
    topic: str = typer.Argument(..., help="Topic label, e.g. 'RAG' or 'mixture_of_experts'."),
    days: int = typer.Option(30),
    json_output: bool = typer.Option(False, "--json", help="json as stdout")
) -> None:
    """Track a specific topic. Prints weekly count history."""

def main() -> None:
    app()

if __name__ == "__main__":
    app()