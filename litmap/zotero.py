from dataclasses import dataclass, field
from pathlib import Path
import sqlite3
from typing import Optional

ZOTERO_DB = Path.home() / "Zotero" / "zotero.sqlite"
EXCLUDED_TYPES = (14, 26)  # attachment, note


@dataclass
class Item:
    key: str
    title: str
    abstract: str
    authors: list[str]
    year: str
    doi: str


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _field_ids(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT fieldName, fieldID FROM fields "
        "WHERE fieldName IN ('title','abstractNote','date','DOI')"
    ).fetchall()
    return {r["fieldName"]: r["fieldID"] for r in rows}


def _author_type_id(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT creatorTypeID FROM creatorTypes WHERE creatorType = 'author'"
    ).fetchone()
    return row["creatorTypeID"] if row else 1


def _rows_to_items(rows) -> list[Item]:
    items = []
    for r in rows:
        authors = [a.strip() for a in (r["authors"] or "").split(";") if a.strip()]
        items.append(Item(
            key=r["key"],
            title=r["title"] or "",
            abstract=r["abstract"] or "",
            authors=authors,
            year=(r["year"] or "")[:4],
            doi=r["doi"] or "",
        ))
    return items


_ITEM_SELECT = """
    SELECT
        i.key,
        tv.value  AS title,
        av.value  AS abstract,
        GROUP_CONCAT(c.lastName || ', ' || c.firstName, '; ') AS authors,
        dv.value  AS year,
        doiv.value AS doi
    FROM items i
    LEFT JOIN itemData    td   ON td.itemID   = i.itemID AND td.fieldID   = :title_id
    LEFT JOIN itemDataValues tv ON tv.valueID = td.valueID
    LEFT JOIN itemData    ad   ON ad.itemID   = i.itemID AND ad.fieldID   = :abs_id
    LEFT JOIN itemDataValues av ON av.valueID = ad.valueID
    LEFT JOIN itemData    dd   ON dd.itemID   = i.itemID AND dd.fieldID   = :date_id
    LEFT JOIN itemDataValues dv ON dv.valueID = dd.valueID
    LEFT JOIN itemData    doid ON doid.itemID = i.itemID AND doid.fieldID = :doi_id
    LEFT JOIN itemDataValues doiv ON doiv.valueID = doid.valueID
    LEFT JOIN itemCreators ic ON ic.itemID = i.itemID AND ic.creatorTypeID = :author_type
    LEFT JOIN creators c ON c.creatorID = ic.creatorID
    WHERE i.itemTypeID NOT IN (14, 26)
      AND tv.value IS NOT NULL
"""


def get_all_items(db_path: Path = ZOTERO_DB) -> list[Item]:
    with _connect(db_path) as conn:
        fids = _field_ids(conn)
        atid = _author_type_id(conn)
        rows = conn.execute(
            _ITEM_SELECT + " GROUP BY i.itemID",
            {"title_id": fids["title"], "abs_id": fids["abstractNote"],
             "date_id": fids["date"], "doi_id": fids["DOI"],
             "author_type": atid},
        ).fetchall()
    return _rows_to_items(rows)


def get_collection(name: str, db_path: Path = ZOTERO_DB) -> list[Item]:
    with _connect(db_path) as conn:
        fids = _field_ids(conn)
        atid = _author_type_id(conn)
        rows = conn.execute(
            _ITEM_SELECT + """
              AND i.itemID IN (
                  SELECT ci.itemID FROM collectionItems ci
                  JOIN collections col ON col.collectionID = ci.collectionID
                  WHERE col.collectionName = :name
              )
            GROUP BY i.itemID
            """,
            {"title_id": fids["title"], "abs_id": fids["abstractNote"],
             "date_id": fids["date"], "doi_id": fids["DOI"],
             "author_type": atid, "name": name},
        ).fetchall()
    return _rows_to_items(rows)


def get_item(key_or_doi: str, db_path: Path = ZOTERO_DB) -> Optional[Item]:
    with _connect(db_path) as conn:
        fids = _field_ids(conn)
        atid = _author_type_id(conn)
        rows = conn.execute(
            _ITEM_SELECT + """
              AND (i.key = :val OR doiv.value = :val)
            GROUP BY i.itemID
            LIMIT 1
            """,
            {"title_id": fids["title"], "abs_id": fids["abstractNote"],
             "date_id": fids["date"], "doi_id": fids["DOI"],
             "author_type": atid, "val": key_or_doi},
        ).fetchall()
    items = _rows_to_items(rows)
    return items[0] if items else None
