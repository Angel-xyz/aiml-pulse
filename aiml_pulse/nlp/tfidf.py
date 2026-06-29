"""TF-IDF vectorization over the ingested item corpus."""

from __future__ import annotations

from collections.abc import Iterable

from sklearn.feature_extraction.text import TfidfVectorizer

from aiml_pulse.models import Item


def build_corpus(items: Iterable[Item]) -> list[str]:
    """Concatenate title and summary, lowercased, with title duplicated
    so it carries more weight than summary in the resulting matrix."""
    docs: list[str] = []
    for item in items:
        title = (item.title or "").strip()
        summary = (item.summary or "").strip()
        docs.append(f"{title}. {title}. {summary}".lower())
    return docs


def fit_tfidf(docs: list[str]) -> tuple[TfidfVectorizer, "scipy.sparse.csr_matrix"]:  # type: ignore[name-defined]
    """Fit a TF-IDF vectorizer tuned for short technical snippets."""
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.6,
        max_features=5000,
        token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z+#.-]{2,}\b",
    )
    matrix = vectorizer.fit_transform(docs)
    return vectorizer, matrix
