import numpy as np
import pytest
from tests.conftest import store_vector, make_vector
from litmap.search import find_similar, extract_proper_nouns, deduplicate_results


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


def test_dedup_by_doi_keeps_highest_score():
    """Two entries with the same DOI → only the higher-scoring one survives."""
    results = [
        {"doi": "10.1234/abc", "title": "Paper A",  "similarity": 0.95},
        {"doi": "10.1234/abc", "title": "Paper A",  "similarity": 0.80},
        {"doi": "10.9999/xyz", "title": "Paper B",  "similarity": 0.70},
    ]
    deduped = deduplicate_results(results, top_k=10)
    assert len(deduped) == 2
    assert deduped[0]["similarity"] == 0.95
    dois = [r["doi"] for r in deduped]
    assert dois.count("10.1234/abc") == 1


def test_dedup_by_title_when_no_doi():
    """Two entries with no DOI but same title → only the first (highest score) survives."""
    results = [
        {"doi": "",  "title": "Ecology of Networks", "similarity": 0.90},
        {"doi": "",  "title": "Ecology of Networks", "similarity": 0.85},
        {"doi": "",  "title": "Climate and Change",  "similarity": 0.60},
    ]
    deduped = deduplicate_results(results, top_k=10)
    assert len(deduped) == 2
    assert deduped[0]["title"] == "Ecology of Networks"
    assert deduped[0]["similarity"] == 0.90


def test_dedup_respects_top_k():
    """After deduplication, result list is truncated to top_k."""
    results = [
        {"doi": f"10.1/{i}", "title": f"Paper {i}", "similarity": 1.0 - i * 0.01}
        for i in range(20)
    ]
    deduped = deduplicate_results(results, top_k=5)
    assert len(deduped) == 5


def test_dedup_no_key_items_respect_top_k():
    """Items with no DOI and no title are kept but still respect top_k."""
    results = [{"doi": "", "title": "", "similarity": 1.0 - i * 0.01} for i in range(10)]
    deduped = deduplicate_results(results, top_k=3)
    assert len(deduped) == 3
