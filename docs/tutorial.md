# litmap Tutorial

This tutorial walks through the main workflows: searching your Zotero library semantically, generating paper maps, clustering a collection, and using litmap alongside a manuscript in progress.

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

**Initial sync time:** The first sync embeds your entire Zotero library using title and abstract and only needs to run once. On a MacBook Air M4, embedding ~31,000 papers took approximately 6.5 hours. The Air throttles the CPU and GPU to manage heat, so throughput drops significantly after the first ~10,000 papers (from >100 papers/s down to ~10 papers/s). Incremental syncs are fast because they only process items not already in the cache.

---

## 2. Full-text Embedding

Title and abstract embeddings are quick to compute but capture limited semantic detail. For better search, map, and cluster quality, embed the full PDF text:

```bash
litmap sync-fulltext
```

This reads each paper's local PDF, extracts the text, and stores a full-text vector alongside the title+abstract vector. All commands automatically prefer full-text embeddings when available, falling back to title+abstract per paper.

**Throughput on Apple Silicon (M4):** ~12 s/paper at 3000 tokens (default), ~100 s/paper at 8000 tokens. At 3000 tokens, a 13,000-paper library takes roughly 45 hours. The database grows to approximately 170 MB for the fulltext table.

### Recommended workflow

Run the full library at the default token count, then re-embed the collection you are actively working with at higher quality:

```bash
# Step 1: embed the full library (takes time; safe to interrupt and resume)
litmap sync-fulltext

# Step 2: re-embed your active collection at higher quality
litmap sync-fulltext --collection Credible_Bib --max-tokens 8000 --force
```

`--force` with `--collection` only re-embeds papers in that collection — the rest of the library is untouched. This gives richer semantic content for your active collection without re-processing everything.

### Checking a paper's embedding status

```bash
litmap info "Chung 2026"
litmap info 10.1038/s41586-024-12345-6
litmap info ABC12DEF
```

Output:

```
Title:      Credible biodiversity metrics for high-integrity nature markets
Authors:    Chung et al.
Year:       2026
DOI:        10.1111/...
Zotero key: ABC12DEF
PDF:        /Users/you/Zotero/storage/ABC12DEF/Chung2026.pdf

Title+abstract embedded: yes, 2026-05-01
Full-text embedded:      yes, 2026-05-10 (3201 tokens, 2 chunks)
```

---

## 3. Searching Your Library

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
```

Scores range 0–1. Anything above ~0.85 is a strong semantic match.

### Scope to a collection

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
# or by title fragment:
litmap search --paper "Sensing biodiversity"
```

The focal paper is excluded from its own results. If the title isn't an exact match, litmap suggests close alternatives.

### Machine-readable output

```bash
litmap search \
  --query "functional diversity trait-based ecology" \
  --format json | jq '.results[].title'
```

---

## 4. Mapping a Zotero Collection

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

Open the HTML file in any browser. Each node is a paper; edges connect the k nearest semantic neighbours. Colour runs along the x-axis (viridis palette) — papers at opposite ends of the colour scale are semantically distant. Cluster labels (TF-IDF keywords from title and abstract) appear in dark teal boxes.

### Adjusting layout density

`--n-neighbors` controls UMAP's neighbourhood size. Lower values (e.g. 3, the default) produce tighter, more separated clusters by emphasising local structure. Higher values (e.g. 30–50) produce smoother, more globally coherent layouts.

```bash
# Default: tight local clusters
litmap map --collection "My Papers" --output ~/Desktop/tight

# Broader, more global layout
litmap map --collection "My Papers" --n-neighbors 30 --output ~/Desktop/broad

# Fewer graph edges
litmap map --collection "My Papers" --edge-k 2 --output ~/Desktop/sparse
```

---

## 5. Mapping a Manuscript's Bibliography

If you have a PDF, DOCX, `.bib`, or `.tex` file, litmap extracts its references and maps only the papers it can match in your Zotero library.

```bash
litmap map \
  --manuscript ~/Documents/my_paper.pdf \
  --output ~/Desktop/litmap_bib
```

This is useful for checking the semantic coverage of your citations — do they cluster around one topic, or spread across the field?

---

## 6. Manuscript + Collection Maps

The most informative workflow: position your manuscript *within* its citation landscape.

### Mode A — Collection only, manuscript shown as a node

Your manuscript appears as a red star at its semantic position among the collection papers. You can see which "neighbourhood" of the literature your paper falls in.

```bash
litmap map \
  --collection "My Papers" \
  --manuscript ~/Documents/my_paper.pdf \
  --output ~/Desktop/litmap_positioned
```

Use `--center-manuscript` to bias the manuscript node toward the centre of the layout. UMAP still optimises its final position based on actual embedding distances, so the result is semantically honest — the init position just biases it centrally when the data permits:

```bash
litmap map \
  --collection "My Papers" \
  --manuscript ~/Documents/my_paper.pdf \
  --center-manuscript \
  --output ~/Desktop/litmap_centered
```

### Mode B — Bibliography only

Map just the papers you cited, with your manuscript as an additional node.

```bash
litmap map \
  --manuscript ~/Documents/my_paper.pdf \
  --output ~/Desktop/litmap_bib_only
```

### Mode C — Union (collection + bibliography)

Include every paper in the collection *plus* any additional papers from your bibliography not already in the collection.

```bash
litmap map \
  --collection "My Papers" \
  --manuscript ~/Documents/my_paper.pdf \
  --union \
  --output ~/Desktop/litmap_union
```

---

## 7. Clustering a Paper Set

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
```

### Cluster a manuscript's bibliography

```bash
litmap cluster \
  --manuscript ~/Documents/my_paper.pdf \
  --output ~/Desktop/bib_clusters
```

Useful for building a discussion section outline: the clusters reveal the thematic groupings implicit in what you cited.

### Cluster both a collection and a bibliography

```bash
litmap cluster \
  --collection "My Papers" \
  --manuscript ~/Documents/my_paper.pdf \
  --union \
  --output ~/Desktop/union_clusters
```

`--union` is required when both `--collection` and `--manuscript` are provided.

### Tuning the hierarchy

```bash
# Force exactly 5 top-level clusters
litmap cluster --collection "My Papers" --top-clusters 5 --output ~/Desktop/c5

# Split any cluster with 10+ papers into sub-clusters (default threshold: 20)
litmap cluster --collection "My Papers" --subcluster-threshold 10 --output ~/Desktop/deep
```

`--top-clusters` defaults to `max(2, round(sqrt(N/2)))` — about 6 clusters for a 72-paper collection, 12 for a 288-paper collection.

### Cluster the entire library

If you omit both `--collection` and `--manuscript`, litmap clusters every item in your Zotero library:

```bash
litmap cluster --output ~/Desktop/full_library_clusters
```

### Picking just one format

```bash
# Outline only, no dendrogram
litmap cluster --collection "My Papers" --format md --output ~/Desktop/outline

# Interactive dendrogram only
litmap cluster --collection "My Papers" --format html --output ~/Desktop/dendro
```

---

## 8. Exporting a Bibliography from a Manuscript

`scripts/manuscript_to_bib.py` extracts Zotero citations from a manuscript and exports a `.bib` file you can import into Zotero — useful for creating a collection from a paper's reference list.

```bash
uv run scripts/manuscript_to_bib.py my_paper.docx refs.bib
```

Works with two document types:

- **Word documents with live Zotero field codes** — keys extracted directly from the field code JSON.
- **Google Docs exports (.docx)** — field codes are stripped on export, so the script falls back to DOI extraction from the bibliography. Requires a Zotero bibliography that includes DOI numbers (e.g. Methods in Ecology & Evolution style).

The script tries field codes first and falls back to DOI extraction automatically. To import the result: Zotero → File → Import → select the `.bib` file.

---

## 9. Only Generating One Output Format

By default `--format all` writes HTML + PNG + PDF. To save time:

```bash
# Interactive HTML only (fastest)
litmap map --collection "My Papers" --format html --output ~/Desktop/map

# Static files only
litmap map --collection "My Papers" --format png --output ~/Desktop/map
```

---

## 10. Using litmap with the manuscript-audit Skill

If you use the `manuscript-audit` skill in Claude, it automatically calls `litmap search` during citation gap detection to find semantically relevant papers for unsupported claims.

To check it's wired up correctly:

```bash
litmap search \
  --query "biodiversity loss accelerating globally" \
  --format json
```

If this returns valid JSON, the skill will use it.

---

## 11. Keeping the Embedding Cache Up to Date

The cache updates automatically at the start of every command. When you add papers to Zotero, the next `litmap` invocation will embed them:

```
Syncing new papers: 100%|████| 12/12 [00:03<00:00,  3.8 paper/s]
```

If Zotero is already up to date, nothing is printed and the command proceeds immediately.

To force a manual sync:

```bash
litmap sync
litmap sync --force   # regenerate all embeddings
```

---

## Tips

- **Large libraries (1000+ papers):** `litmap map` can take 30–60 seconds for the UMAP step. Use `--format html` to skip the matplotlib render if you only need the interactive version.
- **BibTeX input:** `litmap map --manuscript refs.bib` and `litmap cluster --manuscript refs.bib` both work with `.bib` files — useful if you're writing in LaTeX.
- **The embedding model is local:** after first download, all commands work offline. No API keys, no rate limits.
- **Zotero does not need to be running:** litmap reads `~/Zotero/zotero.sqlite` directly in read-only mode.
- **Missing PDFs:** if `litmap info` shows `PDF: —` for a paper you expect to have a PDF, right-click the item in Zotero and choose Find Available PDF, then re-run `litmap sync-fulltext`.
