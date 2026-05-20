import sqlite3
import pytest
from pathlib import Path


@pytest.fixture
def zotero_db(tmp_path):
    """Minimal Zotero-schema SQLite DB with two items in one collection."""
    db_path = tmp_path / "zotero.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE itemTypes (itemTypeID INTEGER PRIMARY KEY, typeName TEXT);
        INSERT INTO itemTypes VALUES (2, 'journalArticle');
        INSERT INTO itemTypes VALUES (14, 'attachment');
        INSERT INTO itemTypes VALUES (26, 'note');

        CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
        INSERT INTO fields VALUES (1, 'title');
        INSERT INTO fields VALUES (2, 'abstractNote');
        INSERT INTO fields VALUES (6, 'date');
        INSERT INTO fields VALUES (8, 'DOI');

        CREATE TABLE creatorTypes (creatorTypeID INTEGER PRIMARY KEY, creatorType TEXT);
        INSERT INTO creatorTypes VALUES (1, 'author');

        CREATE TABLE items (
            itemID INTEGER PRIMARY KEY,
            itemTypeID INTEGER,
            libraryID INTEGER DEFAULT 1,
            key TEXT
        );
        INSERT INTO items VALUES (1, 2, 1, 'AAAA0001');
        INSERT INTO items VALUES (2, 2, 1, 'AAAA0002');
        INSERT INTO items VALUES (3, 14, 1, 'AAAA0003');
        INSERT INTO items VALUES (4, 2, 1, 'AAAA0004');

        CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
        INSERT INTO itemDataValues VALUES (101, 'Ecology of Networks');
        INSERT INTO itemDataValues VALUES (102, 'Abstract about ecology');
        INSERT INTO itemDataValues VALUES (103, '2021');
        INSERT INTO itemDataValues VALUES (104, '10.1234/eco');
        INSERT INTO itemDataValues VALUES (201, 'Climate and Change');
        INSERT INTO itemDataValues VALUES (202, 'Abstract about climate');
        INSERT INTO itemDataValues VALUES (203, '2022');
        INSERT INTO itemDataValues VALUES (204, '10.5678/cli');
        INSERT INTO itemDataValues VALUES (301, 'Trait Based Analysis');
        INSERT INTO itemDataValues VALUES (302, 'Abstract about traits');
        INSERT INTO itemDataValues VALUES (303, '2023');
        INSERT INTO itemDataValues VALUES (304, '10.1111/trait');

        CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER);
        INSERT INTO itemData VALUES (1, 1, 101);
        INSERT INTO itemData VALUES (1, 2, 102);
        INSERT INTO itemData VALUES (1, 6, 103);
        INSERT INTO itemData VALUES (1, 8, 104);
        INSERT INTO itemData VALUES (2, 1, 201);
        INSERT INTO itemData VALUES (2, 2, 202);
        INSERT INTO itemData VALUES (2, 6, 203);
        INSERT INTO itemData VALUES (2, 8, 204);
        INSERT INTO itemData VALUES (4, 1, 301);
        INSERT INTO itemData VALUES (4, 2, 302);
        INSERT INTO itemData VALUES (4, 6, 303);
        INSERT INTO itemData VALUES (4, 8, 304);

        CREATE TABLE creators (creatorID INTEGER PRIMARY KEY, firstName TEXT, lastName TEXT);
        INSERT INTO creators VALUES (1, 'Jane', 'Smith');
        INSERT INTO creators VALUES (2, 'Bob', 'Jones');

        CREATE TABLE itemCreators (
            itemID INTEGER, creatorID INTEGER, creatorTypeID INTEGER, orderIndex INTEGER
        );
        INSERT INTO itemCreators VALUES (1, 1, 1, 0);
        INSERT INTO itemCreators VALUES (2, 2, 1, 0);

        CREATE TABLE collections (
            collectionID INTEGER PRIMARY KEY,
            collectionName TEXT,
            parentCollectionID INTEGER,
            libraryID INTEGER DEFAULT 1
        );
        INSERT INTO collections VALUES (1, 'My Papers', NULL, 1);
        INSERT INTO collections VALUES (2, 'Sub A', 1, 1);

        CREATE TABLE collectionItems (collectionID INTEGER, itemID INTEGER);
        INSERT INTO collectionItems VALUES (1, 1);
        INSERT INTO collectionItems VALUES (1, 2);
        INSERT INTO collectionItems VALUES (2, 1);
        INSERT INTO collectionItems VALUES (2, 4);
    """)
    conn.commit()
    conn.close()
    return db_path


import numpy as np


@pytest.fixture
def embeddings_db(tmp_path):
    """Empty embeddings DB with correct schema."""
    db_path = tmp_path / "embeddings.db"
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE embeddings (
            zotero_key TEXT PRIMARY KEY,
            vector     BLOB NOT NULL,
            embedded_at TEXT NOT NULL
        );
        CREATE TABLE fulltext_embeddings (
            zotero_key  TEXT PRIMARY KEY,
            vector      BLOB NOT NULL,
            embedded_at TEXT NOT NULL,
            n_tokens    INTEGER,
            n_chunks    INTEGER
        );
        CREATE TABLE meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        INSERT INTO meta VALUES ('model', 'Alibaba-NLP/gte-modernbert-base');
        INSERT INTO meta VALUES ('dims', '768');
    """)
    conn.commit()
    conn.close()
    return db_path


def make_vector(seed: int, dims: int = 768) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.random(dims).astype(np.float32)


def store_vector(db_path, key: str, vector: np.ndarray):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO embeddings (zotero_key, vector, embedded_at) VALUES (?, ?, datetime('now'))",
        (key, vector.tobytes()),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def make_vector_fn():
    return make_vector
