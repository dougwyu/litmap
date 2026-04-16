import numpy as np
import pytest
from tests.conftest import store_vector, make_vector
from litmap.search import find_similar, extract_proper_nouns


@pytest.fixture
def search_db(embeddings_db):
    """DB with three vectors: k1 and k3 are close, k2 is orthogonal."""
    v1 = np.array([1.0, 0.0, 0.0] + [0.0] * 381, dtype=np.float32)
    v2 = np.array([0.0, 1.0, 0.0] + [0.0] * 381, dtype=np.float32)
    v3 = np.array([0.9, 0.1, 0.0] + [0.0] * 381, dtype=np.float32)
    store_vector(embeddings_db, "k1", v1)
    store_vector(embeddings_db, "k2", v2)
    store_vector(embeddings_db, "k3", v3)
    return embeddings_db


def test_find_similar_ranks_correctly(search_db):
    query = np.array([1.0, 0.0, 0.0] + [0.0] * 381, dtype=np.float32)
    results = find_similar(query, search_db, top_k=3)
    keys = [r["key"] for r in results]
    # k1 has sim=1.0 (identical to query), k3 has high sim, k2 is orthogonal
    assert keys[0] == "k1"
    assert keys[1] == "k3"
    assert keys[2] == "k2"


def test_find_similar_excludes_self(search_db):
    query = np.array([1.0, 0.0, 0.0] + [0.0] * 381, dtype=np.float32)
    results = find_similar(query, search_db, top_k=3, exclude_key="k1")
    assert all(r["key"] != "k1" for r in results)


def test_find_similar_scope(search_db):
    query = np.array([1.0, 0.0, 0.0] + [0.0] * 381, dtype=np.float32)
    results = find_similar(query, search_db, top_k=3, scope_keys=["k2"])
    assert len(results) == 1
    assert results[0]["key"] == "k2"


def test_find_similar_similarity_in_range(search_db):
    query = np.array([1.0, 0.0, 0.0] + [0.0] * 381, dtype=np.float32)
    results = find_similar(query, search_db, top_k=3)
    for r in results:
        assert 0.0 <= r["similarity"] <= 1.0


def test_extract_proper_nouns_finds_acronyms():
    text = "We used MaxEnt and GBIF data for species distribution modelling."
    nouns = extract_proper_nouns(text)
    assert "MaxEnt" in nouns or "GBIF" in nouns


def test_extract_proper_nouns_finds_capitalised_phrases():
    text = "The Intergovernmental Panel on Climate Change report was cited."
    nouns = extract_proper_nouns(text)
    assert any("Intergovernmental" in n for n in nouns)
