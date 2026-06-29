"""Topic naming heuristics — turn cluster centroids into human labels."""

from __future__ import annotations

from sklearn.cluster import MiniBatchKMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from aiml_pulse.models import Item, Topic


STOP_TERMS = {
    "model", "models", "data", "paper", "papers", "result", "results",
    "approach", "method", "methods", "task", "tasks", "performance",
    "github", "release", "using", "based", "show", "demonstrate",
    "showed", "introduce", "introduces", "propose", "proposes",
    "available", "new", "open", "source", "work", "works", "use",
    "used", "achieves", "achieve", "improved", "improves",
}


def name_cluster(
    vectorizer: TfidfVectorizer,
    model: MiniBatchKMeans,
    cluster_id: int,
    top_n: int = 3,
) -> str:
    """Pick the most distinctive terms of a cluster and join them."""
    terms = vectorizer.get_feature_names_out()
    centroid = model.cluster_centers_[cluster_id]
    top_indices = centroid.argsort()[::-1]

    chosen: list[str] = []
    for idx in top_indices:
        term = terms[idx].replace(" ", "_")
        if term in STOP_TERMS:
            continue
        if any(t.startswith(term + "_") or t == term for t in chosen):
            continue
        chosen.append(term)
        if len(chosen) >= top_n:
            break
    return " / ".join(chosen) if chosen else f"cluster-{cluster_id}"


def name_topics(
    vectorizer: TfidfVectorizer,
    model: MiniBatchKMeans,
) -> list[tuple[int, str]]:
    """Return [(cluster_id, label)] for every non-empty cluster."""
    named: list[tuple[int, str]] = []
    for cid in range(model.n_clusters):
        if (model.labels_ == cid).sum() == 0:
            continue
        named.append((cid, name_cluster(vectorizer, model, cid)))
    return named


def build_topic_assignments(
    items: list[Item],
    labels,
    names: list[tuple[int, str]],
) -> list[tuple[Item, str, float]]:
    """Pair each item with its cluster label and weight (centroid similarity)."""
    by_id = {cid: name for cid, name in names}
    out: list[tuple[Item, str, float]] = []
    for item, cid in zip(items, labels, strict=True):
        label = by_id.get(int(cid))
        if label is None:
            continue
        out.append((item, label, 1.0))
    return out


def aggregate_topics(
    assignments: list[tuple[Item, str, float]],
) -> list[Topic]:
    by_label: dict[str, Topic] = {}
    for item, label, weight in assignments:
        topic = by_label.setdefault(label, Topic(label=label, item_count=0))
        topic.item_count += 1
        if item.score is not None:
            if topic.avg_score is None:
                topic.avg_score = 0.0
            topic.avg_score = (
                topic.avg_score * (topic.item_count - 1) + item.score
            ) / topic.item_count
    return sorted(by_label.values(), key=lambda t: t.item_count, reverse=True)