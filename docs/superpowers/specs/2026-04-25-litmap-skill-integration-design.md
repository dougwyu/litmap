# litmap Integration into `zotero` and `manuscript-audit` Skills

**Date:** 2026-04-25
**Approach:** Comprehensive (Approach 2 from brainstorming).
**Runtime:** Both skills are rewritten in place to be **Claude Code only**. The Cowork web sandbox path is dropped for these two skills.

---

## 1. Goal

Let the user query the Zotero library *and* the local embeddings database (`~/LitLake/embeddings.db`) using natural language, plus expose `litmap`'s paper-to-paper similarity and hierarchical-clustering features through the existing `zotero` and `manuscript-audit` skills.

The user's primary phrasing: *"query the Zotero database and embeddings.db using natural language."*

---

## 2. Architecture

Two skill files are edited in place:

```
~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/
  …/skills/
  ├── zotero/SKILL.md              ← edit
  └── manuscript-audit/SKILL.md    ← edit
```

Both gain a runtime banner at the very top, immediately after the YAML front matter:

> ⚠️ **Runtime: Claude Code only.** This skill calls `uv run litmap …` against `~/LitLake/embeddings.db` on the local machine. It will not work in the Cowork web sandbox. If you reached this skill from the Cowork web frontend, stop and switch to Claude Code.

The front matter `description` field also has `(Claude Code only)` appended so the loader/registry surfaces it.

Both skills shell out via `Bash(uv run --project ~/src/Cowork/litmap litmap …)` — the explicit `--project` makes the skill working-directory-independent. Output is requested as `--format json` (or `md` for cluster outlines) and parsed.

Storage paths the skills depend on (unchanged from current litmap install):

- `~/Zotero/zotero.sqlite` — read-only metadata + full-text index + PDFs
- `~/LitLake/embeddings.db` — float32 vectors keyed by `zotero_key`
- `~/src/Cowork/litmap/` — the litmap package

---

## 3. `zotero` skill changes

### 3.1 Header changes

- Front-matter `description`: append `(Claude Code only)` and add the phrase `semantic search via litmap embeddings` so trigger phrases route here.
- New runtime banner immediately under the front matter (text in §2).
- "Three tiers of search" heading → **"Four tiers of search."** Add Tier 4 to the tier-selection paragraph.

### 3.2 New Tier 4: Semantic (model-backed)

Inserted after Tier 3 (the PDF OCR tier). Three numbered sub-patterns, each with a worked example.

**Tier 4 prologue paragraph (skill text):**

> Use when the query is conceptual or paraphrased — i.e. when keyword search would miss synonyms, acronyms, or rephrasings. Tier 4 calls `litmap search` or `litmap cluster` against the local embeddings database. The first call after a fresh model download or a long idle takes 10–30 seconds while the embedding model warms up; subsequent calls within the same session are sub-second.

**Pattern 4a — Natural-language query → ranked papers.**

```bash
uv run --project ~/src/Cowork/litmap litmap search \
  --query "biodiversity loss accelerating in tropics" \
  --top-k 10 --format json
```

Returns:

```json
{
  "query": "biodiversity loss accelerating in tropics",
  "results": [
    {"zotero_key": "AAAA0001", "title": "...", "authors": ["..."], "year": "2022",
     "doi": "10.1/...", "similarity": 0.91, "abstract": "..."},
    ...
  ]
}
```

The skill summarises the top results with similarity scores. `zotero_key` from the response is portable — pass it to Tier 1/2/3 to open the PDF or fetch full metadata.

**Pattern 4b — Paper-to-paper similarity.**

```bash
uv run --project ~/src/Cowork/litmap litmap search \
  --paper "10.1126/science.1256014" --top-k 10 --format json
```

The focal paper is automatically excluded. Same JSON shape as 4a. Used for *"what else have I read like X?"*

**Pattern 4c — Cluster a collection or library into themed groups.**

```bash
uv run --project ~/src/Cowork/litmap litmap cluster \
  --collection "Chapter 2 refs" \
  --output /tmp/litmap_clusters \
  --format md
```

The skill reads `/tmp/litmap_clusters.md` and presents the outline inline. For visual exploration, the skill mentions the `.html` dendrogram is also available at the same base path with `--format all`.

For an entire-library outline, the user can omit `--collection`.

### 3.3 Tier-selection flowchart

Replaces the current selection paragraph. Skill text:

```
Exact author/year/title or specific Zotero collection?     → Tier 1
A specific keyword/phrase across PDF text?                 → Tier 2
Deep claim verification needing PDF read?                  → Tier 3
Conceptual / paraphrased / "find similar" / "organise"?    → Tier 4
```

When in doubt, Tier 1 first to scope, then Tier 4 within scope.

### 3.4 Cross-tier integration rules

- Tier 4 results carry `zotero_key`. Pass it straight to Tier 1 SQL (`WHERE i.key = ?`) for full metadata, or to Tier 3 for PDF reading.
- When the user has specified a collection scope ("in NatureMAP, find papers about X"), pass `--collection "<name>"` to litmap. If the user has specified a *library* (one of the 7 in the table), litmap cannot scope by library directly — fall back to running Tier 4 unscoped, then filter results by checking each `zotero_key` against `libraryID` via a single Tier 1 SQL query.
- Auto-sync runs before every litmap call. The skill notes this in the user response only if the sync added papers (>0).

### 3.5 Errors and edge cases

| Condition | Skill response |
|---|---|
| `litmap` command not found | "`litmap` is not installed. Run `uv pip install -e .` from `~/src/Cowork/litmap`." |
| First-run model download | "First-run model download (~570 MB), this takes ~1 minute." |
| `~/LitLake/embeddings.db` missing | "Embeddings database not found. Run `litmap sync` once to embed the library." |
| Auto-sync took > 30s on incremental | Note: "Sync took longer than usual — if you've recently added many papers, this is expected." |
| Top result similarity < 0.5 | "No strong semantic matches in your library. Consider rephrasing or broadening the query." |

---

## 4. `manuscript-audit` skill changes

Stage 1, 3, 4 are unchanged. Only Stage 2 ("citation-gap detection") is rewritten.

### 4.1 Header changes

Same as `zotero`: append `(Claude Code only)` to front-matter `description`, add the runtime banner under the front matter.

### 4.2 Stage 2 rewrite

The existing Stage 2 (~260 lines) has two distinct workflows:

- **Step 0 — `(REFS)` placeholder resolution:** the author marks gaps explicitly with `(REFS)` in the draft; the skill resolves these as the highest-priority gaps using two-tier SQL search (metadata + full-text).
- **Implicit gap detection:** five-step process for gaps the author didn't mark, using a three-tier search (semantic via litmap as Tier 1, proper-noun keyword as Tier 2, metadata + full-text as a fallback if litmap returns nothing).

The rewrite **preserves both workflows** and **switches the candidate-search engine to litmap** in both. Specifically:

- `(REFS)` placeholders stay as Step 0. The detection regex, claim-understanding sub-steps (assertion / evidence type / implied audience / additive vs sole), and output format are kept verbatim from the original. Only the candidate-search procedure changes — replace the two-tier SQL block with a single `litmap search --query` call, plus an optional proper-noun pass for species names / acronyms / methods that may not show up in semantic embedding distance.
- The implicit-gap workflow keeps its five-step structure (identify → extract context → search → rank → prioritise). Step 3's three-tier search collapses: litmap is the only required engine (Tier 1 of original), with the proper-noun pass kept as a complement (was Tier 2). The metadata + full-text fallback (was Tier 3) is **dropped** — if `litmap` is unavailable, the skill aborts Stage 2 and emits the install message rather than silently degrading.
- The original output format (relevance levels: **Perfect match / Strong / Moderate / Weak**, with snippet and one-sentence justification per candidate) is **kept**. Similarity score from litmap is exposed alongside the relevance level — they're complementary; relevance assesses *fit to the specific claim*, similarity is the raw embedding distance.
- A **new optional step** is added: when the manuscript has ≥30 unique citations, run `litmap cluster --manuscript <path>` once at the start of Stage 2 and present the thematic outline before any per-claim analysis. Useful for spotting whole topic areas under-cited or over-cited.

The detailed sub-procedure follows.

#### 4.2.1 Step 0 — Resolve `(REFS)` placeholders first (kept; candidate engine swapped)

Detection (verbatim from the original):

```bash
grep -n "REFS" manuscript.txt
```

Or in Python:
```python
import re
for m in re.finditer(r'\bREFS\b', text):
    start = text.rfind('\n', 0, m.start()) + 1
    end = text.find('\n', m.end())
    print(f"Line {text[:m.start()].count(chr(10))+1}: {text[start:end].strip()}")
```

For each occurrence, extract **5–10 lines of surrounding context** and identify:
- The core assertion
- The type of evidence expected (empirical / review / methodology / grey lit)
- The implied audience (e.g. assurance, ecology, economics, policy)
- Additive vs sole

**New candidate-search procedure** (replaces the original two-tier SQL block):

```bash
uv run --project ~/src/Cowork/litmap litmap search \
  --query "<claim assertion + 1–2 sentences of context>" \
  --top-k 8 --format json
```

Plus an optional proper-noun pass against Zotero metadata for species names / acronyms / methods that semantic search may underweight (using the existing `extract_proper_nouns` regex from the original skill — kept verbatim — and a focused `LIKE` query against `tv.value` and `av.value`). Merge the two result sets, deduping by `zotero_key`; semantic hits sort first by similarity, proper-noun-only hits append after.

Filter and rank candidates (kept verbatim from the original):
- Does the paper directly support the claim, or only tangentially?
- Right type of evidence?
- Already cited elsewhere?
- Serves the implied audience?

Suggest **3–4 candidates per REFS**, ranked by fit. One-sentence rationale each.

Output format (kept verbatim):

```
REFS — Line [N]
Context: "[sentence(s) containing REFS, with surrounding citations if any]"
Claim: [1-sentence description of what evidence is needed]
Implied audience: [e.g., assurance/finance/ecology/policy]

Suggested citations:
1. [Zotero key] Author et al. (year). Title. Journal. DOI.
   → [1-sentence rationale]

2. [Zotero key] Author et al. (year). Title. Journal. DOI.
   → [1-sentence rationale]

[If no strong candidates found:]
No strong candidates found in [library name]. Consider searching [suggested alternative sources].
```

Deliver REFS resolutions as a dedicated section before the implicit-gap analysis.

#### 4.2.2 Implicit gap detection (kept structure; candidate engine swapped)

**Step A — (Optional, ≥30 unique citations only) Up-front cluster overview.**
```bash
uv run --project ~/src/Cowork/litmap litmap cluster \
  --manuscript <manuscript_path> \
  --output /tmp/audit_clusters \
  --format md
```
Read `/tmp/audit_clusters.md` and present the thematic outline before per-claim analysis. Useful for spotting topic areas under- or over-cited.

**Step B — Identify unsupported claims** (kept verbatim from original Process step 1):
- No citation
- Citation verdict ✗ **Unsupported** or ⚠ **Overstated** (from Stage 1)
- A citation to a paper that exists in Zotero but lacks the supporting passage

**Step C — Extract claim context** (kept verbatim from original Process step 2):
- Claim text (1–2 sentences)
- Section heading
- Key concepts (nouns, verbs, relationships)

**Step D — Search for candidates (litmap + proper-noun pass).**

Litmap query:
```bash
uv run --project ~/src/Cowork/litmap litmap search \
  --query "<claim_text>. <sentence_context>" \
  [--collection "<scope>"] \
  --top-k 5 --format json
```

`--collection` is included only if the user named one (e.g. "audit against my Chapter 2 refs only").

Proper-noun pass: extract capitalised phrases / acronyms / species names from the claim using the original `extract_proper_nouns` regex (kept verbatim) and run a SQL `LIKE` query against `itemDataValues` for title and abstract. Merge with litmap results, dedupe by `zotero_key`.

If litmap returns no candidates above the **0.75 similarity threshold**, *and* the proper-noun pass also returns nothing, the per-claim entry says "no semantically similar papers in your library; consider broader literature search."

**Step E — Rank and suggest** (kept verbatim from original Process step 4):
- Check if the result's abstract/title matches the claim
- Assign relevance: **Perfect match / Strong / Moderate / Weak**
- Extract a brief snippet from the paper that supports the claim
- Write a 1-sentence justification

**Step F — Prioritise suggestions** (kept verbatim from original Process step 5):
- Up to 2 papers for claims with no citation
- 1 replacement paper if the current citation is unsupported
- 1–2 supplementary papers if the citation is weak or too narrow

**Filter overlap with existing citations:** drop any candidate already cited in the manuscript (compare DOI first, then `lastname year` against the Stage 1 reference list).

**Output format** (kept verbatim from original):

```
[Claim Location] Results section, paragraph 3

Unsupported claim: "Deep learning models outperform traditional SDMs
in predicting species distributions."

**Suggested citations:**

1. **Max et al. 2022** — "Deep learning for species distribution modeling:
A benchmark study"
   Relevance: Perfect match  (similarity 0.91)
   Snippet: "Deep neural networks achieved 12% higher AUC than MaxEnt
   models on average across 500 species."
   Justification: Directly compares deep learning to traditional SDMs with
   quantitative results.

2. **Brown & Kim 2021** — "Machine learning in biodiversity prediction"
   Relevance: Strong  (similarity 0.78)
   Snippet: "Recent advances in neural networks have improved predictive
   accuracy for spatial distribution models."
   Justification: Broader review of ML in SDMs; supports the claim but
   is less specific than Max et al. 2022.
```

Note the addition of `(similarity X.XX)` next to the relevance level — the only material change to the output format.

### 4.3 Stage 2 failure modes

- **Cluster step (Step A) fails** (e.g., < 2 cited papers found in Zotero or `litmap cluster` errors): skip silently, proceed to per-claim search.
- **`litmap` unavailable** (command not found, model fails to load, embeddings DB missing): emit the install/sync message ("Run `uv pip install -e .` from `~/src/Cowork/litmap`" or "Run `litmap sync` first") and abort Stage 2. **Do not silently fall back to keyword/full-text-only search** — the user explicitly requested a semantic audit, and a degraded fallback would be misleading.
- **Manuscript `--collection` scope mismatch**: if `--collection X` was passed but X has fewer than 5 papers, warn the user and offer to broaden.

### 4.4 What's removed

- The original "Tier 3 — Metadata + full-text fallback" inside the implicit-gap Step 3 — dropped. With litmap mandatory, the fallback is unnecessary and would degrade silently.
- Any prior text suggesting "fall back to keyword search if litmap unavailable" — replaced by the abort-with-install-message in §4.3.

### 4.5 What's kept verbatim from the original

To make the diff explicit:

- Step 0 detection regex, context-extraction rule, claim-understanding sub-questions, candidate-filtering criteria, suggestion count (3–4 per REFS), `Output format for REFS resolution` block.
- Implicit-gap Steps B (identify unsupported claims), C (extract claim context), E (rank with relevance levels), F (prioritise).
- The `extract_proper_nouns` regex helper.
- The relevance levels (**Perfect match / Strong / Moderate / Weak**), snippet rule, justification rule, and the implicit-gap output template.

---

## 5. Testing

Skills don't have a unit-test harness, but we verify behaviour by invoking the rewritten skills against the live setup and checking observable outputs.

| Test | Expected |
|---|---|
| `zotero` skill: "find papers about gut microbiome remodelling in hibernating bears" | Skill calls Tier 4a (`litmap search --query …`), returns ≥1 result with similarity ≥ 0.75. |
| `zotero` skill: "what else have I read like 10.1126/science.1256014" | Skill calls Tier 4b, focal paper not in results. |
| `zotero` skill: "organise My Papers into themes" | Skill calls Tier 4c, presents Markdown outline of 2+ clusters. |
| `zotero` skill: "Find papers by Valavi 2022" | Skill stays in Tier 1 (no litmap call). |
| `zotero` skill: invoked with `litmap` uninstalled | Skill emits install instructions, does not crash. |
| `manuscript-audit` Stage 2 with a manuscript containing 3 unsupported claims | Each claim gets up to 3 suggested citations from the library, with relevance level + similarity score, or "no matches" message. |
| `manuscript-audit` Stage 2 with a manuscript containing `(REFS)` placeholders | Step 0 fires, REFS placeholders resolved as a dedicated section before implicit-gap analysis, candidates fetched via `litmap search` (not metadata SQL). |
| `manuscript-audit` Stage 2 with 40-citation manuscript | Cluster overview appears before per-claim analysis. |
| `manuscript-audit` Stage 2 with 5-citation manuscript | No cluster overview (under threshold). |
| `manuscript-audit` Stage 2 with `litmap` unavailable | Stage 2 aborts with install message; does NOT silently fall back to metadata/full-text search. |

---

## 6. Out of scope

- **Cowork sandbox compatibility** — explicitly dropped. The runtime banner makes this loud.
- **Re-organising Zotero collections from cluster output** — the spec for `litmap cluster` left this open as a forward-compatibility hook; this skill update does not exercise it.
- **Cross-paper interdisciplinarity ranking** — separate future feature, depends on the `.linkage.npy` cache that `litmap cluster` already writes.
- **The `zotero-notes-import` skill** — unrelated to litmap, untouched.

---

## 7. Open questions / forward-compat notes

- **Similarity threshold (0.75) is a guess.** First real run against the user's library may show that 0.7 or 0.8 is a better default. The threshold is exposed as a single constant in the skill text — easy to tune later.
- **`--paper` accepts DOI or title.** The skill prefers DOI when the user provides one; for ambiguous titles it falls back to litmap's built-in close-match suggestions.
- **Stage 1 retraction check** is unaffected by this update — it stays in `manuscript-audit` as already specified.
- **Proper-noun pass complementing litmap.** The original skill's `extract_proper_nouns` regex catches species names, acronyms, and method names that semantic embeddings sometimes underweight. We keep it as a complement to `litmap search`, not a fallback. If after a few real audits the proper-noun pass never adds anything litmap missed, drop it.
