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
