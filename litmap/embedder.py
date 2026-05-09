from __future__ import annotations
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from tqdm import tqdm

from litmap.zotero import get_all_items, Item, ZOTERO_DB

EMBEDDINGS_DB = Path.home() / "LitLake" / "embeddings.db"
MODEL_NAME = "Alibaba-NLP/gte-modernbert-base"
DIMS = 768
_BATCH_SIZE = 32
# GTE-ModernBERT context window; leave a small margin
_MAX_TOKENS = 8000
_model = None
_tokenizer = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME, device="mps")
    return _model


def _get_tokenizer():
    global _tokenizer
    if _tokenizer is None:
        from transformers import AutoTokenizer
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    return _tokenizer


def init_db(db_path: Path = EMBEDDINGS_DB) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS embeddings (
            zotero_key  TEXT PRIMARY KEY,
            vector      BLOB NOT NULL,
            embedded_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS fulltext_embeddings (
            zotero_key  TEXT PRIMARY KEY,
            vector      BLOB NOT NULL,
            embedded_at TEXT NOT NULL,
            n_tokens    INTEGER,
            n_chunks    INTEGER
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
    vecs = model.encode([text], normalize_embeddings=True)
    return np.array(vecs[0], dtype=np.float32)


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
    texts = [f"{i.title} {i.abstract} {i.keywords}".strip() for i in items]
    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    with tqdm(total=len(items), desc="Syncing new papers", unit="paper") as bar:
        for batch_start in range(0, len(items), _BATCH_SIZE):
            batch_items = items[batch_start:batch_start + _BATCH_SIZE]
            batch_texts = texts[batch_start:batch_start + _BATCH_SIZE]
            vecs = model.encode(batch_texts, normalize_embeddings=True, show_progress_bar=False)
            for item, vec in zip(batch_items, vecs):
                conn.execute(
                    "INSERT OR REPLACE INTO embeddings (zotero_key, vector, embedded_at) VALUES (?, ?, ?)",
                    (item.key, np.array(vec, dtype=np.float32).tobytes(), now),
                )
                bar.update(1)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Full-text PDF embedding
# ---------------------------------------------------------------------------

def _extract_pdf_text(pdf_path: Path) -> str:
    """Extract plain text from a PDF using PyMuPDF. Returns empty string on failure."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(pdf_path))
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(pages)
    except Exception:
        return ""


def _truncate_to_tokens(text: str, max_tokens: int = _MAX_TOKENS) -> tuple[str, int]:
    """Truncate text to at most max_tokens tokens. Returns (truncated_text, n_tokens)."""
    tokenizer = _get_tokenizer()
    tokens = tokenizer.encode(text, add_special_tokens=False)
    n_tokens = len(tokens)
    if n_tokens <= max_tokens:
        return text, n_tokens
    truncated_ids = tokens[:max_tokens]
    truncated_text = tokenizer.decode(truncated_ids, skip_special_tokens=True)
    return truncated_text, max_tokens


def _embed_fulltext_single(item: Item, max_tokens: int = _MAX_TOKENS) -> Optional[tuple[np.ndarray, int, int]]:
    """Extract, chunk, embed and average a single paper's full text.

    Strategy: split into non-overlapping chunks of max_tokens tokens,
    embed each chunk, then return the L2-normalised mean vector.
    Returns (vector, n_tokens, n_chunks) or None if no text extracted.
    """
    if item.pdf_path is None:
        return None
    raw_text = _extract_pdf_text(item.pdf_path)
    if not raw_text.strip():
        return None

    tokenizer = _get_tokenizer()
    model = _get_model()

    all_tokens = tokenizer.encode(raw_text, add_special_tokens=False)
    n_tokens = len(all_tokens)
    if n_tokens == 0:
        return None

    # Split into chunks
    chunk_ids = [
        all_tokens[start:start + max_tokens]
        for start in range(0, n_tokens, max_tokens)
    ]
    chunk_texts = [
        tokenizer.decode(chunk, skip_special_tokens=True)
        for chunk in chunk_ids
    ]
    n_chunks = len(chunk_texts)

    # Encode one chunk at a time to avoid OOM on MPS with long documents
    chunk_vecs = []
    for chunk_text in chunk_texts:
        vec = model.encode([chunk_text], normalize_embeddings=True, show_progress_bar=False)
        chunk_vecs.append(vec[0])
    vecs = np.stack(chunk_vecs)
    mean_vec = np.mean(vecs, axis=0).astype(np.float32)
    norm = np.linalg.norm(mean_vec)
    if norm > 0:
        mean_vec = mean_vec / norm

    return mean_vec, n_tokens, n_chunks


def _existing_fulltext_keys(db_path: Path) -> set[str]:
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT zotero_key FROM fulltext_embeddings").fetchall()
    conn.close()
    return {r[0] for r in rows}


def load_all_fulltext_embeddings(
    db_path: Path = EMBEDDINGS_DB,
    scope_keys: Optional[list[str]] = None,
) -> tuple[np.ndarray, list[str]]:
    """Load full-text embeddings (falls back to title+abstract embeddings if absent)."""
    conn = sqlite3.connect(db_path)
    if scope_keys:
        placeholders = ",".join("?" * len(scope_keys))
        # Prefer fulltext; fall back to title+abstract
        rows = conn.execute(
            f"""
            SELECT COALESCE(ft.zotero_key, e.zotero_key) AS zotero_key,
                   COALESCE(ft.vector, e.vector) AS vector
            FROM embeddings e
            LEFT JOIN fulltext_embeddings ft ON ft.zotero_key = e.zotero_key
            WHERE e.zotero_key IN ({placeholders})
            """,
            scope_keys,
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT COALESCE(ft.zotero_key, e.zotero_key) AS zotero_key,
                   COALESCE(ft.vector, e.vector) AS vector
            FROM embeddings e
            LEFT JOIN fulltext_embeddings ft ON ft.zotero_key = e.zotero_key
            """
        ).fetchall()
    conn.close()
    if not rows:
        return np.empty((0, DIMS), dtype=np.float32), []
    keys = [r[0] for r in rows]
    matrix = np.stack([np.frombuffer(r[1], dtype=np.float32) for r in rows])
    return matrix, keys


def sync_fulltext(
    db_path: Path = EMBEDDINGS_DB,
    zotero_db: Path = ZOTERO_DB,
    force: bool = False,
    max_tokens: int = _MAX_TOKENS,
) -> tuple[int, int]:
    """Embed full PDF text for all Zotero items that have a local PDF.

    Skips items already in fulltext_embeddings unless force=True.
    Returns (n_embedded, n_skipped_no_pdf).
    """
    init_db(db_path)
    all_items = get_all_items(zotero_db)
    items_with_pdf = [i for i in all_items if i.pdf_path is not None]
    n_skipped_no_pdf = len(all_items) - len(items_with_pdf)

    if not force:
        existing = _existing_fulltext_keys(db_path)
        items_with_pdf = [i for i in items_with_pdf if i.key not in existing]

    if not items_with_pdf:
        return 0, n_skipped_no_pdf

    conn = sqlite3.connect(db_path)
    now = datetime.now(timezone.utc).isoformat()
    n_embedded = 0

    with tqdm(total=len(items_with_pdf), desc="Embedding full-text PDFs", unit="paper") as bar:
        for item in items_with_pdf:
            bar.set_postfix({"file": item.pdf_path.name[:40] if item.pdf_path else ""})
            result = _embed_fulltext_single(item, max_tokens=max_tokens)
            if result is not None:
                vec, n_tokens, n_chunks = result
                conn.execute(
                    """INSERT OR REPLACE INTO fulltext_embeddings
                       (zotero_key, vector, embedded_at, n_tokens, n_chunks)
                       VALUES (?, ?, ?, ?, ?)""",
                    (item.key, vec.tobytes(), now, n_tokens, n_chunks),
                )
                conn.commit()
                n_embedded += 1
            bar.update(1)

    conn.close()
    return n_embedded, n_skipped_no_pdf
