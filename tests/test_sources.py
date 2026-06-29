"""Source adapter tests: HackerNews and GitHub.

Tests use monkeypatch to mock get_json / get_text so they are fast,
 deterministic, and require no network access.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import sentinel

import pytest

from aiml_pulse.models import Item, SourceName
from aiml_pulse.sources import get_source
from aiml_pulse import storage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hn_hit(object_id: str, title: str, created_at_ts: int, points: int = 10, num_comments: int = 0) -> dict:
    """Return a minimal HN Algolia hit dict."""
    return {
        "objectID": object_id,
        "title": title,
        "url": f"https://example.com/{object_id}",
        "author": "testuser",
        "points": points,
        "num_comments": num_comments,
        "created_at_i": created_at_ts,
        "story_title": None,
        "story_url": None,
    }


def _ts(days_ago: int) -> int:
    """Unix timestamp N days ago from now."""
    return int((datetime.now() - timedelta(days=days_ago)).timestamp())


# ---------------------------------------------------------------------------
# HackerNews source
# ---------------------------------------------------------------------------

class TestHackerNewsSource:
    """Tests for HackerNewsSource.fetch()."""

    def test_fetches_and_parses_items(self, tmp_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """Happy path: API returns hits, they are parsed into Items."""
        storage.bootstrap(path=tmp_db)

        now_ts = _ts(0)

        def fake_get_json(url: str, params: dict, **kwargs) -> dict:  # type: ignore[reportUnusedGeneric]
            assert "hn.algolia.com" in url
            query = params.get("query", "")
            # Return different hit sets per query to verify distinct calls
            if query == "AI":
                return {"hits": [
                    _make_hn_hit("hn1", "GPT-5 announced", now_ts - 3600, points=200),
                ]}
            if query == "LLM":
                return {"hits": [
                    _make_hn_hit("hn2", "LLaMA 3 benchmark results", now_ts - 7200, points=150),
                ]}
            return {"hits": []}

        monkeypatch.setattr("aiml_pulse.sources.hackernews.get_json", fake_get_json)

        src = get_source(SourceName.HACKERNEWS)
        cutoff = date.today() - timedelta(days=7)
        items = src.fetch(cutoff)

        assert len(items) == 2
        titles = {i.title for i in items}
        assert "GPT-5 announced" in titles
        assert "LLaMA 3 benchmark results" in titles

    def test_dedupes_by_object_id(self, tmp_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """Same objectID appearing in multiple queries results in one Item."""
        storage.bootstrap(path=tmp_db)
        now_ts = _ts(0)

        def fake_get_json(url: str, params: dict, **kwargs) -> dict:  # type: ignore[reportUnusedGeneric]
            # Same hit returned regardless of query
            return {"hits": [
                _make_hn_hit("dup1", "Mixture of Experts post", now_ts - 1800, points=99),
            ]}

        monkeypatch.setattr("aiml_pulse.sources.hackernews.get_json", fake_get_json)

        src = get_source(SourceName.HACKERNEWS)
        items = src.fetch(date.today() - timedelta(days=7))

        # Even though many queries will return this hit, dedup keeps only one
        assert len(items) == 1
        assert items[0].external_id == "dup1"

    def test_skips_hits_without_url(self, tmp_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """Hits with no URL field are silently dropped."""
        storage.bootstrap(path=tmp_db)

        def fake_get_json(url: str, params: dict, **kwargs) -> dict:  # type: ignore[reportUnusedGeneric]
            return {"hits": [
                {**(_make_hn_hit("ok1", "Good story", _ts(0))), "url": "https://ok.com"},
                {**(_make_hn_hit("nourl", "No URL here", _ts(0))), "url": None},
            ]}

        monkeypatch.setattr("aiml_pulse.sources.hackernews.get_json", fake_get_json)

        src = get_source(SourceName.HACKERNEWS)
        items = src.fetch(date.today() - timedelta(days=7))

        assert len(items) == 1
        assert items[0].external_id == "ok1"

    def test_uses_story_title_fallback(self, tmp_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """When title is absent, story_title is used instead."""
        storage.bootstrap(path=tmp_db)

        def fake_get_json(url: str, params: dict, **kwargs) -> dict:  # type: ignore[reportUnusedGeneric]
            return {"hits": [
                {
                    "objectID": "ask1",
                    "title": None,
                    "story_title": "Ask HN: Thoughts on AI safety?",
                    "url": "https://news.ycombinator.com/item?id=1",
                    "author": "tester",
                    "points": 50,
                    "num_comments": 12,
                    "created_at_i": _ts(0),
                }
            ]}

        monkeypatch.setattr("aiml_pulse.sources.hackernews.get_json", fake_get_json)

        src = get_source(SourceName.HACKERNEWS)
        items = src.fetch(date.today() - timedelta(days=7))

        assert len(items) == 1
        assert "AI safety" in items[0].title

    def test_continues_after_query_error(self, tmp_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """One failing query does not abort the whole fetch."""
        storage.bootstrap(path=tmp_db)
        call_count = 0

        def fake_get_json(url: str, params: dict, **kwargs) -> dict:  # type: ignore[reportUnusedGeneric]
            nonlocal call_count
            call_count += 1
            query = params.get("query", "")
            if query == "AI":
                raise ConnectionError("network glitch")
            return {"hits": [_make_hn_hit(f"ok{call_count}", f"Story {call_count}", _ts(0))]}

        monkeypatch.setattr("aiml_pulse.sources.hackernews.get_json", fake_get_json)

        src = get_source(SourceName.HACKERNEWS)
        items = src.fetch(date.today() - timedelta(days=7))

        # Should still get items from the queries that succeeded
        assert len(items) >= 1


# ---------------------------------------------------------------------------
# GitHub source
# ---------------------------------------------------------------------------

class TestGitHubSource:
    """Tests for GitHubSource.fetch()."""

    def _make_repo(self, full_name: str, pushed_at: str, stars: int = 100, description: str = "A cool repo") -> dict:
        """Return a minimal GitHub API repo dict."""
        return {
            "full_name": full_name,
            "html_url": f"https://github.com/{full_name}",
            "description": description,
            "owner": {"login": full_name.split("/")[0]},
            "stargazers_count": stars,
            "open_issues_count": 3,
            "language": "Python",
            "created_at": "2020-01-01T00:00:00Z",
            "pushed_at": pushed_at,
        }

    def test_fetches_and_parses_repos(self, tmp_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """Happy path: API returns repos, they are parsed into Items."""
        storage.bootstrap(path=tmp_db)

        def fake_get_json(url: str, params: dict, **kwargs) -> dict:  # type: ignore[reportUnusedGeneric]
            assert "api.github.com" in url
            query = params.get("q", "")
            if "machine-learning" in query:
                return {
                    "items": [
                        self._make_repo("owner/ml-repo", "2026-06-25T12:00:00Z", stars=500),
                    ]
                }
            if "deep-learning" in query:
                return {
                    "items": [
                        self._make_repo("owner/dl-repo", "2026-06-24T10:00:00Z", stars=300),
                    ]
                }
            return {"items": []}

        monkeypatch.setattr("aiml_pulse.sources.github.get_json", fake_get_json)

        src = get_source(SourceName.GITHUB)
        cutoff = date.today() - timedelta(days=7)
        items = src.fetch(cutoff)

        assert len(items) == 2
        titles = {i.title for i in items}
        assert "owner/ml-repo" in titles
        assert "owner/dl-repo" in titles

    def test_uses_pushed_at_not_created_at(self, tmp_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """published_at must come from pushed_at, not created_at."""
        storage.bootstrap(path=tmp_db)

        def fake_get_json(url: str, params: dict, **kwargs) -> dict:  # type: ignore[reportUnusedGeneric]
            return {
                "items": [
                    self._make_repo(
                        "old-repo/old-repo",
                        "2026-06-25T12:00:00Z",  # pushed 2 days ago
                        stars=10,
                    )
                ]
            }

        monkeypatch.setattr("aiml_pulse.sources.github.get_json", fake_get_json)

        src = get_source(SourceName.GITHUB)
        items = src.fetch(date.today() - timedelta(days=7))

        assert len(items) == 1
        # pushed_at was 2026-06-25, so published_at should reflect that, not created_at
        assert items[0].published_at.year == 2026
        assert items[0].published_at.month == 6
        assert items[0].published_at.day == 25

    def test_score_is_star_count(self, tmp_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """Item score must be the stargazers_count (float)."""
        storage.bootstrap(path=tmp_db)

        def fake_get_json(url: str, params: dict, **kwargs) -> dict:  # type: ignore[reportUnusedGeneric]
            return {
                "items": [self._make_repo("stars/test", "2026-06-26T00:00:00Z", stars=12345)]
            }

        monkeypatch.setattr("aiml_pulse.sources.github.get_json", fake_get_json)

        src = get_source(SourceName.GITHUB)
        items = src.fetch(date.today() - timedelta(days=7))

        assert len(items) == 1
        assert items[0].score == 12345.0

    def test_dedupes_by_full_name(self, tmp_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """Same repo appearing in multiple topic queries results in one Item."""
        storage.bootstrap(path=tmp_db)

        def fake_get_json(url: str, params: dict, **kwargs) -> dict:  # type: ignore[reportUnusedGeneric]
            # Same repo returned for different topic queries
            return {
                "items": [self._make_repo("shared/repo", "2026-06-26T00:00:00Z", stars=77)]
            }

        monkeypatch.setattr("aiml_pulse.sources.github.get_json", fake_get_json)

        src = get_source(SourceName.GITHUB)
        items = src.fetch(date.today() - timedelta(days=7))

        assert len(items) == 1
        assert items[0].external_id == "shared/repo"

    def test_continues_after_topic_error(self, tmp_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """One failing topic does not abort the whole fetch."""
        storage.bootstrap(path=tmp_db)
        succeed_count = 0

        def fake_get_json(url: str, params: dict, **kwargs) -> dict:  # type: ignore[reportUnusedGeneric]
            nonlocal succeed_count
            query = params.get("q", "")
            if "machine-learning" in query:
                raise ConnectionError("GH API glitch")
            succeed_count += 1
            return {
                "items": [self._make_repo(f"ok/success{succeed_count}", "2026-06-26T00:00:00Z")]
            }

        monkeypatch.setattr("aiml_pulse.sources.github.get_json", fake_get_json)

        src = get_source(SourceName.GITHUB)
        items = src.fetch(date.today() - timedelta(days=7))

        assert len(items) >= 1
        assert succeed_count >= 1
