# litmap Skill Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Edit the user's `zotero` and `manuscript-audit` skills in place so they call `litmap` for natural-language semantic search, paper-to-paper similarity, and collection clustering. Both skills are Claude-Code-only after this update.

**Architecture:** Two SKILL.md files are edited in place. Each gains a runtime banner at the top, an updated front-matter `description`, and new content sections. The `zotero` skill gains a "Tier 4: Semantic" section with three patterns. The `manuscript-audit` skill's Stage 2 procedure is rewritten to call `litmap search` per unsupported claim, with an optional up-front `litmap cluster` overview for ≥30-citation manuscripts. Files are not under git; we use `.bak` snapshots for rollback and copy the edited files into the litmap repo at `docs/skills/snapshots/` for audit trail.

**Tech Stack:** Markdown editing only. Verification is manual through Claude Code shell invocations and observed skill behaviour.

**Reference spec:** `docs/superpowers/specs/2026-04-25-litmap-skill-integration-design.md`.

**Important conventions:**
- All shell commands assume `~/src/Cowork/litmap` is the project repo (run `git -C ~/src/Cowork/litmap …` from anywhere).
- Skill files live under macOS `~/Library/Application Support/Claude/...` — paths contain spaces and UUIDs; always quote.
- Commits in the litmap repo use the trailer: `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`.

---

### Task 1: Resolve current skill paths, snapshot both files

**Files:**
- Read: `~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/<UUID1>/<UUID2>/skills/zotero/SKILL.md`
- Read: `~/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/<UUID1>/<UUID2>/skills/manuscript-audit/SKILL.md`
- Create: `~/src/Cowork/litmap/docs/skills/snapshots/2026-04-25-pre-edit/zotero.SKILL.md`
- Create: `~/src/Cowork/litmap/docs/skills/snapshots/2026-04-25-pre-edit/manuscript-audit.SKILL.md`

---

- [ ] **Step 1: Discover the runtime skills directory**

```bash
SKILLS_ROOT=$(find ~/Library/Application\ Support/Claude/local-agent-mode-sessions/skills-plugin -maxdepth 4 -type d -name skills -print -quit 2>/dev/null)
echo "$SKILLS_ROOT"
test -f "$SKILLS_ROOT/zotero/SKILL.md" && echo "zotero ✓"
test -f "$SKILLS_ROOT/manuscript-audit/SKILL.md" && echo "manuscript-audit ✓"
```

Expected: prints a path containing two UUIDs ending in `/skills`, then `zotero ✓` and `manuscript-audit ✓`. If either skill is missing, stop and report — do not invent a path.

Save the resolved `$SKILLS_ROOT` value. Every subsequent task assumes it is in scope.

- [ ] **Step 2: Create the litmap repo snapshot directory and copy the two pre-edit files**

```bash
mkdir -p ~/src/Cowork/litmap/docs/skills/snapshots/2026-04-25-pre-edit
cp "$SKILLS_ROOT/zotero/SKILL.md"           ~/src/Cowork/litmap/docs/skills/snapshots/2026-04-25-pre-edit/zotero.SKILL.md
cp "$SKILLS_ROOT/manuscript-audit/SKILL.md" ~/src/Cowork/litmap/docs/skills/snapshots/2026-04-25-pre-edit/manuscript-audit.SKILL.md
```

- [ ] **Step 3: Create `.bak` rollback copies next to the runtime files**

```bash
cp "$SKILLS_ROOT/zotero/SKILL.md"           "$SKILLS_ROOT/zotero/SKILL.md.bak"
cp "$SKILLS_ROOT/manuscript-audit/SKILL.md" "$SKILLS_ROOT/manuscript-audit/SKILL.md.bak"
ls -la "$SKILLS_ROOT/zotero/" "$SKILLS_ROOT/manuscript-audit/"
```

Expected: each directory now has both `SKILL.md` and `SKILL.md.bak`.

- [ ] **Step 4: Commit the snapshots in the litmap repo**

```bash
cd ~/src/Cowork/litmap
git add docs/skills/snapshots/2026-04-25-pre-edit/
git commit -m "docs: snapshot zotero + manuscript-audit SKILL.md before edit

Pre-edit copies of the runtime skill files for audit trail and rollback.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Update `zotero` front matter + add Claude-Code-only banner + change tier count

**Files:**
- Modify: `$SKILLS_ROOT/zotero/SKILL.md` (lines ~1–10 plus the "Three tiers of search" heading)

The current front matter (from the snapshot) is:

```yaml
---
name: zotero
description: "Use this skill whenever the user wants to query, search, or explore their Zotero reference library — or when they need help with citations in their writing. ..."
---
```

The current "tiers" overview heading is `## Three tiers of search`.

---

- [ ] **Step 1: Read the file to confirm exact heading text**

```bash
head -50 "$SKILLS_ROOT/zotero/SKILL.md"
grep -n "Three tiers of search" "$SKILLS_ROOT/zotero/SKILL.md"
```

Confirm there is exactly one match for `## Three tiers of search`. If there are zero matches the heading text drifted — stop and report.

- [ ] **Step 2: Edit the front-matter `description`**

Use the Edit tool. Find the existing `description: "..."` line (it is one long line ending with `, "what did I highlight"."`) and append `(Claude Code only — runs litmap against ~/LitLake/embeddings.db; not available in Cowork sandbox.)` immediately before the closing quote and after the existing trailing period.

The resulting line should end with:
```
... "what did I highlight". (Claude Code only — runs litmap against ~/LitLake/embeddings.db; not available in Cowork sandbox.)"
```

- [ ] **Step 3: Insert the runtime banner immediately under the front matter**

Locate the first line after the closing `---` and the `# Zotero Skill` H1 heading. Immediately after the H1, before the first paragraph (`## Setup`), insert this block:

```markdown
> ⚠️ **Runtime: Claude Code only.** This skill calls `uv run litmap …` against `~/LitLake/embeddings.db` on the local machine. It will not work in the Cowork web sandbox. If you reached this skill from the Cowork web frontend, stop and switch to Claude Code.

```

(Trailing blank line included.)

- [ ] **Step 4: Update the tier-overview heading**

Change `## Three tiers of search` to `## Four tiers of search`.

- [ ] **Step 5: Verify the edits parse**

```bash
head -20 "$SKILLS_ROOT/zotero/SKILL.md"
grep -c "Four tiers of search"   "$SKILLS_ROOT/zotero/SKILL.md"  # expect 1
grep -c "Three tiers of search"  "$SKILLS_ROOT/zotero/SKILL.md"  # expect 0
grep -c "Runtime: Claude Code only" "$SKILLS_ROOT/zotero/SKILL.md"  # expect 1
grep -c "Claude Code only — runs litmap" "$SKILLS_ROOT/zotero/SKILL.md"  # expect 1
```

All four `grep -c` counts must match the expected value.

- [ ] **Step 6: Snapshot the in-progress edit into the litmap repo**

```bash
mkdir -p ~/src/Cowork/litmap/docs/skills/snapshots/2026-04-25-post-edit
cp "$SKILLS_ROOT/zotero/SKILL.md" ~/src/Cowork/litmap/docs/skills/snapshots/2026-04-25-post-edit/zotero.SKILL.md
```

(No commit yet — we'll commit once all zotero edits are done in Task 4.)

---

### Task 3: Insert the new Tier 4 section into `zotero/SKILL.md`

**Files:**
- Modify: `$SKILLS_ROOT/zotero/SKILL.md` (insert before the section that follows Tier 3)

---

- [ ] **Step 1: Locate the insertion point**

```bash
grep -n "^## " "$SKILLS_ROOT/zotero/SKILL.md"
```

Identify the heading that immediately follows Tier 3's content (it will be the next `## `-level heading after the Tier 3 block). The new Tier 4 section is inserted **before** that heading.

If the heading immediately after Tier 3 is something like `## Cross-tier rules` or `## Errors` or any other section, the insertion happens just above it. If Tier 3 is the last `## `-level section in the file, append at end of file.

- [ ] **Step 2: Insert the Tier 4 block**

Insert the following text. Maintain a blank line above and below.

````markdown
## Tier 4 — Semantic (model-backed)

Use when the query is conceptual or paraphrased — i.e. when keyword search would miss synonyms, acronyms, or rephrasings. Tier 4 calls `litmap search` or `litmap cluster` against the local embeddings database. The first call after a fresh model download or a long idle takes 10–30 seconds while the embedding model warms up; subsequent calls within the same session are sub-second.

### Pattern 4a — Natural-language query → ranked papers

```bash
uv run --project ~/src/Cowork/litmap litmap search \
  --query "biodiversity loss accelerating in tropics" \
  --top-k 10 --format json
```

Returns JSON of the form:

```json
{
  "query": "biodiversity loss accelerating in tropics",
  "results": [
    {"zotero_key": "AAAA0001", "title": "...", "authors": ["..."],
     "year": "2022", "doi": "10.1/...", "similarity": 0.91, "abstract": "..."}
  ]
}
```

Summarise the top results with similarity scores. The `zotero_key` is portable — pass it to Tier 1/2/3 to open the PDF or fetch full metadata.

### Pattern 4b — Paper-to-paper similarity

```bash
uv run --project ~/src/Cowork/litmap litmap search \
  --paper "10.1126/science.1256014" --top-k 10 --format json
```

Same JSON shape as 4a; the focal paper is automatically excluded. Use for *"what else have I read that's like X?"*

### Pattern 4c — Cluster a collection or library into themed groups

```bash
uv run --project ~/src/Cowork/litmap litmap cluster \
  --collection "Chapter 2 refs" \
  --output /tmp/litmap_clusters \
  --format md
```

Read `/tmp/litmap_clusters.md` and present the outline inline. For visual exploration, mention that the `.html` dendrogram is also available via `--format all`.

To cluster the entire library, omit `--collection`.

````

- [ ] **Step 3: Verify the Tier 4 block parsed**

```bash
grep -c "^## Tier 4 — Semantic" "$SKILLS_ROOT/zotero/SKILL.md"  # expect 1
grep -c "Pattern 4a"            "$SKILLS_ROOT/zotero/SKILL.md"  # expect 1
grep -c "Pattern 4b"            "$SKILLS_ROOT/zotero/SKILL.md"  # expect 1
grep -c "Pattern 4c"            "$SKILLS_ROOT/zotero/SKILL.md"  # expect 1
grep -c "uv run --project ~/src/Cowork/litmap" "$SKILLS_ROOT/zotero/SKILL.md"  # expect 3
```

All five must match.

---

### Task 4: Update `zotero` tier-selection flowchart, cross-tier rules, and error table

**Files:**
- Modify: `$SKILLS_ROOT/zotero/SKILL.md`

---

- [ ] **Step 1: Locate the existing tier-selection paragraph**

The current selection guidance is the paragraph immediately above or inside `## Three tiers of search`/`## Four tiers of search` (renamed in Task 2). Find it:

```bash
grep -n "Choose the right tier" "$SKILLS_ROOT/zotero/SKILL.md"
```

Confirm one match. If zero, the wording differs — read the section and locate the equivalent paragraph manually.

- [ ] **Step 2: Replace the existing selection paragraph with the new flowchart**

Find the existing text (starts with "Choose the right tier for the task." and ends just before the **Tier 1 — Metadata** heading) and replace with:

```markdown
Choose the right tier for the task:

```
Exact author/year/title or specific Zotero collection?     → Tier 1
A specific keyword/phrase across PDF text?                 → Tier 2
Deep claim verification needing PDF read?                  → Tier 3
Conceptual / paraphrased / "find similar" / "organise"?    → Tier 4
```

When in doubt, Tier 1 first to scope, then Tier 4 within scope.
```

- [ ] **Step 3: Append the cross-tier integration rules section**

After the Tier 4c block (end of Task 3 insertion), but before any subsequent top-level section, insert:

```markdown
## Cross-tier integration rules

- Tier 4 results carry `zotero_key`. Pass it straight to Tier 1 SQL (`WHERE i.key = ?`) for full metadata, or to Tier 3 for PDF reading.
- When the user has specified a collection scope ("in NatureMAP, find papers about X"), pass `--collection "<name>"` to litmap.
- When the user has specified a *library* (one of the 7 in the libraries table), litmap cannot scope by library directly. Run Tier 4 unscoped, then filter results by checking each `zotero_key` against `libraryID` via a single Tier 1 SQL query.
- Auto-sync runs before every litmap call. Mention the sync in the user response only if it added papers (>0 new embeddings).

## Tier 4 errors and edge cases

| Condition | Skill response |
|---|---|
| `litmap` command not found | "`litmap` is not installed. Run `uv pip install -e .` from `~/src/Cowork/litmap`." |
| First-run model download | "First-run model download (~570 MB), this takes ~1 minute." |
| `~/LitLake/embeddings.db` missing | "Embeddings database not found. Run `litmap sync` once to embed the library." |
| Auto-sync took > 30s on incremental | Note: "Sync took longer than usual — if you've recently added many papers, this is expected." |
| Top result similarity < 0.5 | "No strong semantic matches in your library. Consider rephrasing or broadening the query." |
```

- [ ] **Step 4: Verify all zotero edits are present**

```bash
grep -c "^## Cross-tier integration rules" "$SKILLS_ROOT/zotero/SKILL.md"  # expect 1
grep -c "^## Tier 4 errors and edge cases" "$SKILLS_ROOT/zotero/SKILL.md"  # expect 1
grep -c "Conceptual / paraphrased"          "$SKILLS_ROOT/zotero/SKILL.md"  # expect 1
```

All three must match.

- [ ] **Step 5: Snapshot the final zotero edit into the litmap repo and commit**

```bash
cp "$SKILLS_ROOT/zotero/SKILL.md" ~/src/Cowork/litmap/docs/skills/snapshots/2026-04-25-post-edit/zotero.SKILL.md
cd ~/src/Cowork/litmap
git add docs/skills/snapshots/2026-04-25-post-edit/zotero.SKILL.md
git commit -m "docs: post-edit snapshot of zotero SKILL.md (Tier 4 added)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Verify zotero skill against three live test queries

**Files:** none modified.

This is manual verification through Claude Code (the host running this plan). The implementer asks the user to perform each test or — if comfortable — performs them by invoking the skill themselves.

---

- [ ] **Step 1: Test 4a (natural-language query)**

Ask the host (Claude Code) to invoke the zotero skill with this query:

> "Find papers in my Zotero about the gut microbiome of hibernating bears."

Expected behaviour: the skill matches Tier 4a, runs `uv run --project ~/src/Cowork/litmap litmap search --query "gut microbiome of hibernating bears" --top-k 10 --format json`, parses the result, and returns a ranked list of papers with similarity scores. If the user's library has no relevant content, the skill says so cleanly.

If instead the skill falls back to keyword search (Tier 2) without trying Tier 4 first, the routing is wrong — re-read the tier-selection flowchart edit in Task 4 Step 2.

- [ ] **Step 2: Test 4b (paper-to-paper)**

> "What else have I read that's similar to Valavi et al. 2022 — Predictive performance of presence-only species distribution models?"

Expected: skill identifies the focal paper (Tier 1 lookup → DOI), then invokes Tier 4b: `litmap search --paper "<doi-or-key>" --top-k 10 --format json`. Returns ranked similar papers, focal paper not in results.

- [ ] **Step 3: Test 4c (cluster outline)**

> "Organise my 'Chapter 2 refs' Zotero collection into thematic groups."

(Substitute a real collection name from the user's library if "Chapter 2 refs" doesn't exist.)

Expected: skill runs `litmap cluster --collection "Chapter 2 refs" --output /tmp/litmap_clusters --format md`, reads the resulting Markdown, and presents the outline.

- [ ] **Step 4: Test the unavailable-litmap path (optional, safe to skip)**

Temporarily rename the litmap binary or pass a bogus project path, then re-run a Tier 4a query. Expected: skill emits the install message from the errors table without crashing. Restore afterwards.

- [ ] **Step 5: Record the verification outcomes**

Append a short `verification.md` note to the snapshot directory:

```bash
cat > ~/src/Cowork/litmap/docs/skills/snapshots/2026-04-25-post-edit/zotero-verification.md <<'EOF'
# zotero SKILL.md Tier 4 verification

Date: <fill in>

- [x] Test 4a (NL query) — passed / failed: <one-line outcome>
- [x] Test 4b (paper-to-paper) — passed / failed: <one-line outcome>
- [x] Test 4c (cluster outline) — passed / failed: <one-line outcome>
- [ ] Test 5 (litmap unavailable) — skipped / passed
EOF
```

Edit the placeholders, then commit:

```bash
cd ~/src/Cowork/litmap
git add docs/skills/snapshots/2026-04-25-post-edit/zotero-verification.md
git commit -m "docs: zotero skill Tier 4 verification record

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

If any test failed, do not proceed to Task 6 — fix the skill text or the routing first, re-run that test, then commit.

---

### Task 6: Update `manuscript-audit` front matter + add Claude-Code-only banner

**Files:**
- Modify: `$SKILLS_ROOT/manuscript-audit/SKILL.md` (lines ~1–10 and the H1 region)

---

- [ ] **Step 1: Read the front matter**

```bash
head -10 "$SKILLS_ROOT/manuscript-audit/SKILL.md"
```

The current front matter has `description: "Audit and polish scientific manuscripts ..."` and a `compatibility:` line.

- [ ] **Step 2: Append the Claude-Code-only marker to the description**

Locate the `description:` line. Append `(Claude Code only — uses litmap for semantic citation-gap detection.)` immediately before the closing quote and after the existing trailing period.

The resulting line should end with:
```
... 'check my paper,' or 'prepare for submission.'. (Claude Code only — uses litmap for semantic citation-gap detection.)"
```

- [ ] **Step 3: Update the `compatibility:` line**

Change the existing `compatibility: "Requires zotero skill, pdf-reading skill, file-reading skill (if manuscript uploaded as file)"` to:

```yaml
compatibility: "Claude Code only. Requires zotero skill, pdf-reading skill, file-reading skill (if manuscript uploaded as file), and a working `uv run litmap` install at ~/src/Cowork/litmap."
```

- [ ] **Step 4: Insert the runtime banner under the H1**

Find the line `# Manuscript Audit for Scientific Journal Submission` and immediately below it (before the next paragraph), insert:

```markdown
> ⚠️ **Runtime: Claude Code only.** This skill calls `uv run litmap …` against `~/LitLake/embeddings.db` on the local machine. It will not work in the Cowork web sandbox. If you reached this skill from the Cowork web frontend, stop and switch to Claude Code.

```

- [ ] **Step 5: Verify**

```bash
grep -c "Claude Code only" "$SKILLS_ROOT/manuscript-audit/SKILL.md"  # expect ≥3 (description, compatibility, banner)
grep -c "^> ⚠️ \*\*Runtime: Claude Code only" "$SKILLS_ROOT/manuscript-audit/SKILL.md"  # expect 1
```

---

### Task 7: Rewrite `manuscript-audit` Stage 2 procedure

**Files:**
- Modify: `$SKILLS_ROOT/manuscript-audit/SKILL.md` (the `## Stage 2:` section)

The current Stage 2 section says (paraphrased): "identifies unsupported claims and suggests citations via semantic search of the library; falls back to keyword search if litmap unavailable."

We replace the entire Stage 2 procedural content with the new procedure. Stage 1, 3, and 4 are untouched.

---

- [ ] **Step 1: Locate Stage 2 boundaries**

```bash
grep -n "^## Stage " "$SKILLS_ROOT/manuscript-audit/SKILL.md"
```

You'll see four headings (Stage 1, 2, 3, 4). Identify the line numbers of `## Stage 2: ...` and `## Stage 3: ...`. The block to replace is everything between them (exclusive of the Stage 3 line itself).

- [ ] **Step 2: Read the existing Stage 2 block to confirm what's being replaced**

```bash
sed -n '<stage2_line>,<stage3_line - 1>p' "$SKILLS_ROOT/manuscript-audit/SKILL.md" | head -80
```

Note any external references (e.g., the reference list built in Stage 1) so the new text uses the same names.

- [ ] **Step 3: Replace the Stage 2 block**

Delete every line from the Stage 2 heading to the line just before the Stage 3 heading. Insert the following replacement (preserve the exact `## Stage 2: ...` heading wording from the existing file — copy that line first, then the new body):

```markdown
## Stage 2: Citation Gap Detection (Semantic)

> Calls `litmap search` against the user's local embeddings database. Requires Claude Code runtime — see banner above.

### Input
- Manuscript (docx, pdf, or pasted text)
- Reference list built in Stage 1
- User's Zotero library (read via the zotero skill)
- (Optional) `--collection` scope if the user named one

### Procedure

1. **Identify unsupported claims.** Scan the manuscript for empirical or theoretical assertions that lack an in-text citation. Build a list of records:

    ```
    {claim_text, sentence_context, section_heading}
    ```

    where `sentence_context` is the claim's sentence plus the one preceding sentence (for query disambiguation).

2. **(Optional, ≥30 unique citations only) Up-front cluster overview.**

    ```bash
    uv run --project ~/src/Cowork/litmap litmap cluster \
      --manuscript <manuscript_path> \
      --output /tmp/audit_clusters \
      --format md
    ```

    Read `/tmp/audit_clusters.md` and present the thematic outline before per-claim analysis. The user can use this to spot whole topic areas that are over- or under-cited.

3. **Per-claim semantic search.** For each unsupported-claim record, call:

    ```bash
    uv run --project ~/src/Cowork/litmap litmap search \
      --query "<claim_text>. <sentence_context>" \
      [--collection "<scope>"] \
      --top-k 5 --format json
    ```

    `--collection` is included only if the user named one (e.g., "audit my manuscript against my Chapter 2 refs only").

4. **Filter candidates.**
    - Drop any candidate already cited in the manuscript (compare DOI first, then `lastname year` against the Stage 1 reference list).
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

    If no candidates clear the threshold, write plainly:
    > "No semantically similar papers in your library. Consider broader literature search outside the local Zotero collection."

### Failure modes

- **Cluster step fails** (e.g., < 2 cited papers found in Zotero): skip silently, proceed to per-claim search.
- **`litmap` unavailable**: emit the install message ("Run `uv pip install -e .` from `~/src/Cowork/litmap`") and abort Stage 2. Do not silently fall back to keyword search — the user explicitly requested a semantic audit.
- **Manuscript scope mismatch**: if `--collection X` was passed but X has fewer than 5 papers, warn the user and offer to broaden.
```

- [ ] **Step 4: Verify the replacement parsed**

```bash
grep -c "^## Stage 2: Citation Gap Detection (Semantic)" "$SKILLS_ROOT/manuscript-audit/SKILL.md"  # expect 1
grep -c "Per-claim semantic search"        "$SKILLS_ROOT/manuscript-audit/SKILL.md"  # expect 1
grep -c "similarity < 0.75"                "$SKILLS_ROOT/manuscript-audit/SKILL.md"  # expect 1
grep -c "Up-front cluster overview"        "$SKILLS_ROOT/manuscript-audit/SKILL.md"  # expect 1
grep -c "Stage 2 keyword fallback"         "$SKILLS_ROOT/manuscript-audit/SKILL.md"  # expect 0
grep -c "^## Stage 3"                      "$SKILLS_ROOT/manuscript-audit/SKILL.md"  # expect 1 (Stage 3 still present)
```

All six counts must match.

- [ ] **Step 5: Snapshot and commit**

```bash
cp "$SKILLS_ROOT/manuscript-audit/SKILL.md" ~/src/Cowork/litmap/docs/skills/snapshots/2026-04-25-post-edit/manuscript-audit.SKILL.md
cd ~/src/Cowork/litmap
git add docs/skills/snapshots/2026-04-25-post-edit/manuscript-audit.SKILL.md
git commit -m "docs: post-edit snapshot of manuscript-audit SKILL.md (Stage 2 rewrite)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

### Task 8: Verify `manuscript-audit` Stage 2 against a sample manuscript

**Files:** none modified.

---

- [ ] **Step 1: Pick a sample manuscript**

Use any small manuscript-style file the user has on disk. A 5–10-page PDF with a reference list works best. If none is at hand, ask the user. Note its path as `$MS`.

- [ ] **Step 2: Run the skill**

In Claude Code, ask the host:

> "Audit `<path-to-MS>` for citation gaps using my Zotero library."

Expected behaviour:
- Stage 1 runs (citation extraction + retraction check) — already known to work.
- Stage 2 begins. If the manuscript has ≥30 unique citations, an up-front cluster outline appears first.
- For each unsupported claim, the skill invokes `litmap search` and shows up to 3 candidates with similarity scores ≥ 0.75 (or "no semantically similar papers" if none qualify).
- Stage 3 (logical-consistency) and Stage 4 (copyediting) run after Stage 2 — these were not modified.

- [ ] **Step 3: Inspect a representative claim**

Pick one Stage 2 suggestion at random. Verify the suggested paper actually exists in `~/Zotero/zotero.sqlite` by running a Tier 1 query:

```bash
uv run --project ~/src/Cowork/litmap python -c "
import sqlite3
conn = sqlite3.connect('$HOME/Zotero/zotero.sqlite')
key = '<zotero_key from suggestion>'
print(conn.execute('SELECT key FROM items WHERE key = ?', (key,)).fetchone())
"
```

Expected: a tuple containing the same key. None means the skill returned a stale or invalid key — investigate before declaring success.

- [ ] **Step 4: Test the unavailable-litmap path (optional)**

Temporarily set `PATH` to exclude `uv` (or pass an invalid `--project`), re-run the audit. Expected: Stage 2 emits the install message and aborts (does NOT silently fall back to keyword search). Restore environment afterwards.

- [ ] **Step 5: Record verification**

```bash
cat > ~/src/Cowork/litmap/docs/skills/snapshots/2026-04-25-post-edit/manuscript-audit-verification.md <<'EOF'
# manuscript-audit Stage 2 verification

Date: <fill in>
Sample manuscript: <path>

- [x] Stage 2 ran on sample manuscript
- [x] Per-claim suggestions shown (or "no matches" message where applicable)
- [x] At least one suggested paper verified to exist in zotero.sqlite
- [ ] Cluster overview appeared (only if ≥30 unique citations)
- [ ] litmap-unavailable error path tested (optional)
EOF
```

Edit placeholders, commit:

```bash
cd ~/src/Cowork/litmap
git add docs/skills/snapshots/2026-04-25-post-edit/manuscript-audit-verification.md
git commit -m "docs: manuscript-audit Stage 2 verification record

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

If verification failed, do not announce completion — fix the skill text and re-run.

- [ ] **Step 6: Final cleanup**

If everything works, the `.bak` rollback files at the runtime location can stay in place indefinitely (they are tiny). If the user wants them removed:

```bash
rm "$SKILLS_ROOT/zotero/SKILL.md.bak" "$SKILLS_ROOT/manuscript-audit/SKILL.md.bak"
```

(Skip this step unless requested.)

---

## Self-review notes

- **Spec coverage check:**
  - §2 architecture (banner, `--project` invocation) → Task 2 Step 3, Task 6 Step 4.
  - §3.1 zotero header changes → Task 2.
  - §3.2 Tier 4 patterns 4a/4b/4c → Task 3.
  - §3.3 tier-selection flowchart → Task 4 Step 2.
  - §3.4 cross-tier integration rules → Task 4 Step 3.
  - §3.5 errors & edge cases → Task 4 Step 3 (table).
  - §4.1 manuscript-audit header → Task 6.
  - §4.2 Stage 2 procedure → Task 7.
  - §4.3 failure modes → Task 7 Step 3.
  - §4.4 removal of keyword-fallback paragraph → Task 7 Step 4 (the `expect 0` grep).
  - §5 testing checklist → Tasks 5 and 8.
- **Placeholder scan:** No TBD/TODO/"add error handling". All grep counts have explicit expected values. The user-fill-in placeholders in `verification.md` are explicitly bracketed and not part of the executable plan.
- **Type / name consistency:** All path variables consistently named `$SKILLS_ROOT` and `$MS`. All skill paths use the `~/Library/Application Support/Claude/...` pattern. The `--project ~/src/Cowork/litmap` form appears identically in every example. The threshold `0.75` appears once (Task 7) and matches the spec.
- **Known limitation:** the runtime SKILL.md files are not under git. Snapshots in the litmap repo provide audit trail and rollback. Rollback procedure: `cp $SKILLS_ROOT/<skill>/SKILL.md.bak $SKILLS_ROOT/<skill>/SKILL.md`.
