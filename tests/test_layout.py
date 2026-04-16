import numpy as np
import pytest
from litmap.layout import compute_layout, build_graph


@pytest.fixture
def small_embeddings():
    rng = np.random.default_rng(0)
    matrix = rng.random((8, 384)).astype(np.float32)
    keys = [f"k{i}" for i in range(8)]
    return matrix, keys


def test_compute_layout_shape(small_embeddings):
    matrix, keys = small_embeddings
    layout = compute_layout(matrix, keys)
    assert len(layout) == 8
    for key in keys:
        assert key in layout
        x, y = layout[key]
        assert isinstance(float(x), float)
        assert isinstance(float(y), float)


def test_build_graph_k_edges(small_embeddings):
    matrix, keys = small_embeddings
    edges = build_graph(matrix, keys, k=2)
    assert len(edges) > 0
    for key_a, key_b, sim in edges:
        assert key_a in keys
        assert key_b in keys
        assert key_a != key_b
        assert 0.0 <= sim <= 1.0


def test_build_graph_no_self_edges(small_embeddings):
    matrix, keys = small_embeddings
    edges = build_graph(matrix, keys, k=3)
    for key_a, key_b, _ in edges:
        assert key_a != key_b


def test_build_graph_k_controls_density(small_embeddings):
    matrix, keys = small_embeddings
    edges_k2 = build_graph(matrix, keys, k=2)
    edges_k4 = build_graph(matrix, keys, k=4)
    assert len(edges_k4) >= len(edges_k2)
