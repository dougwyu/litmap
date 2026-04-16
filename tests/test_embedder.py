import numpy as np
import pytest
import sqlite3
from unittest.mock import patch, MagicMock
from litmap.embedder import init_db, embed_text, get_embedding, sync, DIMS


def test_init_db_creates_tables(tmp_path):
    db_path = tmp_path / "embeddings.db"
    init_db(db_path)
    import sqlite3
    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "embeddings" in tables
    assert "meta" in tables
    conn.close()


def test_embed_text_returns_float32_array(tmp_path):
    db_path = tmp_path / "embeddings.db"
    init_db(db_path)
    with patch("litmap.embedder._get_model") as mock_model:
        mock_model.return_value.embed.return_value = iter(
            [np.ones(DIMS, dtype=np.float32)]
        )
        vec = embed_text("test sentence", db_path)
    assert vec.shape == (DIMS,)
    assert vec.dtype == np.float32


def test_get_embedding_returns_stored_vector(embeddings_db, make_vector_fn):
    vec = make_vector_fn(42)
    from tests.conftest import store_vector
    store_vector(embeddings_db, "KEY001", vec)
    result = get_embedding("KEY001", embeddings_db)
    assert result is not None
    np.testing.assert_array_almost_equal(result, vec)


def test_get_embedding_returns_none_for_missing(embeddings_db):
    result = get_embedding("NOTEXIST", embeddings_db)
    assert result is None


def test_sync_embeds_only_new_items(zotero_db, tmp_path):
    db_path = tmp_path / "embeddings.db"
    init_db(db_path)
    with patch("litmap.embedder._get_model") as mock_model:
        fake_vec = np.ones(DIMS, dtype=np.float32)
        mock_model.return_value.embed.return_value = iter([fake_vec, fake_vec])
        count = sync(db_path, zotero_db)
    assert count == 2  # two journalArticle items in fixture

    # second sync should embed 0 new items
    with patch("litmap.embedder._get_model") as mock_model:
        mock_model.return_value.embed.return_value = iter([])
        count2 = sync(db_path, zotero_db)
    assert count2 == 0
