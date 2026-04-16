from __future__ import annotations

import numpy as np
from sklearn.neighbors import NearestNeighbors
from umap import UMAP


def compute_layout(
    matrix: np.ndarray,
    keys: list[str],
    n_neighbors: int = 15,
    min_dist: float = 0.1,
) -> dict[str, tuple[float, float]]:
    """Reduce embedding matrix to 2D with UMAP. Returns {key: (x, y)}."""
    n = len(keys)
    # UMAP requires n_neighbors < n_samples
    actual_neighbors = min(n_neighbors, n - 1)
    reducer = UMAP(
        n_neighbors=actual_neighbors,
        min_dist=min_dist,
        metric="cosine",
        random_state=42,
        n_jobs=1,
    )
    coords = reducer.fit_transform(matrix)  # shape (n, 2)
    return {key: (float(coords[i, 0]), float(coords[i, 1])) for i, key in enumerate(keys)}


def build_graph(
    matrix: np.ndarray,
    keys: list[str],
    k: int = 3,
) -> list[tuple[str, str, float]]:
    """Return list of (key_a, key_b, cosine_similarity) edges for k-NN graph."""
    n = len(keys)
    actual_k = min(k + 1, n)  # +1 because the point itself is a neighbour
    nbrs = NearestNeighbors(n_neighbors=actual_k, metric="cosine", algorithm="brute")
    nbrs.fit(matrix)
    distances, indices = nbrs.kneighbors(matrix)

    seen = set()
    edges = []
    for i, (dists, idxs) in enumerate(zip(distances, indices)):
        for dist, j in zip(dists, idxs):
            if j == i:
                continue
            pair = (min(i, j), max(i, j))
            if pair in seen:
                continue
            seen.add(pair)
            similarity = float(1.0 - dist)
            edges.append((keys[i], keys[j], similarity))
    return edges
