# litmap Tutorial

This tutorial walks through the main workflows: searching your Zotero library semantically, generating paper maps, and using litmap alongside a manuscript in progress.

---

## 1. Setup

Install and add a shell alias so you can run `litmap` from any directory:

```bash
cd ~/src/Cowork/litmap
uv venv
uv pip install -e .

# Add a global alias (do this once)
echo 'alias litmap="uv run --project ~/src/Cowork/litmap litmap"' >> ~/.zshrc
source ~/.zshrc
```

Without the alias, `litmap` only works when your working directory is inside `~/src/Cowork/litmap/`. With the alias, `litmap` works from anywhere.

Then run the initial sync:

```bash
litmap sync
```

You will see a progress bar while `Alibaba-NLP/gte-modernbert-base` (~570 MB) downloads and your Zotero library is embedded. On Apple Silicon, embeddings run on the Metal GPU (MPS) automatically.

```
Syncing new papers: 100%|████████████████| 347/347 [01:23<00:00,  4.1 paper/s]
Embedded 347 new papers.
```

**Initial sync time:** The first sync embeds your entire Zotero library and only needs to run once. On a MacBook Air M4, embedding ~31,000 papers took approximately 6.5 hours. The Air throttles the CPU and GPU to manage heat, so throughput drops significantly after the first ~10,000 papers (from >100 papers/s down to ~10 papers/s). Incremental syncs — adding newly downloaded papers — are fast because they only process items not already in the cache, and those run before the chip has a chance to throttle.

---

## 2. Searching Your Library

### Find papers similar to a sentence

```bash
litmap search --query "deep learning models for species distribution modelling"
```

Output:
```
 1. [0.921] Machine learning in species distribution modelling
     Valavi, Roozbeh, Elith, Jane 2022  10.1111/geb.13476
 2. [0.908] A comparison of machine learning methods for modelling ...
     Norberg, Anna 2019  10.1111/ecog.04547
 3. [0.893] Spatially transferable species distribution models
     ...
```

Scores range 0–1. Anything above ~0.85 is a strong semantic match.

### Scope to a collection

If you only want results from a particular Zotero collection:

```bash
litmap search \
  --query "carbon sequestration tropical forests" \
  --collection "Chapter 2 refs" \
  --top-k 5
```

### Search from a focal paper

Find what else in your library is similar to a paper you already know:

```bash
litmap search --paper "10.1126/science.1256014"
# or by title:
litmap search --paper "Sensing biodiversity"
```

The focal paper is excluded from its own results. If the title isn't an exact match, litmap suggests close alternatives.

### Machine-readable output

For scripting or use with other tools (e.g. the `manuscript-audit` skill):

```bash
litmap search \
  --query "functional diversity trait-based ecology" \
  --format json | jq '.results[].title'
```

---

## 3. Mapping a Zotero Collection

```bash
litmap map \
  --collection "My Papers" \
  --output ~/Desktop/litmap_collection
```

This writes three files:

| File | Use |
|---|---|
| `litmap_collection.html` | Interactive browser map — hover for title/author/year, pan and zoom |
| `litmap_collection.png` | 300 DPI raster for presentations or supplementary material |
| `litmap_collection.pdf` | Vector format for journal submission |

Open the HTML file in any browser. Each node is a paper; edges connect the k nearest semantic neighbours. Colour runs along the x-axis (viridis palette) — papers at opposite ends of the colour scale are semantically distant.

### Adjusting layout density

```bash
# Tighter clusters (good for large libraries)
litmap map --collection "My Papers" --n-neighbors 30 --output ~/Desktop/dense

# Sparser graph edges
litmap map --collection "My Papers" --edge-k 2 --output ~/Desktop/sparse
```

`--n-neighbors` controls the UMAP global structure (higher = broader view of neighbourhood). `--edge-k` controls how many edges each node draws.

---

## 4. Mapping a Manuscript's Bibliography

If you have a PDF, DOCX, `.bib`, or `.tex` file, litmap extracts its references and maps only the papers it can match in your Zotero library.

```bash
litmap map \
  --manuscript ~/Documents/my_paper.pdf \
  --output ~/Desktop/litmap_bib
```

This is useful for checking the semantic coverage of your citations — do they cluster around one topic, or spread across the field?

---

## 5. Manuscript + Collection Maps

The most informative workflow: position your manuscript *within* its citation landscape.

### Mode A — Collection only, manuscript shown as a node

Your manuscript appears as a red star at its semantic position among the collection papers. You can see which "neighbourhood" of the literature your paper falls in.

```bash
litmap map \
  --collection "My Papers" \
  --manuscript ~/Documents/my_paper.pdf \
  --output ~/Desktop/litmap_positioned
```

### Mode B — Bibliography only

Map just the papers you cited, with your manuscript at the centre.

```bash
litmap map \
  --manuscript ~/Documents/my_paper.pdf \
  --output ~/Desktop/litmap_bib_only
```

### Mode C — Union (collection + bibliography)

Include every paper in the collection *plus* any additional papers from your bibliography not already in the collection. The manuscript node is added too.

```bash
litmap map \
  --collection "My Papers" \
  --manuscript ~/Documents/my_paper.pdf \
  --union \
  --output ~/Desktop/litmap_union
```

This is the most complete view: the full collection provides context, and any papers you cited outside the collection appear as additions.

---

## 6. Clustering a Paper Set

`litmap cluster` groups papers into a labelled semantic hierarchy (up to two levels) and produces both a **dendrogram** (for visual inspection) and an **outline** (for reading).

### Cluster a collection

```bash
litmap cluster \
  --collection "My Papers" \
  --output ~/Desktop/litmap_clusters
```

This writes six files:

| File | Use |
|---|---|
| `litmap_clusters.html` | Interactive dendrogram — hover on a leaf to see title and Zotero key |
| `litmap_clusters.png` / `.pdf` | Static dendrogram, 300 DPI |
| `litmap_clusters.md` | Human-readable outline: each cluster labelled by TF-IDF keywords, members listed as short references |
| `litmap_clusters.json` | Machine-readable outline (same structure), ready for scripting |
| `litmap_clusters.linkage.npy` | scipy linkage cache — skip re-clustering in downstream analyses |

The Markdown outline looks like this:

```markdown
# litmap cluster — My Papers (74 papers)

## 1. species · distribution · modelling  (28 papers)
- Valavi et al. 2022 — *Predictive performance of presence-only SDMs*
- Norberg 2019 — *A comprehensive evaluation of predictive performance of 33 SDMs*
  [in: Chapter 2]
...

## 2. genome · sequencing · annotation  (14 papers)
...
```

### Cluster a manuscript's bibliography

```bash
litmap cluster \
  --manuscript ~/Documents/my_paper.pdf \
  --output ~/Desktop/bib_clusters
```

Useful for building a discussion section outline: the clusters reveal the thematic groupings implicit in what you cited.

### Tuning the hierarchy

```bash
# Force exactly 5 top-level clusters
litmap cluster --collection "My Papers" --top-clusters 5 --output ~/Desktop/c5

# Split any cluster with 10+ papers into sub-clusters (default threshold: 20)
litmap cluster --collection "My Papers" --subcluster-threshold 10 --output ~/Desktop/deep
```

`--top-clusters` defaults to `max(2, round(√(N/2)))` — about 6 clusters for a 72-paper collection, 12 for a 288-paper collection. Papers in any level-1 cluster whose size ≥ `--subcluster-threshold` are recursively split into `max(2, round(√(size/2)))` sub-clusters.

### Cluster the entire library

If you omit both `--collection` and `--manuscript`, litmap clusters every non-attachment item in your Zotero library. For a 30k-paper library, expect the clustering step itself to take a minute or two.

```bash
litmap cluster --output ~/Desktop/full_library_clusters
```

### Existing Zotero sub-collections

If papers already belong to Zotero sub-collections, those are listed in the outline as `[in: Sub-Collection Name]` alongside each entry. This lets you compare litmap's semantic grouping against your manual curation — handy before deciding whether to reorganise.

### Picking just one format

Same as `litmap map`:

```bash
# Outline only, no dendrogram
litmap cluster --collection "My Papers" --format md --output ~/Desktop/outline

# Interactive dendrogram only
litmap cluster --collection "My Papers" --format html --output ~/Desktop/dendro
```

---

## 7. Only Generating One Output Format

By default `--format all` writes HTML + PNG + PDF. To save time:

```bash
# Interactive HTML only (fastest)
litmap map --collection "My Papers" --format html --output ~/Desktop/map

# Static files only (no Plotly overhead)
litmap map --collection "My Papers" --format png --output ~/Desktop/map
```

---

## 8. Using litmap with the manuscript-audit Skill

If you use the `manuscript-audit` skill in Claude, it automatically calls `litmap search` during Stage 2 (citation gap detection) to find semantically relevant papers for unsupported claims. It falls back to keyword search if litmap is unavailable.

To check it's wired up correctly:

```bash
litmap search \
  --query "biodiversity loss accelerating globally" \
  --format json
```

If this returns valid JSON, the skill will use it.

---

## 9. Keeping the Embedding Cache Up to Date

The cache updates automatically at the start of every command. When you add papers to Zotero, the next `litmap` invocation will embed them:

```
Syncing new papers: 100%|████| 12/12 [00:03<00:00,  3.8 paper/s]
```

If Zotero is already up to date, nothing is printed and the command proceeds immediately. Incremental syncs are fast — a few dozen new papers takes seconds, well before any thermal throttling kicks in.

To force a manual sync at any time:

```bash
litmap sync
```

---

## Tips

- **Large libraries (1000+ papers):** `litmap map` can take 30–60 seconds for the UMAP step. Use `--format html` to skip the matplotlib render if you only need the interactive version.
- **BibTeX input:** `litmap map --manuscript refs.bib` and `litmap search` both work with `.bib` files — useful if you're writing in LaTeX and want to check coverage before submission.
- **The embedding model is local:** after first download, all commands work offline. No API keys, no rate limits.
- **Zotero does not need to be running:** litmap reads `~/Zotero/zotero.sqlite` directly in read-only mode.
