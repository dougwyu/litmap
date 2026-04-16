# litmap Tutorial

This tutorial walks through the main workflows: searching your Zotero library semantically, generating paper maps, and using litmap alongside a manuscript in progress.

---

## 1. Setup

Install and run once to trigger the model download and first sync:

```bash
cd ~/src/Cowork/litmap
uv venv
uv pip install -e .
uv run litmap sync
```

You will see a progress bar while `BAAI/bge-small-en-v1.5` (~130 MB) downloads and your Zotero library is embedded. This happens once. After that every command is instantaneous for the sync step (it only processes new items).

```
Syncing new papers: 100%|████████████████| 347/347 [01:23<00:00,  4.1 paper/s]
Embedded 347 new papers.
```

---

## 2. Searching Your Library

### Find papers similar to a sentence

```bash
uv run litmap search --query "deep learning models for species distribution modelling"
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
uv run litmap search \
  --query "carbon sequestration tropical forests" \
  --collection "Chapter 2 refs" \
  --top-k 5
```

### Search from a focal paper

Find what else in your library is similar to a paper you already know:

```bash
uv run litmap search --paper "10.1126/science.1256014"
# or by title:
uv run litmap search --paper "Sensing biodiversity"
```

The focal paper is excluded from its own results. If the title isn't an exact match, litmap suggests close alternatives.

### Machine-readable output

For scripting or use with other tools (e.g. the `manuscript-audit` skill):

```bash
uv run litmap search \
  --query "functional diversity trait-based ecology" \
  --format json | jq '.results[].title'
```

---

## 3. Mapping a Zotero Collection

```bash
uv run litmap map \
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
uv run litmap map --collection "My Papers" --n-neighbors 30 --output ~/Desktop/dense

# Sparser graph edges
uv run litmap map --collection "My Papers" --edge-k 2 --output ~/Desktop/sparse
```

`--n-neighbors` controls the UMAP global structure (higher = broader view of neighbourhood). `--edge-k` controls how many edges each node draws.

---

## 4. Mapping a Manuscript's Bibliography

If you have a PDF, DOCX, `.bib`, or `.tex` file, litmap extracts its references and maps only the papers it can match in your Zotero library.

```bash
uv run litmap map \
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
uv run litmap map \
  --collection "My Papers" \
  --manuscript ~/Documents/my_paper.pdf \
  --output ~/Desktop/litmap_positioned
```

### Mode B — Bibliography only

Map just the papers you cited, with your manuscript at the centre.

```bash
uv run litmap map \
  --manuscript ~/Documents/my_paper.pdf \
  --output ~/Desktop/litmap_bib_only
```

### Mode C — Union (collection + bibliography)

Include every paper in the collection *plus* any additional papers from your bibliography not already in the collection. The manuscript node is added too.

```bash
uv run litmap map \
  --collection "My Papers" \
  --manuscript ~/Documents/my_paper.pdf \
  --union \
  --output ~/Desktop/litmap_union
```

This is the most complete view: the full collection provides context, and any papers you cited outside the collection appear as additions.

---

## 6. Only Generating One Output Format

By default `--format all` writes HTML + PNG + PDF. To save time:

```bash
# Interactive HTML only (fastest)
uv run litmap map --collection "My Papers" --format html --output ~/Desktop/map

# Static files only (no Plotly overhead)
uv run litmap map --collection "My Papers" --format png --output ~/Desktop/map
```

---

## 7. Using litmap with the manuscript-audit Skill

If you use the `manuscript-audit` skill in Claude, it automatically calls `litmap search` during Stage 2 (citation gap detection) to find semantically relevant papers for unsupported claims. It falls back to keyword search if litmap is unavailable.

To check it's wired up correctly:

```bash
uv run litmap search \
  --query "biodiversity loss accelerating globally" \
  --format json
```

If this returns valid JSON, the skill will use it.

---

## 8. Keeping the Embedding Cache Up to Date

The cache updates automatically at the start of every command. When you add papers to Zotero, the next `litmap` invocation will embed them:

```
Syncing new papers: 100%|████| 12/12 [00:03<00:00,  3.8 paper/s]
```

If Zotero is already up to date, nothing is printed and the command proceeds immediately.

To force a manual sync at any time:

```bash
uv run litmap sync
```

---

## Tips

- **Large libraries (1000+ papers):** `litmap map` can take 30–60 seconds for the UMAP step. Use `--format html` to skip the matplotlib render if you only need the interactive version.
- **BibTeX input:** `litmap map --manuscript refs.bib` and `litmap search` both work with `.bib` files — useful if you're writing in LaTeX and want to check coverage before submission.
- **The embedding model is local:** after first download, all commands work offline. No API keys, no rate limits.
- **Zotero does not need to be running:** litmap reads `~/Zotero/zotero.sqlite` directly in read-only mode.
