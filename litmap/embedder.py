from __future__ import annotations
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from tqdm import tqdm

from litmap.zotero import get_all_items, Item, ZOTERO_DB

EMBEDDINGS_DB = Path.home() / "LitLake" / "embeddings.db"
MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIMS = 384
_model = None


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        _model = TextEmbedding(MODEL_NAME)
    return _model


def init_db(db_path: Path = EMBEDDINGS_DB) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS embeddings (
            zotero_key  TEXT PRIMARY KEY,
            vector      BLOB NOT NULL,
            embedded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS meta (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    conn.execute("INSERT OR IGNORE INTO meta VALUES ('model', ?)", (MODEL_NAME,))
    conn.execute("INSERT OR IGNORE INTO meta VALUES ('dims', ?)", (str(DIMS),))
    conn.commit()
    conn.close()


def embed_text(text: str, db_path: Path = EMBEDDINGS_DB) -> np.ndarray:
    model = _get_model()
    vectors = list(model.embed([text]))
    return np.array(vectors[0], dtype=np.float32)


def get_embedding(zotero_key: str, db_path: Path = EMBEDDINGS_DB) -> Optional[np.ndarray]:
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        "SELECT vector FROM embeddings WHERE zotero_key = ?", (zotero_key,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return np.frombuffer(row[0], dtype=np.float32).copy()


def load_all_embeddings(
    db_path: Path = EMBEDDINGS_DB,
    scope_keys: Optional[list[str]] = None,
) -> tuple[np.ndarray, list[str]]:
    conn = sqlite3.connect(db_path)
    if scope_keys:
        placeholders = ",".join("?" * len(scope_keys))
        rows = conn.execute(
            f"SELECT zotero_key, vector FROM embeddings WHERE zotero_key IN ({placeholders})",
            scope_keys,
        ).fetchall()
    else:
        rows = conn.execute("SELECT zotero_key, vector FROM embeddings").fetchall()
    conn.close()
    if not rows:
        return np.empty((0, DIMS), dtype=np.float32), []
    keys = [r[0] for r in rows]
    matrix = np.stack([np.frombuffer(r[1], dtype=np.float32) for r in rows])
    return matrix, keys


def sync(
    db_path: Path = EMBEDDINGS_DB,
    zotero_db: Path = ZOTERO_DB,
) -> int:
    init_db(db_path)
    all_items = get_all_items(zotero_db)
    existing_keys = _existing_keys(db_path)
    new_items = [i for i in all_items if i.key not in existing_keys]
    if not new_items:
        return 0
    _embed_and_store(new_items, db_path)
    return len(new_items)


def _existing_keys(db_path: Path) -> set[str]:
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT zotero_key FROM embeddings").fetchall()
    conn.close()
    return {r[0] for r in rows}


def _embed_and_store(items: list[Item], db_path: Path) -> None:
    model = _get_model()
    texts = [f"{i.title} {i.abstract}".strip() for i in items]
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    with tqdm(total=len(items), desc="Syncing new papers", unit="paper") as bar:
        for item, text in zip(items, texts):
            vec = next(model.embed([text]))
            vec = np.array(vec, dtype=np.float32)
            conn.execute(
                "INSERT OR REPLACE INTO embeddings (zotero_key, vector, embedded_at) VALUES (?, ?, ?)",
                (item.key, vec.tobytes(), now),
            )
            bar.update(1)
    conn.commit()
    conn.close()
