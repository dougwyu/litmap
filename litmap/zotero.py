from dataclasses import dataclass, field
from pathlib import Path
import sqlite3
from typing import Optional

ZOTERO_DB = Path.home() / "Zotero" / "zotero.sqlite"
# Zotero itemTypeIDs we exclude from all paper-level queries:
# 14 = attachment, 26 = note. Neither represents a citable paper.
EXCLUDED_TYPES = (14, 26)
_EXCLUDED_TYPES_SQL = "(" + ",".join(str(t) for t in EXCLUDED_TYPES) + ")"

# Personal "My Library" is libraryID 1; group libraries have other IDs
# (e.g. the RD3 department group = 579642, ~28k energy items). The default
# corpus is Personal only, so the large shared RD3 group is not embedded
# and does not appear in default search/cluster results. Pass
# library_id=None to get_all_items() to include every library.
PERSONAL_LIBRARY_ID = 1


@dataclass
class Item:
    key: str
    title: str
    abstract: str
    authors: list[str]
    year: str
    doi: str
    keywords: str = ""
    pdf_path: Optional[Path] = None


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _field_ids(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT fieldName, fieldID FROM fields "
        "WHERE fieldName IN ('title','abstractNote','date','DOI','keywords')"
    ).fetchall()
    return {r["fieldName"]: r["fieldID"] for r in rows}


def _author_type_id(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT creatorTypeID FROM creatorTypes WHERE creatorType = 'author'"
    ).fetchone()
    return row["creatorTypeID"] if row else 1


def _rows_to_items(rows, zotero_base: Optional[Path] = None) -> list[Item]:
    items = []
    for r in rows:
        authors = [a.strip() for a in (r["authors"] or "").split(";") if a.strip()]
        # Resolve PDF path from storage:filename pattern
        pdf_path: Optional[Path] = None
        raw_path = dict(r).get("pdf_path") or ""
        if raw_path and zotero_base is not None:
            if raw_path.startswith("storage:"):
                filename = raw_path[len("storage:"):]
                # Zotero stores attachments in storage/<8-char-key>/<filename>
                # We use the attachment key stored alongside
                att_key = dict(r).get("att_key") or ""
                candidate = zotero_base / "storage" / att_key / filename
                if candidate.exists():
                    pdf_path = candidate
        items.append(Item(
            key=r["key"],
            title=r["title"] or "",
            abstract=r["abstract"] or "",
            authors=authors,
            year=(r["year"] or "")[:4],
            doi=r["doi"] or "",
            keywords=r["keywords"] or "",
            pdf_path=pdf_path,
        ))
    return items


_ITEM_SELECT = """
    SELECT
        i.key,
        tv.value  AS title,
        av.value  AS abstract,
        GROUP_CONCAT(c.lastName || ', ' || c.firstName, '; ' ORDER BY ic.orderIndex) AS authors,
        dv.value  AS year,
        doiv.value AS doi,
        kv.value  AS keywords,
        att.path  AS pdf_path,
        atti.key  AS att_key
    FROM items i
    LEFT JOIN itemData    td   ON td.itemID   = i.itemID AND td.fieldID   = :title_id
    LEFT JOIN itemDataValues tv ON tv.valueID = td.valueID
    LEFT JOIN itemData    ad   ON ad.itemID   = i.itemID AND ad.fieldID   = :abs_id
    LEFT JOIN itemDataValues av ON av.valueID = ad.valueID
    LEFT JOIN itemData    dd   ON dd.itemID   = i.itemID AND dd.fieldID   = :date_id
    LEFT JOIN itemDataValues dv ON dv.valueID = dd.valueID
    LEFT JOIN itemData    doid ON doid.itemID = i.itemID AND doid.fieldID = :doi_id
    LEFT JOIN itemDataValues doiv ON doiv.valueID = doid.valueID
    LEFT JOIN itemData    kd   ON kd.itemID   = i.itemID AND kd.fieldID   = :keywords_id
    LEFT JOIN itemDataValues kv ON kv.valueID = kd.valueID
    LEFT JOIN itemCreators ic ON ic.itemID = i.itemID AND ic.creatorTypeID = :author_type
    LEFT JOIN creators c ON c.creatorID = ic.creatorID
    LEFT JOIN (
        SELECT parentItemID, MIN(itemID) AS itemID, path
        FROM itemAttachments
        WHERE contentType = 'application/pdf'
        GROUP BY parentItemID
    ) att ON att.parentItemID = i.itemID
    LEFT JOIN items atti ON atti.itemID = att.itemID
    WHERE i.itemTypeID NOT IN """ + _EXCLUDED_TYPES_SQL + """
      AND tv.value IS NOT NULL
"""


def get_all_items(
    db_path: Path = ZOTERO_DB,
    library_id: Optional[int] = PERSONAL_LIBRARY_ID,
) -> list[Item]:
    """All citable items. Defaults to the Personal library only
    (library_id=PERSONAL_LIBRARY_ID); pass library_id=None for every
    library (incl. the RD3 group)."""
    zotero_base = db_path.parent
    with _connect(db_path) as conn:
        fids = _field_ids(conn)
        atid = _author_type_id(conn)
        params = {"title_id": fids["title"], "abs_id": fids["abstractNote"],
                  "date_id": fids["date"], "doi_id": fids["DOI"],
                  "keywords_id": fids.get("keywords"),
                  "author_type": atid}
        lib_sql = ""
        if library_id is not None:
            lib_sql = " AND i.libraryID = :library_id"
            params["library_id"] = library_id
        rows = conn.execute(
            _ITEM_SELECT + lib_sql + " GROUP BY i.itemID", params
        ).fetchall()
    return _rows_to_items(rows, zotero_base)


def get_collection(name: str, db_path: Path = ZOTERO_DB) -> list[Item]:
    zotero_base = db_path.parent
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
             "keywords_id": fids.get("keywords"),
             "author_type": atid, "name": name},
        ).fetchall()
    return _rows_to_items(rows, zotero_base)


def get_item(key_or_doi: str, db_path: Path = ZOTERO_DB) -> Optional[Item]:
    zotero_base = db_path.parent
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
             "keywords_id": fids.get("keywords"),
             "author_type": atid, "val": key_or_doi},
        ).fetchall()
    items = _rows_to_items(rows, zotero_base)
    return items[0] if items else None


def get_subcollection_map(db_path: Path = ZOTERO_DB) -> dict[str, list[str]]:
    """Return {zotero_key: [collection_names]} for every non-attachment item.

    Lists only the collections the item directly belongs to — parents of
    a child collection are not included by inheritance.
    """
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT i.key AS key, col.collectionName AS name
            FROM items i
            JOIN collectionItems ci ON ci.itemID = i.itemID
            JOIN collections col ON col.collectionID = ci.collectionID
            WHERE i.itemTypeID NOT IN """ + _EXCLUDED_TYPES_SQL + """
            ORDER BY i.key, col.collectionName
            """
        ).fetchall()
    mapping: dict[str, list[str]] = {}
    for r in rows:
        mapping.setdefault(r["key"], []).append(r["name"])
    return mapping
