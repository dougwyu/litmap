# litmap — Design Spec
**Date:** 2026-04-16
**Status:** Approved

---

## Overview

`litmap` is a local Python CLI package that provides two capabilities:

1. **Semantic map** (`litmap map`): generates a 2D network diagram of papers from a Zotero collection or manuscript bibliography, positioned by semantic similarity, with k-nearest-neighbour edges. Outputs interactive HTML and publication-quality PNG/PDF.

2. **Semantic search** (`litmap search`): finds papers in Zotero semantically similar to a query sentence, passage, or focal paper. Outputs a ranked list (human-readable or JSON for machine consumption).

Both features share a common embedding cache (`~/LitLake/embeddings.db`) that is updated automatically on every command invocation.

The tool is security-conscious by design: fully local, no background processes, no daemon, no network calls (embeddings run via `fastembed` on-device). It replicates the core functionality of [lit-lake](https://github.com/ElliotRoe/lit-lake) without the `.mcpb` installer, persistent queue worker, or opaque binary.

---

## Project Location

```
~/src/Cowork/litmap/
├── pyproject.toml
├── litmap/
│   ├── __init__.py
│   ├── cli.py
│   ├── zotero.py
│   ├── embedder.py
│   ├── manuscript.py
│   ├── layout.py
│   ├── search.py
│   └── renderer.py
└── tests/
```

---

## Architecture & Data Flow

```
Input
  ├── --collection "Name"     → zotero.py  → list of papers
  └── --manuscript file.pdf   → manuscript.py → cited papers + manuscript text
                                            ↓
                              embedder.py (auto-sync new Zotero items)
                                            ↓
                              embeddings.db (sqlite-vec, ~/LitLake/)
                                            ↓
                    ┌─────────────────────────────────────┐
                    │ map command          │ search command │
                    │ layout.py (UMAP +    │ search.py      │
                    │ k-NN graph)          │ (cosine sim)   │
                    │ renderer.py          │ ranked results │
                    │ → HTML + PDF/PNG     │ → table / JSON │
                    └─────────────────────────────────────┘
```

---

## Modules

### `zotero.py`
- Reads directly from `~/Zotero/zotero.sqlite` (no Zotero process required)
- `get_collection(name) → [Item]` — returns all items in a named collection
- `get_item(key_or_doi) → Item` — returns a single item by Zotero key or DOI
- `get_all_items() → [Item]` — returns full library (used by embedder sync)
- `Item` dataclass: `{key, title, abstract, authors, year, doi}`

### `embedder.py`
- Model: `BAAI/bge-small-en-v1.5` via `fastembed` (~130MB, local, first-run download)
- Embeds `title + " " + abstract` for each paper
- Persists embeddings in `~/LitLake/embeddings.db` using `sqlite-vec`
- **Auto-sync**: on every call, queries Zotero for items not yet in `embeddings.db` and embeds them before proceeding. New-item embedding is incremental — only unembedded items are processed. A `tqdm` progress bar is shown during sync: `Syncing N new papers [=====>  ] 14/47`. Silent if nothing to sync.
- `embed_text(text: str) → np.ndarray` — embed arbitrary text (for manuscript node and search queries)
- `get_embedding(zotero_key: str) → np.ndarray` — retrieve stored embedding
- `sync() → int` — embed all unembedded Zotero items; returns count of newly embedded items

### `manuscript.py`
- `parse_bibliography(path) → [Item]` — extract cited papers from PDF/DOCX/LaTeX; match to Zotero by DOI or title fuzzy match; return matched `Item` list with a flag for unmatched citations
- `extract_manuscript_text(path) → str` — extract title + abstract (or first ~500 words) for embedding as the manuscript node
- Supported formats: PDF (PyMuPDF), DOCX (python-docx), LaTeX (`.tex` file parsing `\bibitem` blocks, or `.bib` file parsing BibTeX entries directly)
- Manuscript text extraction: prefer explicit abstract section; fall back to first ~500 words of body text

### `layout.py`
- `compute_layout(embeddings, keys) → dict[key, (x, y)]` — UMAP to 2D; default params: `n_neighbors=15`, `min_dist=0.1`, `metric='cosine'`
- `build_graph(embeddings, keys, k=3) → list[(key_a, key_b, similarity)]` — k-NN graph via scikit-learn `NearestNeighbors`; edge weight = cosine similarity; self-edges excluded
- Both `n_neighbors` and `k` are CLI-configurable

### `search.py`
- `find_similar(query_embedding, scope_keys=None, top_k=10) → list[{key, similarity}]` — cosine similarity against `embeddings.db`; optional scope restricts to a collection or set of keys
- Returns results sorted descending by similarity; excludes the query item itself when query is a Zotero paper
- `--paper` with a title/DOI not found in Zotero: exits with a clear error message listing close title matches if any

### `renderer.py`
- `render_html(layout, graph, items, manuscript_key=None) → str` — Plotly figure with:
  - Nodes: scatter points coloured by continuous colormap mapped to UMAP x-coordinate (no separate clustering step required)
  - Edges: grey lines, alpha proportional to similarity weight
  - Manuscript node: star marker, distinct colour, always labelled
  - Hover: title, authors, year, similarity to manuscript (if present)
- `render_static(layout, graph, items, manuscript_key=None, path, dpi=300)` — matplotlib figure; labels via `adjustText` for non-overlapping placement; saves as PDF and PNG

---

## CLI Reference

```bash
# Visualization — four modes
litmap map --manuscript paper.pdf
  # Paper set: bibliography of manuscript. Manuscript node included.

litmap map --collection "My Papers"
  # Paper set: collection. No manuscript node.

litmap map --manuscript paper.pdf --collection "My Papers"
  # Paper set: collection. Manuscript node added.

litmap map --manuscript paper.pdf --collection "My Papers" --union
  # Paper set: collection ∪ bibliography. Manuscript node added.

# Common map flags
litmap map ... --output fig1          # base name for output files (fig1.html, fig1.pdf, fig1.png)
litmap map ... --n-neighbors 15       # UMAP n_neighbors
litmap map ... --edge-k 3             # k-NN edges per node
litmap map ... --format html          # html | pdf | png | all (default: all)

# Search
litmap search --query "sentence or passage"
litmap search --paper "Title or DOI"
litmap search ... --collection "My Papers"   # scope results to collection
litmap search ... --top-k 10                 # number of results (default: 10)
litmap search ... --format json              # machine-readable output for manuscript-audit

# Maintenance
litmap sync   # force full re-sync without running map or search
```

---

## Map Modes Detail

| Invocation | Paper set | Manuscript node |
|---|---|---|
| `--manuscript` only | Bibliography of manuscript (matched in Zotero) | Yes |
| `--collection` only | Named Zotero collection | No |
| `--manuscript` + `--collection` | Collection only | Yes |
| `--manuscript` + `--collection` + `--union` | Collection ∪ bibliography | Yes |

---

## JSON Output Schema (for `manuscript-audit` integration)

```json
{
  "query": "the query text or paper title",
  "results": [
    {
      "zotero_key": "ABC123",
      "title": "Paper title",
      "authors": ["Smith, J.", "Brown, K."],
      "year": "2020",
      "abstract": "...",
      "similarity": 0.87,
      "doi": "10.xxxx/xxxxx"
    }
  ]
}
```

---

## manuscript-audit Integration

Stage 2 (Citation Gap Detection) of `manuscript-audit` uses a revised three-tier search, with semantic search as the primary tier:

| Tier | Method | Runs when |
|---|---|---|
| 1 | **Semantic** — `litmap search --query` | Always (primary) |
| 2 | **Narrow keyword** — exact proper-noun pass | Always alongside Tier 1 |
| Fallback | **Full keyword** — metadata + full-text SQL | Only if `litmap` unavailable or returns zero results |

**Tier 1 — Semantic search (primary):**

```python
import subprocess, json

def semantic_search(claim_text: str, top_k: int = 5) -> list[dict]:
    result = subprocess.run(
        ["litmap", "search", "--query", claim_text,
         "--top-k", str(top_k), "--format", "json"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return []
    return json.loads(result.stdout).get("results", [])
```

**Tier 2 — Narrow keyword pass (proper nouns):**

Extract capitalised multi-word phrases, known method names, and species names from the claim (e.g., "MaxEnt", "*Homo sapiens*", "IPBES"). Run a focused SQL title/abstract `LIKE` query against Zotero for each. This catches exact-match papers that semantic compression may rank lower.

```python
import re

def extract_proper_nouns(text: str) -> list[str]:
    # Capitalised sequences of 1–3 words, acronyms, italicised terms
    return re.findall(r'\b[A-Z][A-Za-z]+(?:\s[A-Z][A-Za-z]+)?\b', text)

def keyword_exact(terms: list[str], conn) -> list[dict]:
    results = []
    for term in terms:
        rows = conn.execute("""
            SELECT i.key, tv.value, av.value FROM items i
            JOIN itemData td ON i.itemID = td.itemID AND td.fieldID = 1
            JOIN itemDataValues tv ON td.valueID = tv.valueID
            LEFT JOIN itemData ad ON i.itemID = ad.itemID AND ad.fieldID = 2
            LEFT JOIN itemDataValues av ON ad.valueID = av.valueID
            WHERE tv.value LIKE ? OR av.value LIKE ?
        """, (f'%{term}%', f'%{term}%')).fetchall()
        results.extend(rows)
    return results
```

**Merge and deduplicate:** combine Tier 1 + Tier 2 results, deduplicate by `zotero_key`, rank semantic hits first (by similarity score), append any Tier 2-only hits after.

**Fallback:** if `litmap` is not installed or returns a non-zero exit code, fall back to the original full metadata keyword search (Tier 1 old) and full-text index search (Tier 2 old).

Called for:
- Every unsupported or weakly supported claim (general gap detection)
- Every `(REFS)` placeholder (Step 0 of Stage 2)

---

## Embedding Cache (`embeddings.db`)

- Location: `~/LitLake/embeddings.db`
- Format: SQLite with `sqlite-vec` extension
- Schema:
  - `embeddings(zotero_key TEXT PRIMARY KEY, vector BLOB, embedded_at TIMESTAMP)`
  - `meta(key TEXT PRIMARY KEY, value TEXT)` — stores model name, version
- Auto-sync checks for Zotero items missing from `embeddings` table before each command
- `litmap sync` forces a full pass; useful after bulk Zotero imports

---

## Dependencies

| Package | Purpose |
|---|---|
| `fastembed` | Local embeddings (`BAAI/bge-small-en-v1.5`) |
| `sqlite-vec` | Vector storage + similarity search |
| `umap-learn` | Dimensionality reduction |
| `scikit-learn` | k-NN graph construction |
| `plotly` | Interactive HTML output |
| `matplotlib` | Static PNG/PDF output |
| `adjustText` | Non-overlapping labels in matplotlib |
| `pymupdf` | PDF text extraction |
| `python-docx` | DOCX parsing |
| `typer` | CLI framework |
| `tqdm` | Progress bar during auto-sync |
| `numpy`, `pandas` | Data handling |

**Prerequisites not yet installed:**
- `uv` (Python package manager) — must be installed first (`brew install uv` or `curl` installer)

---

## Out of Scope

- Background embedding daemon or queue worker
- MCP server / Claude Desktop integration (deliberate — this is a standalone CLI)
- Full-text PDF extraction for embeddings (title+abstract only; full-text is lit-lake's approach and adds significant complexity)
- Web UI
- Collaborative / multi-user support
