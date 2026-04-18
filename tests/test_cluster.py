import numpy as np
import pytest

from litmap.cluster import compute_hierarchy


def test_compute_hierarchy_shape():
    rng = np.random.default_rng(0)
    matrix = rng.random((10, 768)).astype(np.float32)
    linkage = compute_hierarchy(matrix)
    assert linkage.shape == (9, 4)
    assert (linkage[:, 2] >= 0).all()


from litmap.cluster import cut_levels


def _three_cluster_matrix():
    """9 vectors forming 3 tight, well-separated clusters of 3."""
    rng = np.random.default_rng(42)
    centres = np.array([
        [1.0] + [0.0] * 767,
        [0.0, 1.0] + [0.0] * 766,
        [0.0, 0.0, 1.0] + [0.0] * 765,
    ], dtype=np.float32)
    rows = []
    for c in centres:
        for _ in range(3):
            jitter = rng.normal(scale=0.01, size=768).astype(np.float32)
            rows.append(c + jitter)
    return np.stack(rows)  # shape (9, 768)


def test_cut_levels_three_synthetic_clusters():
    matrix = _three_cluster_matrix()
    keys = [f"k{i}" for i in range(9)]
    linkage = compute_hierarchy(matrix)
    assignments = cut_levels(
        linkage, keys, matrix, top_k=3, subcluster_threshold=99999
    )
    assert all(a["subcluster_id"] is None for a in assignments)
    cluster_ids = {a["cluster_id"] for a in assignments}
    assert cluster_ids == {1, 2, 3}
    from collections import Counter
    counts = Counter(a["cluster_id"] for a in assignments)
    assert all(c == 3 for c in counts.values())
    assert [a["key"] for a in assignments] == keys


def test_cut_levels_respects_subcluster_threshold():
    matrix = _three_cluster_matrix()
    keys = [f"k{i}" for i in range(9)]
    linkage = compute_hierarchy(matrix)
    assignments = cut_levels(
        linkage, keys, matrix, top_k=1, subcluster_threshold=100
    )
    assert all(a["cluster_id"] == 1 for a in assignments)
    assert all(a["subcluster_id"] is None for a in assignments)


def test_cut_levels_splits_large_cluster():
    matrix = _three_cluster_matrix()
    keys = [f"k{i}" for i in range(9)]
    linkage = compute_hierarchy(matrix)
    assignments = cut_levels(
        linkage, keys, matrix, top_k=1, subcluster_threshold=5
    )
    assert all(a["cluster_id"] == 1 for a in assignments)
    subcluster_ids = {a["subcluster_id"] for a in assignments}
    assert None not in subcluster_ids
    assert len(subcluster_ids) >= 2
