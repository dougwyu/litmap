"""Hierarchical clustering, labelling, and outline construction for litmap.

Pure functions. No I/O. No global state. Consumed by cluster_render.py and
by the `litmap cluster` CLI command.
"""
from __future__ import annotations

import numpy as np
from scipy.cluster.hierarchy import linkage as _linkage


def compute_hierarchy(matrix: np.ndarray) -> np.ndarray:
    """Return a scipy linkage matrix from an N×D embedding matrix.

    Uses cosine distance and average linkage — consistent with the cosine
    similarity used elsewhere in litmap, and compatible with non-Euclidean
    metrics (unlike Ward linkage).

    Shape of the returned array: (N-1, 4).
    """
    if matrix.shape[0] < 2:
        raise ValueError("compute_hierarchy requires at least 2 rows")
    return _linkage(matrix, method="average", metric="cosine")


from scipy.cluster.hierarchy import fcluster as _fcluster


def cut_levels(
    linkage: np.ndarray,
    keys: list[str],
    matrix: np.ndarray,
    top_k: int,
    subcluster_threshold: int,
) -> list[dict]:
    """Return [{key, cluster_id, subcluster_id|None}, ...] in input order.

    Level-1 cluster ids come from fcluster(linkage, t=top_k, criterion='maxclust').
    Level-2 sub-clustering runs only on level-1 clusters with size >= threshold;
    for each such cluster we recompute linkage on the subset of rows and cut
    into max(2, round(sqrt(size / 2))) sub-clusters. Papers in smaller clusters
    have subcluster_id = None.
    """
    n = len(keys)
    if matrix.shape[0] != n:
        raise ValueError("keys and matrix must have the same length")

    level1 = _fcluster(linkage, t=top_k, criterion="maxclust")

    from collections import defaultdict
    groups: dict[int, list[int]] = defaultdict(list)
    for idx, cid in enumerate(level1):
        groups[int(cid)].append(idx)

    subcluster_by_idx: dict[int, int | None] = {i: None for i in range(n)}
    for cid, idxs in groups.items():
        size = len(idxs)
        if size < subcluster_threshold:
            continue
        sub_matrix = matrix[idxs]
        sub_linkage = compute_hierarchy(sub_matrix)
        n_sub = max(2, round((size / 2) ** 0.5))
        sub_labels = _fcluster(sub_linkage, t=n_sub, criterion="maxclust")
        for local_i, idx in enumerate(idxs):
            subcluster_by_idx[idx] = int(sub_labels[local_i])

    return [
        {
            "key": keys[i],
            "cluster_id": int(level1[i]),
            "subcluster_id": subcluster_by_idx[i],
        }
        for i in range(n)
    ]
