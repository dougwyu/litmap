import numpy as np
import pytest

from litmap.cluster import compute_hierarchy


def test_compute_hierarchy_shape():
    rng = np.random.default_rng(0)
    matrix = rng.random((10, 768)).astype(np.float32)
    linkage = compute_hierarchy(matrix)
    assert linkage.shape == (9, 4)
    assert (linkage[:, 2] >= 0).all()
