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

app = typer.Typer(add_completion=False, help="AI/ML Pulse, local AI/ML field-trends aggregator.")
console = Console()

# structure -> pulse function --parse_since 

def _parse_since(value: str) -> datetime:
    s = value.strip().lower
    if s.endswith("d") and s[:-1].isdigit():
        return datetime.now() - timedelta(days=int(s[:-1]))
    if s.endswith("w") and s[:-1].isdigit():
        return datetime.now() - timedelta(weeks=int(s[:-1]))
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        raise type.BadParameter(f"unrecognized --since={value!r}") from None
    

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

def main() -> None:
    app()

if __name__ == "__main__":
    app()