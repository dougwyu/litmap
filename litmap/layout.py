from __future__ import annotations

import numpy as np
from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import HDBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer
from umap import UMAP

from litmap.zotero import Item


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


def _read_pdf_text(item: Item) -> str:
    """Extract plain text from item's local PDF. Returns empty string if unavailable."""
    if item.pdf_path is None:
        return ""
    try:
        import fitz
        doc = fitz.open(str(item.pdf_path))
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text
    except Exception:
        return ""


def cluster_labels(
    layout: dict[str, tuple[float, float]],
    items: list[Item],
    min_cluster_size: int = 5,
) -> dict[str, tuple[float, float, str]]:
    """Run HDBSCAN on 2D layout coords; label each cluster with TF-IDF keywords.

    TF-IDF corpus uses full PDF text when available, falling back to
    title + abstract per paper. Returns {cluster_id: (centroid_x, centroid_y, label)}
    for all clusters except noise (cluster -1).
    """
    keys = list(layout.keys())
    coords = np.array([layout[k] for k in keys])

    clusterer = HDBSCAN(min_cluster_size=min_cluster_size, store_centers="centroid")
    labels = clusterer.fit_predict(coords)

    # Build item index for text lookup
    item_idx = {i.key: i for i in items}

    # Group keys by cluster
    from collections import defaultdict
    clusters: dict[int, list[str]] = defaultdict(list)
    for key, label in zip(keys, labels):
        if label >= 0:
            clusters[label].append(key)

    if not clusters:
        return {}

    # TF-IDF over title+abstract for clean keyword extraction
    cluster_ids = sorted(clusters.keys())
    corpus = []
    for cid in cluster_ids:
        texts = []
        for key in clusters[cid]:
            item = item_idx.get(key)
            if item is None:
                continue
            texts.append(f"{item.title} {item.abstract}")
        corpus.append(" ".join(texts))

    tfidf = TfidfVectorizer(max_features=5000, stop_words="english", ngram_range=(1, 2))
    try:
        tfidf_matrix = tfidf.fit_transform(corpus)
    except ValueError:
        return {}
    feature_names = np.array(tfidf.get_feature_names_out())

    result: dict[int, tuple[float, float, str]] = {}
    for i, cid in enumerate(cluster_ids):
        # Top 3 TF-IDF terms for this cluster
        row = np.asarray(tfidf_matrix[i].todense()).flatten()
        top_idx = row.argsort()[-3:][::-1]
        keywords = " · ".join(feature_names[top_idx])

        # Centroid of cluster points in 2D
        member_coords = coords[[j for j, lbl in enumerate(labels) if lbl == cid]]
        cx, cy = float(member_coords[:, 0].mean()), float(member_coords[:, 1].mean())
        result[cid] = (cx, cy, keywords)

    return result


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
