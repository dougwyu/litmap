# litmap

A local Python CLI for semantic mapping and search over your [Zotero](https://www.zotero.org/) library. Generate interactive 2D maps of papers positioned by meaning, find papers similar to a query or focal paper, and understand how your manuscript sits within its citation landscape.

Everything runs locally — no background daemon, no network calls after the first model download, no opaque installers.

---

## Features

- **`litmap map`** — UMAP scatter plot of papers with k-nearest-neighbour edges, coloured by semantic position. Outputs interactive Plotly HTML and publication-quality PNG/PDF (300 DPI).
- **`litmap search`** — Cosine similarity search over your Zotero library for a query sentence, passage, or focal paper. Outputs a ranked table or JSON.
- **`litmap sync`** — Manually trigger embedding of all Zotero items.
- **Auto-sync** — Every command automatically embeds any Zotero items not yet in the cache before running. A `tqdm` progress bar appears during sync; silent if already up to date.
- **Four map modes** — collection only, manuscript bibliography only, intersection, or full union.
- **Manuscript node** — When `--manuscript` is provided, your paper appears as a red star in the map, positioned semantically among its cited works.

---

## Requirements

- Python 3.11–3.13
- [uv](https://github.com/astral-sh/uv) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Zotero installed with a library at `~/Zotero/zotero.sqlite`

---

## Installation

```bash
git clone <this-repo> ~/src/Cowork/litmap
cd ~/src/Cowork/litmap
uv venv
uv pip install -e .
```

On first use, `sentence-transformers` downloads the `Alibaba-NLP/gte-modernbert-base` embedding model (~570 MB). Subsequent runs are fully offline. On Apple Silicon, inference uses Metal (MPS) automatically.

---

## Quick Start

`uv run litmap` must be run from inside the project directory (or a subdirectory). The easiest way to make it available everywhere is a shell alias:

```bash
echo 'alias litmap="uv run --project ~/src/Cowork/litmap litmap"' >> ~/.zshrc
source ~/.zshrc
```

After that, you can run `litmap` from anywhere:

```bash
# Search your library
litmap search --query "biodiversity measurement remote sensing" --top-k 5

# Map a Zotero collection
litmap map --collection "My Papers" --output ~/Desktop/litmap

# Map a manuscript's bibliography
litmap map --manuscript paper.pdf --output ~/Desktop/litmap

# Map a manuscript positioned within its cited collection
litmap map --collection "My Papers" --manuscript paper.pdf --output ~/Desktop/litmap
```

Without the alias, prefix every command with `uv run` and run it from `~/src/Cowork/litmap/`.

Open `litmap.html` in a browser for the interactive version. `litmap.png` and `litmap.pdf` are ready for publication.

See [docs/tutorial.md](docs/tutorial.md) for a full walkthrough.

---

## CLI Reference

### `litmap map`

```
Options:
  -c, --collection TEXT     Zotero collection name
  -m, --manuscript PATH     Manuscript file (PDF, DOCX, .bib, .tex)
      --union               Use collection ∪ manuscript bibliography
  -o, --output PATH         Output base path [default: litmap_output]
      --n-neighbors INT     UMAP n_neighbors [default: 15]
      --edge-k INT          k-NN edges per node [default: 3]
  -f, --format TEXT         html | png | pdf | all [default: all]
```

### `litmap search`

```
Options:
  -q, --query TEXT          Query sentence or passage
  -p, --paper TEXT          Title or DOI of a focal paper in your library
  -c, --collection TEXT     Scope search to a collection
  -k, --top-k INT           Number of results [default: 10]
  -f, --format TEXT         table | json [default: table]
```

### `litmap sync`

Force re-sync of all Zotero items (normally runs automatically).

---

## Storage

Embeddings are stored in `~/LitLake/embeddings.db` (SQLite, ~1 KB per paper). The directory is created automatically on first run.

---

## Architecture

```
litmap/
├── zotero.py      Read-only access to ~/Zotero/zotero.sqlite
├── embedder.py    sentence-transformers model + ~/LitLake/embeddings.db cache
├── layout.py      UMAP 2D layout + scikit-learn k-NN graph
├── search.py      Cosine similarity search + proper noun extraction
├── manuscript.py  Bibliography parser (PDF/DOCX/BibTeX/LaTeX)
├── renderer.py    Plotly HTML + matplotlib PNG/PDF
└── cli.py         Typer CLI — map, search, sync
```

---

## Credits

- **[lit-lake](https://github.com/ElliotRoe/lit-lake)** by Elliot Roe — the original inspiration for this project. `litmap` replicates lit-lake's core embedding and search functionality as an auditable, dependency-light Python package, without the `.mcpb` installer or background daemon.
- **[Claude](https://claude.ai)** (Anthropic) — this codebase was designed and implemented in a single session using Claude Code with the [Superpowers](https://github.com/superpowers) skill system for structured TDD and subagent-driven development.
- **[sentence-transformers](https://www.sbert.net/)** + **[Alibaba-NLP/gte-modernbert-base](https://huggingface.co/Alibaba-NLP/gte-modernbert-base)** — local embedding inference; 768-dim GTE-ModernBERT (149M params, 8192-token context) with Metal GPU acceleration on Apple Silicon.
- **[UMAP](https://github.com/lmcinnes/umap)** — dimensionality reduction for the semantic layout.

---

## License

MIT
