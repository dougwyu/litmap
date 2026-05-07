from __future__ import annotations
import re
from pathlib import Path
from typing import Optional

import numpy as np

from litmap.embedder import load_all_embeddings, load_all_fulltext_embeddings, EMBEDDINGS_DB


def find_similar(
    query_embedding: np.ndarray,
    db_path: Path = EMBEDDINGS_DB,
    scope_keys: Optional[list[str]] = None,
    top_k: int = 10,
    exclude_key: Optional[str] = None,
) -> list[dict]:
    """Return top_k most similar papers to query_embedding.

    Each result: {"key": str, "similarity": float}
    """
    matrix, keys = load_all_fulltext_embeddings(db_path, scope_keys)
    if len(keys) == 0:
        return []

    # Cosine similarity: normalise both matrix and query, then dot product
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-10, norms)
    matrix_norm = matrix / norms

    q_norm = query_embedding / max(float(np.linalg.norm(query_embedding)), 1e-10)
    similarities = matrix_norm @ q_norm  # shape (n,)

    results = []
    for key, sim in zip(keys, similarities):
        if key == exclude_key:
            continue
        results.append({"key": key, "similarity": float(sim)})

    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]


def deduplicate_results(
    enriched: list[dict],
    top_k: int,
) -> list[dict]:
    """Collapse duplicate papers from enriched search results.

    Deduplication key: DOI (lowercased, stripped) if non-empty,
    otherwise normalised title (lowercased, stripped).
    Input must already be sorted by descending similarity — the first
    occurrence of each canonical key is kept (highest score wins).
    Returns at most top_k entries.
    """
    seen: set[str] = set()
    unique: list[dict] = []
    for r in enriched:
        doi = (r.get("doi") or "").strip().lower()
        title = (r.get("title") or "").strip().lower()
        canon = doi if doi else title
        if not canon:
            unique.append(r)  # no dedup key available — keep as-is
        elif canon not in seen:
            seen.add(canon)
            unique.append(r)
        if len(unique) == top_k:
            break
    return unique


# Matches: single ALL-CAPS acronyms (>=2 chars), or capitalised words/phrases
_PROPER_NOUN_RE = re.compile(
    r'\b[A-Z]{2,}\b'                          # ALL-CAPS acronyms: GBIF, IPCC
    r'|'
    r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2}\b' # Title Case phrases: MaxEnt, Climate Change
)


def extract_proper_nouns(text: str) -> list[str]:
    """Extract capitalised phrases and acronyms from a sentence."""
    matches = _PROPER_NOUN_RE.findall(text)
    # Deduplicate, filter common English sentence-starters
    _SKIP = {"The", "A", "An", "In", "We", "Our", "This", "These", "For", "To"}
    seen: set[str] = set()
    result = []
    for m in matches:
        if m not in _SKIP and m not in seen:
            seen.add(m)
            result.append(m)
    return result
