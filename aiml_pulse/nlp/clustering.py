"""K-means clustering over the TF-IDF matrix."""

from __future__ import annotations

import numpy as np
from sklearn.cluster import MiniBatchKMeans


def choose_k(n_items: int) -> int:
    if n_items < 5:
        return 1
    return max(5, min(20, n_items // 25))


def cluster(matrix, k: int, random_state: int = 42) -> MiniBatchKMeans:
    """Cluster `matrix` into `k` clusters. Returns the fitted estimator."""
    n_clusters = max(1, min(k, matrix.shape[0]))
    model = MiniBatchKMeans(
        n_clusters=n_clusters,
        random_state=random_state,
        n_init=3,
        batch_size=64,
        reassignment_ratio=0.0,
    )
    model.fit(matrix)
    return model


def cluster_sizes(model: MiniBatchKMeans) -> dict[int, int]:
    """Return {cluster_id: count} ignoring empty clusters."""
    counts = np.bincount(model.labels_, minlength=model.n_clusters)
    return {int(i): int(c) for i, c in enumerate(counts) if c > 0}