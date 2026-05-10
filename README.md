# litmap

A local Python CLI for semantic mapping and search over your [Zotero](https://www.zotero.org/) library. Generate interactive 2D maps of papers positioned by meaning, find papers similar to a query or focal paper, and understand how your manuscript sits within its citation landscape.

Everything runs locally — no background daemon, no network calls after the first model download, no opaque installers.

---

## Features

- **`litmap map`** — UMAP scatter plot of papers with k-nearest-neighbour edges, coloured by semantic position. Outputs interactive Plotly HTML and publication-quality PNG/PDF (300 DPI).
- **`litmap search`** — Cosine similarity search over your Zotero library for a query sentence, passage, or focal paper. Outputs a ranked table or JSON.
- **`litmap cluster`** — Hierarchical semantic clustering (≤2 levels) of a collection, bibliography, or the whole library. Outputs an interactive dendrogram (HTML), static dendrograms (PNG/PDF), a labelled outline (Markdown + JSON), and a `.linkage.npy` cache for downstream analyses.
- **`litmap sync`** — Manually trigger embedding of all Zotero items (title + abstract).
- **`litmap sync-fulltext`** — Embed full PDF text for all items with a local PDF attachment. Vectors are stored separately and automatically preferred over title+abstract embeddings in all commands. Safe to interrupt and resume.
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
git clone <this-repo> ~/your/path/litmap
cd ~/your/path/litmap
uv venv
uv pip install -e .
```

On first use, `sentence-transformers` downloads the `Alibaba-NLP/gte-modernbert-base` embedding model (~570 MB). Subsequent runs are fully offline. On Apple Silicon, inference uses Metal (MPS) automatically.

---

## Quick Start

`uv run litmap` must be run from inside the project directory (or a subdirectory). The easiest way to make it available everywhere is a shell alias:

```bash
echo 'alias litmap="uv run --project ~/your/path/litmap litmap"' >> ~/.zshrc
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

# Cluster a collection into a labelled semantic hierarchy
litmap cluster --collection "My Papers" --output ~/Desktop/clusters
```

Without the alias, prefix every command with `uv run` and run it from `~/your/path/litmap/`.

Open `litmap.html` in a browser for the interactive version. `litmap.png` and `litmap.pdf` are ready for publication.

See [docs/tutorial.md](docs/tutorial.md) for a full walkthrough.

---

## CLI Reference

### `litmap map`

```
Options:
  -c, --collection TEXT          Zotero collection name
  -m, --manuscript PATH          Manuscript file (PDF, DOCX, .bib, .tex)
      --union                    Use collection ∪ manuscript bibliography
  -o, --output PATH              Output base path [default: litmap_output]
      --n-neighbors INT          UMAP n_neighbors [default: 15]
      --edge-k INT               k-NN edges per node [default: 3]
  -f, --format TEXT              html | png | pdf | all [default: all]
      --label-clusters           Annotate HDBSCAN clusters with TF-IDF keywords [default: on]
      --no-label-clusters        Disable cluster annotations
      --min-cluster-size INT     HDBSCAN min_cluster_size [default: 5]
```

Cluster labels are generated automatically using HDBSCAN on the 2D layout coordinates, with each cluster labelled by its top-3 TF-IDF keyword phrases over member titles and abstracts. Noise points (papers HDBSCAN couldn't assign to a cluster) are left unlabelled. Use `--no-label-clusters` to disable, or `--min-cluster-size` to control cluster granularity — larger values produce fewer, broader clusters.

### `litmap search`

```
Options:
  -q, --query TEXT          Query sentence or passage
  -p, --paper TEXT          Title or DOI of a focal paper in your library
  -c, --collection TEXT     Scope search to a collection
  -k, --top-k INT           Number of results [default: 10]
  -f, --format TEXT         table | json [default: table]
```

### `litmap cluster`

```
Options:
  -c, --collection TEXT         Zotero collection name
  -m, --manuscript PATH         Manuscript file (PDF, DOCX, .bib, .tex)
      --union                   Use collection ∪ manuscript bibliography
      --top-clusters INT        Number of level-1 clusters [default: auto]
      --subcluster-threshold INT Min cluster size that triggers level-2 [default: 20]
  -o, --output PATH             Output base path [default: litmap_cluster]
  -f, --format TEXT             html | pdf | png | md | json | all [default: all]
```

Writes `<output>.html` (interactive dendrogram), `.pdf` + `.png` (static 300 DPI), `.md` + `.json` (labelled outline), and `.linkage.npy` (scipy linkage cache). If neither `--collection` nor `--manuscript` is given, the entire library is clustered. Level-1 cluster count defaults to `max(2, round(√(N/2)))`; any level-1 cluster with at least `--subcluster-threshold` papers is split into sub-clusters. Cluster labels are TF-IDF keyword triplets over title + abstract.

### `litmap info <paper>`

Show embedding status for a single paper. Accepts a title fragment, DOI, or Zotero key. Reports whether the paper has a title+abstract embedding, a full-text embedding, and if so how many tokens and chunks were used.

```bash
litmap info "Chung 2026"
litmap info 10.1038/s41586-024-12345-6
litmap info ABC12DEF
```

### `litmap sync`

Force re-sync of all Zotero items (title + abstract) into the embeddings cache. Normally runs automatically before every command.

### `litmap sync-fulltext`

```
Options:
      --max-tokens INT   Max tokens per chunk [default: 3000; up to 8000]
      --force            Re-embed even already-processed PDFs
```

Embeds the full text of every Zotero item that has a local PDF attachment. Text is extracted with PyMuPDF, split into non-overlapping chunks of `--max-tokens` tokens, encoded one chunk at a time (to avoid GPU OOM), and averaged into a single L2-normalised vector per paper. Vectors are stored in a separate `fulltext_embeddings` table and automatically preferred over title+abstract embeddings in `search`, `map`, and `cluster`. Papers without a local PDF fall back to title+abstract silently.

The job is safe to interrupt and resume — already-embedded papers are skipped unless `--force` is passed. To re-embed everything at a new token limit:

```bash
litmap sync-fulltext --max-tokens 3000 --force
```

Approximate throughput on Apple Silicon (MPS) on a MacBook Air M4: ~12 s/paper at 3000 tokens, ~100 s/paper at 8000 tokens. Encoding time scales roughly as O(n²) in token count because transformer attention computes interactions between every pair of tokens — doubling the sequence length roughly quadruples the compute. This makes 8000-token encoding disproportionately expensive; 3000 tokens is recommended.

**Choosing `--max-tokens`**

Token count maps roughly to 0.75 words, so 1000 tokens ≈ 750 words.

- **2000 tokens (~1500 words)** — full abstract and introduction. Captures topic framing and research questions; good for subject-area similarity.
- **3000 tokens (~2250 words)** — full abstract, introduction, and most of the methods. Adds methodological signal; recommended default.
- **8000 tokens (~6000 words)** — abstract through most of the results. Near-complete coverage for typical journal articles, but ~8× slower per paper due to quadratic attention scaling, and risks GPU OOM on machines with limited memory.

Papers shorter than `--max-tokens` are encoded in full regardless of the setting. For mixed libraries where speed matters, 3000 tokens is a good balance.

---

## Storage

`~/LitLake/embeddings.db` (SQLite) holds two tables: `embeddings` (title + abstract, ~3 KB/paper) and `fulltext_embeddings` (full text, ~3 KB/paper). The directory is created automatically on first run. Running both syncs on a library of ~16 000 papers with PDFs produces a database of roughly 100–150 MB.

---

## Architecture

```
litmap/
├── zotero.py      Read-only access to ~/Zotero/zotero.sqlite
├── embedder.py    sentence-transformers model + ~/LitLake/embeddings.db cache
├── layout.py      UMAP 2D layout + scikit-learn k-NN graph
├── search.py      Cosine similarity search + proper noun extraction
├── manuscript.py  Bibliography parser (PDF/DOCX/BibTeX/LaTeX)
├── renderer.py    Plotly HTML + matplotlib PNG/PDF (for `map`)
├── cluster.py     Hierarchical clustering, TF-IDF labelling, outline
├── cluster_render.py  Dendrograms (Plotly HTML + matplotlib) + outline renderers
└── cli.py         Typer CLI — map, search, cluster, sync, sync-fulltext
```

---

## Credits

- **[lit-lake](https://github.com/ElliotRoe/lit-lake)** by Elliot Roe — the original inspiration for this project. `litmap` replicates lit-lake's core embedding and search functionality as an auditable, dependency-light Python package, without the `.mcpb` installer or background daemon.
- **[Claude](https://claude.ai)** (Anthropic) — this codebase was designed and implemented using Claude (Cowork mode), including full-text PDF embedding, chunked encoding, and MPS memory management.
- **[sentence-transformers](https://www.sbert.net/)** + **[Alibaba-NLP/gte-modernbert-base](https://huggingface.co/Alibaba-NLP/gte-modernbert-base)** — local embedding inference; 768-dim GTE-ModernBERT (149M params, 8192-token context) with Metal GPU acceleration on Apple Silicon.
- **[UMAP](https://github.com/lmcinnes/umap)** — dimensionality reduction for the semantic layout.

---

## License

MIT
