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

from aiml_pulse.models import FetchResult, Item, SourceName

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

def _item_id(item: Item) -> int:
    """ToDo, needs functional storage (bd)"""

@app.command()
def fetch(
    since: str = typer.Option("7d", help="Window like 7d or 2w"),
    sources: str = typer.Option("", help="Comma-separated source names (Default: all enabled)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="dry run"),
    json_output: bool = typer.Option(False, "--json", help="json as stdout")
) -> None:
    """Scrape all configured sources, persist to SQLite while caching"""

@app.command()
def top(
    days: int = typer.Option(7, help="Limit of days for the top (Default: 7)"),
    limit: int = typer.Option(20, help="Limit of elements (Default: 20)"),
    json_output: bool = typer.Option(False, "--json")
) -> None:
    """Top paper/repos/discussions of the week"""

@app.command()
def trending(
    days: int = typer.Option(7, help="Limit of days for the top (Default: 7)"),
    limit: int = typer.Option(20, help="Limit of elements (Default: 20)"),
    json_output: bool = typer.Option(False, "--json")
) -> None:
    """Scrape trending repos with the tag AI/ML (ranked by weekly stars)"""

@app.command()
def topics(
    days: int = typer.Option(7, help="window in days (Default 7)"),
    k: int = typer.Option(0, help="Number of clusters (0 = auto)"),
    json_output: bool = typer.Option(False, "--json")
) -> None:
    """Auto extract trending topics (TF-IDF + K-means)"""

@app.command()
def search(
    query: str = typer.Argument(..., help="Search query."),
    limit: int = typer.Option(25),
    json_output: bool = typer.Option(False, "--json", help="json as stdout")
) -> None:
    """Full-text search across all ingested items (FTS5)"""

@app.command(name="digest")
def digest_cmd(
    days: int = typer.Option(7, help="Limit of days for the top (Default: 7)"),
    out: Path = typer.Option(None, "--out", help="Output path."),
    open_browser: bool = typer.Option(False, "--open", help="Open the file in your browser")
) -> None:
    """Generate a beatiful HTML digest for the week"""

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