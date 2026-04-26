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

**Replaces** the current Stage 2 "use the zotero skill for semantic search; fall back to keyword search" paragraph (~15 lines) with the following procedure.

**Procedure:**

1. **Identify unsupported claims.** Unchanged from current behaviour. Scan the manuscript for empirical or theoretical assertions that lack an in-text citation. Build a list of records:
   ```
   {claim_text, sentence_context, section_heading}
   ```
   where `sentence_context` is the claim's sentence plus the one preceding sentence (for query disambiguation).

2. **(Optional, ≥30 unique citations only) — Up-front cluster overview.**
   ```bash
   uv run --project ~/src/Cowork/litmap litmap cluster \
     --manuscript <manuscript_path> \
     --output /tmp/audit_clusters \
     --format md
   ```
   Skill reads `/tmp/audit_clusters.md` and presents the thematic outline before per-claim analysis. The user can use this to spot whole topic areas that are over- or under-cited in the manuscript.

3. **Per-claim semantic search.** For each unsupported-claim record, call:
   ```bash
   uv run --project ~/src/Cowork/litmap litmap search \
     --query "<claim_text>. <sentence_context>" \
     [--collection "<scope>"] \
     --top-k 5 --format json
   ```
   `--collection` is included only if the user named one ("audit my manuscript against my Chapter 2 refs only").

4. **Filter candidates.**
   - Drop any candidate already cited in the manuscript (compare DOI first, then `lastname year` against the reference list built in Stage 1).
   - Drop any candidate with `similarity < 0.75` — below that threshold the match is usually too weak to be useful.
   - Keep at most 3 candidates per claim.

5. **Present the report.** For each unsupported claim:
   ```markdown
   ### Section 3.2 — claim text excerpt
   > "<the claim sentence>"

   Suggested citations from your library (similarity, zotero_key):
   1. **0.87** — Valavi et al. 2022, *Predictive performance of presence-only SDMs* (`AAAA0001`)
      DOI: 10.1111/geb.13476
   2. **0.81** — Norberg 2019, *A comprehensive evaluation of predictive performance...* (`AAAA0042`)
   ```
   If no candidates clear the threshold:
   > "No semantically similar papers in your library. Consider broader literature search outside the local Zotero collection."

### 4.3 Stage 2 failure modes

- **Cluster step fails** (e.g., < 2 cited papers found in Zotero): skip silently, proceed to per-claim search.
- **litmap unavailable**: emit the same install message as the zotero skill, and abort Stage 2 (do not silently fall back to keyword search — the user explicitly requested a semantic audit).
- **Manuscript scope mismatch**: if the user passed `--collection X` but X has fewer than 5 papers, warn that the scoped search is likely too narrow and offer to broaden.

### 4.4 What's removed

- The existing "Stage 2 keyword fallback" paragraph (`if litmap not available, use full-text index ...`) — gone, replaced by the unavailability error in §4.3.
- Any prior text saying "results may be approximate" — Stage 2 is now first-class.

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
| `manuscript-audit` Stage 2 with a manuscript containing 3 unsupported claims | Each claim gets up to 3 suggested citations from the library, all with similarity ≥ 0.75 or "no matches" message. |
| `manuscript-audit` Stage 2 with 40-citation manuscript | Cluster overview appears before per-claim analysis. |
| `manuscript-audit` Stage 2 with 5-citation manuscript | No cluster overview (under threshold). |

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
