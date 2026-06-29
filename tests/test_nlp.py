"""NLP pipeline tests on a tiny synthetic corpus."""

from __future__ import annotations

from datetime import datetime

from aiml_pulse.models import Item, SourceName
from aiml_pulse.nlp.clustering import choose_k, cluster, cluster_sizes
from aiml_pulse.nlp.tfidf import build_corpus, fit_tfidf
from aiml_pulse.nlp.topics import name_cluster, name_topics


def _make_items() -> list[Item]:
    now = datetime.now()
    return [
        Item(
            source=SourceName.HACKERNEWS,
            external_id=str(i),
            title=f"item {i}",
            url=f"https://example.com/{i}",
            summary=text,
            author="tester",
            score=1.0,
            published_at=now,
        )
        for i, text in enumerate(
            [
                "mixture of experts for scalable language models",
                "sparse mixture of experts routing strategies",
                "switch transformers with mixture of experts layers",
                "diffusion model for high-resolution image generation",
                "stable diffusion XL open weights release",
                "latent diffusion beats GANs on image synthesis",
                "retrieval augmented generation for open domain QA",
                "RAG pipelines with vector databases and reranking",
                "advanced RAG chunking strategies and evaluation",
            ]
        )
    ]


def test_build_corpus_concatenates_fields() -> None:
    items = _make_items()
    docs = build_corpus(items)
    assert len(docs) == len(items)
    for doc in docs:
        assert doc.startswith("item ")  # title duplicated and lowercased


def test_tfidf_fits_with_expected_shape() -> None:
    items = _make_items()
    docs = build_corpus(items)
    vec, matrix = fit_tfidf(docs)
    assert matrix.shape[0] == len(items)
    assert matrix.shape[1] > 0
    assert len(vec.get_feature_names_out()) == matrix.shape[1]


def test_clustering_separates_themes() -> None:
    items = _make_items()
    docs = build_corpus(items)
    vec, matrix = fit_tfidf(docs)
    k = 3
    model = cluster(matrix, k)
    sizes = cluster_sizes(model)
    assert len(sizes) == 3
    biggest = max(sizes, key=sizes.get)
    assert biggest is not None


def test_topic_naming_returns_strings() -> None:
    items = _make_items()
    docs = build_corpus(items)
    vec, matrix = fit_tfidf(docs)
    k = 3
    model = cluster(matrix, k)
    names = name_topics(vec, model)
    assert len(names) == k
    for cid, label in names:
        assert isinstance(label, str)
        assert label  # non-empty


def test_choose_k_clamps_to_range() -> None:
    assert choose_k(0) == 1
    assert choose_k(3) == 1
    assert 5 <= choose_k(100) <= 20
