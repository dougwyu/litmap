# litmap

A local Python CLI for semantic mapping and search over your [Zotero](https://www.zotero.org/) library. Generate interactive 2D maps of papers positioned by meaning, find papers similar to a query or focal paper, and understand how your manuscript sits within its citation landscape.

Everything runs locally — no background daemon, no network calls after the first model download, no opaque installers.

---

## Features

- **`litmap map`** — UMAP scatter plot of papers with k-nearest-neighbour edges, coloured by semantic position. Cluster labels generated automatically via HDBSCAN + TF-IDF. Outputs interactive Plotly HTML and publication-quality PNG/PDF (300 DPI).
- **`litmap search`** — Cosine similarity search over your Zotero library for a query sentence, passage, or focal paper. Uses full-text embeddings when available, otherwise title+abstract. Outputs a ranked table or JSON.
- **`litmap cluster`** — Hierarchical semantic clustering (≤2 levels) of a collection, bibliography, or the whole library. Outputs an interactive dendrogram (HTML), static dendrograms (PNG/PDF), a labelled outline (Markdown + JSON), and a `.linkage.npy` cache for downstream analyses.
- **`litmap info`** — Show embedding status for a single paper.
- **`litmap sync`** — Manually trigger title+abstract embedding of all Zotero items.
- **`litmap sync-fulltext`** — Embed full PDF text for items with a local PDF. Vectors are stored separately and automatically preferred over title+abstract embeddings in all commands. Safe to interrupt and resume.
- **Auto-sync** — Every command automatically embeds any Zotero items not yet in the cache before running. A `tqdm` progress bar appears during sync; silent if already up to date.
- **Four map modes** — collection only, manuscript bibliography only, intersection, or full union.
- **Manuscript node** — When `--manuscript` is provided, your paper appears as a red star in the map, positioned semantically among its cited works. Papers in the library that have the manuscript among their k nearest neighbours in embedding space will also draw edges to it, so the manuscript typically accumulates more edges than regular nodes.

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

Requires at least one of `--collection` or `--manuscript`.

```
Options:
  -c, --collection TEXT          Zotero collection name
  -m, --manuscript PATH          Manuscript file (PDF, DOCX, .bib, .tex)
      --union                    Use collection ∪ manuscript bibliography
  -o, --output PATH              Output base path [default: litmap_output]
      --n-neighbors INT          UMAP n_neighbors [default: 3]
      --edge-k INT               k-NN edges per node [default: 3]
  -f, --format TEXT              html | png | pdf | all [default: all]
      --label-clusters           Annotate HDBSCAN clusters with TF-IDF keywords [default: on]
      --no-label-clusters        Disable cluster annotations
      --min-cluster-size INT     HDBSCAN min_cluster_size [default: 5]
```

**Paper set.** The paper set depends on which flags are provided:

- `--collection` only — maps papers in the collection.
- `--manuscript` only — parses the manuscript bibliography and maps those papers.
- `--collection --manuscript` (no `--union`) — maps the collection only, with the manuscript added as a red star node.
- `--collection --manuscript --union` — maps the union of the collection and the manuscript bibliography, with the manuscript as a red star node.

**Layout.** UMAP reduces the high-dimensional embedding vectors to 2D. `--n-neighbors` controls how many neighbours each point considers: lower values (e.g. 3) produce tighter, more separated clusters by emphasising local structure; higher values (e.g. 30–50) produce smoother, more globally coherent layouts.

**Edges.** Each paper is connected to its `--edge-k` nearest neighbours in embedding space. In the static PNG/PDF output, edge opacity is weighted by cosine similarity — darker edges indicate stronger semantic overlap. The manuscript node (red star) accumulates both its own outgoing edges and incoming edges from papers that count it among their nearest neighbours, so it typically has more connections than regular nodes.

**Cluster labels.** Generated automatically by running HDBSCAN on the 2D layout coordinates, then labelling each cluster with its top-3 TF-IDF keyword phrases. Title and abstract are used as the TF-IDF corpus (full PDF text produces noisy labels from reference lists and boilerplate). Noise points (papers HDBSCAN couldn't assign to any cluster) are left unlabelled. Labels are rendered in dark teal with a white background box. Use `--no-label-clusters` to disable, or `--min-cluster-size` to control granularity — larger values produce fewer, broader clusters.

### `litmap search`

Requires either `--query` or `--paper`.

```
Options:
  -q, --query TEXT          Query sentence or passage
  -p, --paper TEXT          Title or DOI of a focal paper in your library
  -c, --collection TEXT     Scope search to a collection
  -k, --top-k INT           Number of results [default: 10]
  -f, --format TEXT         table | json [default: table]
```

Searches using full-text embeddings when available, falling back to title+abstract per paper. Provide either `--query` (free text) or `--paper` (title fragment or DOI of a paper already in your library). When using `--paper`, the focal paper itself is excluded from results. Results are deduplicated by DOI before returning.

### `litmap cluster`

```
Options:
  -c, --collection TEXT          Zotero collection name
  -m, --manuscript PATH          Manuscript file (PDF, DOCX, .bib, .tex)
      --union                    Use collection ∪ bibliography as paper set
      --top-clusters INT         Number of level-1 clusters [default: auto]
      --subcluster-threshold INT Min cluster size that triggers level-2 [default: 20]
  -o, --output PATH              Output base path [default: litmap_cluster]
  -f, --format TEXT              html | pdf | png | md | json | all [default: all]
```

Writes `<output>.html` (interactive dendrogram), `.pdf` + `.png` (static 300 DPI), `.md` + `.json` (labelled outline), and `.linkage.npy` (scipy linkage cache). If neither `--collection` nor `--manuscript` is given, the entire library is clustered. If both are given, `--union` is required.

Level-1 cluster count defaults to `max(2, round(sqrt(N/2)))`; any level-1 cluster with at least `--subcluster-threshold` papers is split into sub-clusters. Cluster labels are TF-IDF keyword triplets derived from member title and abstract text.

### `litmap info <paper>`

Show embedding status for a single paper. Accepts a title fragment, DOI, or Zotero key. Reports the PDF path, whether a title+abstract embedding exists, and whether a full-text embedding exists (with token count and chunk count).

```bash
litmap info "Chung 2026"
litmap info 10.1038/s41586-024-12345-6
litmap info ABC12DEF
```

### `litmap sync`

```
Options:
      --force    Re-embed all papers, even those already in the cache
```

Embed all Zotero items (title + abstract) not yet in the cache. Runs automatically before every command, so manual invocation is rarely needed. Use `--force` to regenerate all embeddings (e.g. after switching models).

### `litmap sync-fulltext`

```
Options:
  -c, --collection TEXT  Scope to a Zotero collection
      --max-tokens INT   Max tokens per chunk [default: 3000; up to 8000]
      --force            Re-embed even already-processed PDFs
```

Embeds the full text of every Zotero item that has a local PDF attachment. Text is extracted with PyMuPDF, split into non-overlapping chunks of `--max-tokens` tokens, and encoded one chunk at a time on MPS (to avoid GPU OOM on long documents). The chunk vectors are averaged and L2-normalised into a single 768-dimensional vector per paper. Vectors are stored in the `fulltext_embeddings` table and automatically preferred over title+abstract embeddings in `search`, `map`, and `cluster`. Papers without a local PDF fall back to title+abstract silently.

The job is safe to interrupt and resume — already-embedded papers are skipped unless `--force` is passed. Use `--collection` to scope the run to a single collection (works for both personal and group library collections), which is useful for testing higher token counts on a smaller set before committing to a full-library run.

```bash
# Embed a single collection at higher quality
litmap sync-fulltext --collection "My Papers" --max-tokens 6000

# Re-embed a collection at 8000 tokens for richer semantic content
litmap sync-fulltext --collection "My Papers" --max-tokens 8000 --force

# Re-embed everything at a new token limit
litmap sync-fulltext --max-tokens 3000 --force
```

A common workflow is to run the full library at 3000 tokens, then re-embed the specific collection you are actively working with at 8000 tokens. This gives richer semantic content for that collection — improving results from `litmap map`, `litmap cluster`, and `litmap search` — without the time cost of re-embedding your entire library.

Approximate throughput on Apple Silicon (MPS) on a MacBook Air M4: ~12 s/paper at 3000 tokens, ~100 s/paper at 8000 tokens. Encoding time scales roughly as O(n^2) in token count because transformer attention computes interactions between every pair of tokens — doubling the sequence length roughly quadruples the compute. This makes 8000-token encoding disproportionately expensive; 3000 tokens is recommended.

**Choosing `--max-tokens`**

Token count maps roughly to 0.75 words, so 1000 tokens ≈ 750 words.

- **2000 tokens (~1500 words)** — full abstract and introduction. Captures topic framing and research questions; good for subject-area similarity.
- **3000 tokens (~2250 words)** — full abstract, introduction, and most of the methods. Adds methodological signal; recommended default.
- **8000 tokens (~6000 words)** — abstract through most of the results. Near-complete coverage for typical journal articles, but ~8x slower per paper due to quadratic attention scaling, and risks GPU OOM on machines with limited memory.

Papers shorter than `--max-tokens` are encoded in full regardless of the setting.

---

## Storage

Embeddings are stored in `~/LitLake/embeddings.db` (SQLite), created automatically on first run. The database holds two tables:

- **`embeddings`** — title + abstract vectors. One row per Zotero item, ~3 KB each. Populated by `litmap sync` and auto-sync.
- **`fulltext_embeddings`** — full-text vectors. One row per item with a local PDF, also ~3 KB each (the vector is always 768 float32 values regardless of how many chunks were averaged). Also stores `n_tokens` and `n_chunks` per paper, queryable via `litmap info` or directly with `sqlite3`.

All commands prefer full-text vectors when available and fall back to title+abstract per paper — the two tables can be populated independently and at different token limits.

Approximate database sizes for a library of ~16,000 items with PDFs: `embeddings` ~50 MB, `fulltext_embeddings` ~170 MB, total ~220 MB.

To inspect coverage:

```bash
sqlite3 ~/LitLake/embeddings.db "
SELECT
  (SELECT COUNT(*) FROM embeddings) AS title_abstract_embedded,
  (SELECT COUNT(*) FROM fulltext_embeddings) AS fulltext_embedded,
  (SELECT AVG(n_tokens) FROM fulltext_embeddings) AS avg_tokens,
  (SELECT SUM(CASE WHEN n_chunks > 1 THEN 1 ELSE 0 END)
   FROM fulltext_embeddings) AS multi_chunk_papers;"
```

---

## Scripts

### `scripts/manuscript_to_bib.py`

Export a BibTeX file of all papers cited in a manuscript, matched against your Zotero library.

```bash
uv run scripts/manuscript_to_bib.py manuscript.docx refs.bib
uv run scripts/manuscript_to_bib.py manuscript.docx refs.bib --zotero-db ~/Zotero/zotero.sqlite
```

Works with two document types:

- **Word documents with live Zotero field codes** — citations inserted via the Zotero Word or Google Docs plugin, not yet unlinked. Keys are extracted directly from the field code JSON and matched exactly.
- **Google Docs exports (Download as .docx)** — field codes are stripped on export, so the script falls back to extracting `https://doi.org/` links from the Zotero-generated bibliography and matching them against Zotero by DOI. Requires the document to contain a Zotero bibliography that includes DOI numbers (e.g. Methods in Ecology & Evolution style).

The script tries field codes first and falls back to DOI extraction automatically. Output is a `.bib` file importable via Zotero **File → Import**. Errors if the output file already exists.

---

## Architecture

```
litmap/
├── zotero.py          Read-only access to ~/Zotero/zotero.sqlite; resolves PDF paths
├── embedder.py        Embedding model, embeddings.db cache, fulltext pipeline
├── layout.py          UMAP 2D layout + HDBSCAN cluster labels + k-NN graph
├── search.py          Cosine similarity search + deduplication
├── manuscript.py      Bibliography parser (PDF/DOCX/BibTeX/LaTeX)
├── renderer.py        Plotly HTML + matplotlib PNG/PDF (for `map`)
├── cluster.py         Hierarchical clustering, TF-IDF labelling, outline builder
├── cluster_render.py  Dendrograms (Plotly HTML + matplotlib) + outline renderers
├── cli.py             Typer CLI — map, search, cluster, sync, sync-fulltext, info
└── scripts/
    └── manuscript_to_bib.py  Export cited papers to BibTeX (Google Docs + Word)
```

---

## Credits

- **[lit-lake](https://github.com/ElliotRoe/lit-lake)** by Elliot Roe — the original inspiration for this project. `litmap` replicates lit-lake's core embedding and search functionality as an auditable, dependency-light Python package, without the `.mcpb` installer or background daemon.
- **[Claude](https://claude.ai)** (Anthropic) — this codebase was designed and implemented using Claude (Cowork mode), including full-text PDF embedding, chunked encoding, MPS memory management, and HDBSCAN cluster labelling.
- **[sentence-transformers](https://www.sbert.net/)** + **[Alibaba-NLP/gte-modernbert-base](https://huggingface.co/Alibaba-NLP/gte-modernbert-base)** — local embedding inference; 768-dim GTE-ModernBERT (149M params, 8192-token context) with Metal GPU acceleration on Apple Silicon.
- **[UMAP](https://github.com/lmcinnes/umap)** — dimensionality reduction for the semantic layout.
- **[HDBSCAN](https://scikit-learn.org/stable/modules/clustering.html#hdbscan)** (via scikit-learn) — unsupervised clustering for map annotations.

---

## License

MIT
