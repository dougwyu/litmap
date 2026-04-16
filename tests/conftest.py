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

        CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
        INSERT INTO itemDataValues VALUES (101, 'Ecology of Networks');
        INSERT INTO itemDataValues VALUES (102, 'Abstract about ecology');
        INSERT INTO itemDataValues VALUES (103, '2021');
        INSERT INTO itemDataValues VALUES (104, '10.1234/eco');
        INSERT INTO itemDataValues VALUES (201, 'Climate and Change');
        INSERT INTO itemDataValues VALUES (202, 'Abstract about climate');
        INSERT INTO itemDataValues VALUES (203, '2022');
        INSERT INTO itemDataValues VALUES (204, '10.5678/cli');

        CREATE TABLE itemData (itemID INTEGER, fieldID INTEGER, valueID INTEGER);
        INSERT INTO itemData VALUES (1, 1, 101);
        INSERT INTO itemData VALUES (1, 2, 102);
        INSERT INTO itemData VALUES (1, 6, 103);
        INSERT INTO itemData VALUES (1, 8, 104);
        INSERT INTO itemData VALUES (2, 1, 201);
        INSERT INTO itemData VALUES (2, 2, 202);
        INSERT INTO itemData VALUES (2, 6, 203);
        INSERT INTO itemData VALUES (2, 8, 204);

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

        CREATE TABLE collectionItems (collectionID INTEGER, itemID INTEGER);
        INSERT INTO collectionItems VALUES (1, 1);
        INSERT INTO collectionItems VALUES (1, 2);
    """)
    conn.commit()
    conn.close()
    return db_path
