---
name: manuscript-audit
description: "Audit and polish scientific manuscripts for journal submission. Use this skill whenever the user has a manuscript draft (docx, pdf, or pasted text) for peer review. The skill performs four passes: (1) extracts all author-year citations and verifies claims against original PDFs in the user's Zotero library to ensure faithfulness, consulting the manuscript's reference list to disambiguate author-year citations; (2) identifies unsupported or weakly supported claims and suggests additional citations via semantic search of the library; (3) checks for logical inconsistencies, contradictions, and reasoning gaps within the manuscript; (4) copyedits for grammar, style, punctuation, flow, and journal conventions. Trigger on phrases like 'audit my manuscript,' 'review my citations,' 'fact-check my claims,' 'check my paper,' or 'prepare for submission.'"
compatibility: "Requires zotero skill, pdf-reading skill, file-reading skill (if manuscript uploaded as file)"
---

# Manuscript Audit for Scientific Journal Submission

A four-stage workflow to verify citations against sources, identify evidence gaps, detect logical flaws, and polish a manuscript draft before submission.

---

## Stage 1: Citation Extraction & Faithfulness Audit

### Input
- Manuscript (docx, pdf, or pasted text)
- User's Zotero library (via zotero skill)

### Process

1. **Extract reference list:** Locate the References or Bibliography section in the manuscript. Build a lookup table: `author_year → [full citation text, DOI/URL if present]`.

2. **Extract in-text citations:** Use regex to find all author-year patterns:
   - `Smith 2020`
   - `(Jones et al. 2019)`
   - `Smith and Brown 2018`
   - `(Smith 2020; Brown 2021)`
   
   For each citation, record: the matched text, the sentence/paragraph context, the section heading, and the claim being supported.

3. **Disambiguate via reference list:** For each in-text citation, match it to the reference list entry to confirm author names, year, and full publication details. Flag any mismatches (e.g., cited as "Smith 2020" but reference list shows "Smith, J. 2019").

4. **Check for retracted papers (Zotero 9):** Before opening any PDFs, query the `retractedItems` table for every paper matched in the database:

   ```python
   retracted = {
       r[0]: r[1]
       for r in conn.execute("SELECT itemID, data FROM retractedItems").fetchall()
   }
   ```

   If any cited paper's itemID appears in `retracted`, flag it at the very top of the Stage 1 report with a ⛔ **RETRACTED** verdict and the retraction data (journal notice, date if available). The author must address this before submission — retracted papers should not be cited without explicit acknowledgement of retraction status.

4b. **Locate PDFs in Zotero:** Query the Zotero SQLite database directly rather than grepping filenames. Filename-based search is unreliable for two reasons: (a) auto-generated filenames may not include the author name at all (e.g., an organisation such as "Nature Positive Initiative" may be saved under the document title), and (b) overly broad filename patterns return hundreds of false positives, making truncation errors likely. Instead, run a Python query against `zotero.sqlite`:

   ```python
   import sqlite3
   conn = sqlite3.connect('/mnt/Zotero/zotero.sqlite')
   query = '''
   SELECT i.key, c.lastName, c.firstName, idv_year.value AS year,
          idv_title.value AS title, ia.path
   FROM items i
   JOIN itemCreators ic ON ic.itemID = i.itemID AND ic.orderIndex = 0
   JOIN creators c ON c.creatorID = ic.creatorID
   LEFT JOIN itemData id_year ON id_year.itemID = i.itemID
       AND id_year.fieldID = (SELECT fieldID FROM fields WHERE fieldName = 'date')
   LEFT JOIN itemDataValues idv_year ON idv_year.valueID = id_year.valueID
   LEFT JOIN itemData id_title ON id_title.itemID = i.itemID
       AND id_title.fieldID = (SELECT fieldID FROM fields WHERE fieldName = 'title')
   LEFT JOIN itemDataValues idv_title ON idv_title.valueID = id_title.valueID
   LEFT JOIN itemAttachments ia ON ia.parentItemID = i.itemID
   WHERE c.lastName LIKE ? AND idv_year.value LIKE ?
   '''
   results = conn.execute(query, ('%He%', '2015%')).fetchall()
   ```

   Substitute the author's last name and year from the reference list. For multi-word organisation names (e.g. "Nature Positive Initiative"), search by the first distinctive word as `lastName LIKE '%Nature Positive%'` or search by title keywords instead. The `path` field returned is of the form `storage:filename.pdf`; prepend `/mnt/Zotero/storage/<key>/` using the item key to get the full path. If multiple results are returned for the same author+year, use the title from the reference list entry to select the correct one.

   **Important:** Zotero PDF filenames are generated automatically and may contain errors — misspelled author names, wrong years, truncated titles. Never use a filename mismatch as evidence of a citation error in the manuscript. Always resolve ambiguity by matching against the full reference list entry (title, journal, DOI), not the filename alone.

4c. **Check for reading notes:** Once a Zotero item is matched, query any attached reading notes as a secondary source before opening the PDF:

   ```python
   from bs4 import BeautifulSoup

   notes = conn.execute(
       "SELECT note FROM itemNotes WHERE parentItemID = ?",
       (matched_item_id,)
   ).fetchall()

   for (note_html,) in notes:
       soup = BeautifulSoup(note_html, 'html.parser')
       hr = soup.find('hr')
       if hr:
           summary_text = ' '.join(t.get_text() for t in hr.previous_siblings)
           dy_text = ' '.join(t.get_text() for t in hr.next_siblings)
       else:
           summary_text = soup.get_text()
           dy_text = ''
   ```

   Use **PDF summary sections** (content before `<hr/>`) to quickly locate passages relevant to the claim — they save time when skimming a long PDF. Treat as helpful but non-authoritative; always confirm any finding against the PDF itself.

   Use **DY sections** (content after `<hr/>`) as context only for understanding how the paper was intended to be used. Never cite DY content in a faithfulness verdict.

   In the Stage 1 output, add a Notes subsection where reading notes exist:

   ```
   Notes (Zotero reading notes — secondary source, verify against PDF):
     [Relevant excerpt from PDF summary section]

   DY context (personal use-case notes — not a faithfulness source):
     [Relevant excerpt from DY section, if any]
   ```

5. **Extract and verify:** For each PDF found:
   - Extract full text using pdf-reading skill
   - Search for keywords from the claim (nouns, key concepts)
   - Extract relevant passages (context: 2–3 sentences before/after the keyword)
   - Compare the claim in the manuscript to the passage in the PDF
   - Record verdict: ✓ **Faithful** (claim matches source), ⚠ **Overstated** (claim goes beyond source), ✗ **Unsupported** (no matching passage found), or **Partial** (only part of the claim is supported)

5b. **Check for unquoted verbatim phrases:** While the PDF text is in hand, also scan the manuscript sentence(s) surrounding this citation for word-for-word borrowing from the source that is not enclosed in quotation marks. A run of 5 or more consecutive words appearing identically in both texts is a strong signal; 4 words is worth flagging if the phrasing is distinctive (e.g. a notable characterisation like "notoriously difficult").

   ```python
   import re

   def ngrams(text, n):
       words = re.findall(r'\b\w+\b', text.lower())
       return [tuple(words[i:i+n]) for i in range(len(words) - n + 1)]

   manuscript_context = # the 1-3 sentences around the citation in the manuscript
   pdf_text = # full PDF text

   for n in (6, 5, 4):
       ms_grams = set(ngrams(manuscript_context, n))
       pdf_grams = set(ngrams(pdf_text, n))
       matches = ms_grams & pdf_grams
       if matches:
           # reconstruct matched phrase and check it isn't already in quotes
           for gram in matches:
               phrase = ' '.join(gram)
               # check manuscript context for surrounding quote marks
               pattern = r'["\u201c\u201d\u2018\u2019][^"]*' + re.escape(phrase)
               if not re.search(pattern, manuscript_context.lower()):
                   flag_unquoted(phrase, manuscript_context)
   ```

   Flag any match with the verdict **⚠ Unquoted verbatim phrase** and report:
   - The matched phrase
   - The original sentence in the manuscript
   - The source sentence from the PDF
   - A suggested fix: either wrap in quotation marks and add a page reference, or paraphrase

   Report format:

   ```
   ⚠ Unquoted verbatim phrase — Smith et al. 2020

   Manuscript: "...measuring biodiversity is notoriously difficult and expensive..."
   Source:     "...measuring biodiversity is notoriously difficult in all fields..."

   Matched phrase: "measuring biodiversity is notoriously difficult"

   Fix: Either quote directly — 'measuring biodiversity is "notoriously difficult"
   (Marshall et al. 2020, p. X)' — or paraphrase to make the wording clearly your own.
   ```

6. **Missing PDFs:** Before flagging a paper as absent, always: (a) search Zotero using variant spellings, partial author names, and keywords from the title; (b) check the manuscript's full reference list (which may be in a separate document if the PDF says "reference list located elsewhere") for the complete citation details, then re-search. Only flag as "PDF not found in library" after both steps have been attempted. When flagging, include the full reference entry from the reference list so the user can verify.

7. **Web fallback for missing PDFs:** If a PDF is not found in Zotero after step 6, attempt to retrieve the source from the web using the DOI or URL recorded in the reference list entry. Use the WebFetch tool with the DOI URL (e.g., `https://doi.org/10.xxxx/xxxxx`) or the direct URL if one is given. If the fetch succeeds, treat the retrieved content as the source for claim verification and proceed with the usual faithfulness check. If the fetch is blocked by the network proxy (`EGRESS_BLOCKED` error), record this explicitly and note: "PDF not in Zotero; web access blocked — claim could not be independently verified. Reference entry: [full citation]." In either case (success or blocked), include the full reference list entry in the report. **Never silently skip verification for a missing PDF** — always report what was attempted and what was found.

### Output Format

For each citation, report:

```
[Citation ID] Smith et al. 2020

Claim: "Biodiversity loss is accelerating globally (Smith et al. 2020)."

Verdict: ✓ Faithful
Source passage: "Our analysis shows accelerating declines in species richness 
across terrestrial and marine ecosystems over the past two decades."

Confidence: High (exact match to claim)

---
```

Alternatively for overstatement:

```
[Citation ID] Jones 2019

Claim: "All temperate forests show declining productivity (Jones 2019)."

Verdict: ⚠ Overstated
Source passage: "Productivity declines were observed in 68% of sampled 
temperate forests in North America."

Issue: The manuscript claims universality; the source reports 68% prevalence. 
Suggest: "Most temperate forests show declining productivity (Jones 2019)."

---
```

---

## Stage 2: Citation Gap Detection & Suggestion

### Step 0 — Resolve `(REFS)` Placeholders First

Before scanning for implicit gaps, check whether the author has explicitly marked citation gaps with a `(REFS)` placeholder. These are the highest-priority gaps because the author already knows a citation is needed.

**Detect placeholders:**

```bash
grep -n "REFS" manuscript.txt
```

Or in Python on the extracted text:

```python
import re
for m in re.finditer(r'\bREFS\b', text):
    start = text.rfind('\n', 0, m.start()) + 1
    end = text.find('\n', m.end())
    print(f"Line {text[:m.start()].count(chr(10))+1}: {text[start:end].strip()}")
```

For each `(REFS)` occurrence, extract **5–10 lines of surrounding context** — enough to understand the full claim being supported, including any citations already present in the same sentence or parenthetical cluster (they reveal the topic and the kind of evidence expected).

**Understand the claim:** Identify:
- The core assertion (what is being claimed?)
- The type of evidence expected (empirical study? review? methodology paper? grey literature?)
- The implied audience (e.g., a claim about audit standards needs assurance/accounting literature; a claim about SDMs needs ecology literature; a claim about market mechanisms needs economics literature)
- Whether the REFS is additive (joining a cluster of existing citations) or the sole citation for the claim

**Search Zotero for candidates using two tiers:**

*Tier 1 — Metadata search* (titles and abstracts): Cast a moderately wide net using 2–3 keywords from the claim. Run separate queries for different facets of the claim — e.g., for a claim about "audit costs enabling deterrence," search both `['audit', 'assurance', 'verification']` and `['deterrence', 'monitoring cost', 'principal agent']`.

```python
import sqlite3
conn = sqlite3.connect('/mnt/Zotero/zotero.sqlite')

def search_metadata(keywords, lib_id=7, limit=12):
    placeholders = ' OR '.join(["(tv.value LIKE ? OR av.value LIKE ?)"] * len(keywords))
    params = [f'%{kw}%' for kw in keywords for _ in range(2)]
    params.append(lib_id)
    return conn.execute(f"""
        SELECT DISTINCT i.itemID, i.key, tv.value AS title, dv.value AS date,
               GROUP_CONCAT(c.lastName, ', ') AS authors, av.value AS abstract
        FROM items i
        JOIN itemData td ON i.itemID = td.itemID AND td.fieldID = 1
        JOIN itemDataValues tv ON td.valueID = tv.valueID
        LEFT JOIN itemData dd ON i.itemID = dd.itemID AND dd.fieldID = 6
        LEFT JOIN itemDataValues dv ON dd.valueID = dv.valueID
        LEFT JOIN itemData ad ON i.itemID = ad.itemID AND ad.fieldID = 2
        LEFT JOIN itemDataValues av ON ad.valueID = av.valueID
        LEFT JOIN itemCreators ic ON i.itemID = ic.itemID AND ic.orderIndex = 0
        LEFT JOIN creators c ON ic.creatorID = c.creatorID
        WHERE ({placeholders}) AND i.libraryID = ?
        AND i.itemTypeID NOT IN (14, 26)
        GROUP BY i.itemID LIMIT {limit}
    """, params).fetchall()
```

*Tier 2 — Full-text index* (when Tier 1 returns few results): Intersect single words across Zotero's indexed PDFs.

```python
def search_fulltext(words, lib_id=7, limit=10):
    intersects = " INTERSECT ".join([
        f"SELECT fiw.itemID FROM fulltextWords fw "
        f"JOIN fulltextItemWords fiw ON fw.wordID = fiw.wordID "
        f"WHERE fw.word = '{w.lower()}'"
        for w in words
    ])
    return conn.execute(f"""
        SELECT DISTINCT i.itemID, i.key, tv.value, dv.value,
               GROUP_CONCAT(c.lastName, ', ') AS authors, av.value
        FROM items i
        JOIN itemData td ON i.itemID = td.itemID AND td.fieldID = 1
        JOIN itemDataValues tv ON td.valueID = tv.valueID
        LEFT JOIN itemData dd ON i.itemID = dd.itemID AND dd.fieldID = 6
        LEFT JOIN itemDataValues dv ON dd.valueID = dv.valueID
        LEFT JOIN itemData ad ON i.itemID = ad.itemID AND ad.fieldID = 2
        LEFT JOIN itemDataValues av ON ad.valueID = av.valueID
        LEFT JOIN itemCreators ic ON i.itemID = ic.itemID AND ic.orderIndex = 0
        LEFT JOIN creators c ON ic.creatorID = c.creatorID
        WHERE i.libraryID = ? AND i.itemID IN ({intersects})
        AND i.itemTypeID NOT IN (14, 26)
        GROUP BY i.itemID LIMIT {limit}
    """, (lib_id,)).fetchall()
```

**Filter and rank candidates:** Read the abstract of each candidate and assess:
- Does the paper directly support the claim, or only tangentially?
- Is it the right type of evidence (primary study, review, grey literature, canonical reference)?
- Is it already cited elsewhere in the manuscript? (Avoid suggesting duplicates unless the same paper is appropriate in multiple locations.)
- Does it serve the implied audience of the claim?

Discard weak matches. For strong candidates, retrieve full reference details (authors, year, title, journal, DOI) using the item key.

**Suggest no more than 3–4 candidates per REFS**, ranked by fit. For each, write one sentence explaining *why* it supports the specific claim — not just what the paper is about.

Note: if the REFS sits in a cluster with existing citations, candidates should complement rather than duplicate the existing papers. Read those existing citations' titles/abstracts briefly to understand what is already covered.

**Output format for REFS resolution:**

```
REFS — Line [N]
Context: "[the sentence(s) containing REFS, with surrounding citations if any]"
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

Deliver all REFS resolutions as a dedicated section before the general gap analysis below.

---

### Input
- The manuscript
- The faithfulness audit from Stage 1
- User's Zotero library

### Process

1. **Identify unsupported claims:** Flag all sentences/paragraphs with:
   - No citation
   - Citation verdict ✗ **Unsupported** or ⚠ **Overstated**
   - A citation to a paper that exists in Zotero but lacks the supporting passage

2. **Extract claim context:** For each flagged claim, extract:
   - The claim text (1–2 sentences)
   - The section heading
   - Key concepts (nouns, verbs, relationships)

3. **Search for candidates — three tiers:**

   **Tier 1 — Semantic search (primary, always runs):**
   Requires `litmap` to be installed (`uv run litmap --help` to verify).

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

   **Tier 2 — Narrow keyword pass (proper nouns, always runs alongside Tier 1):**
   Extract capitalised phrases, acronyms, and method/species names from the claim.
   Run a focused SQL `LIKE` query against Zotero titles and abstracts for each term.

   ```python
   import re, sqlite3

   def extract_proper_nouns(text: str) -> list[str]:
       pattern = re.compile(
           r'\b[A-Z]{2,}\b'
           r'|\b[A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2}\b'
       )
       skip = {"The", "A", "An", "In", "We", "Our", "This", "These", "For", "To"}
       seen, result = set(), []
       for m in pattern.findall(text):
           if m not in skip and m not in seen:
               seen.add(m); result.append(m)
       return result

   def keyword_exact(terms: list[str], conn) -> list[dict]:
       results = []
       for term in terms:
           rows = conn.execute("""
               SELECT DISTINCT i.key, tv.value AS title, av.value AS abstract,
                      dv.value AS year, doiv.value AS doi
               FROM items i
               JOIN itemData td ON i.itemID = td.itemID AND td.fieldID =
                   (SELECT fieldID FROM fields WHERE fieldName = 'title')
               JOIN itemDataValues tv ON td.valueID = tv.valueID
               LEFT JOIN itemData ad ON i.itemID = ad.itemID AND ad.fieldID =
                   (SELECT fieldID FROM fields WHERE fieldName = 'abstractNote')
               LEFT JOIN itemDataValues av ON ad.valueID = av.valueID
               LEFT JOIN itemData dd ON i.itemID = dd.itemID AND dd.fieldID =
                   (SELECT fieldID FROM fields WHERE fieldName = 'date')
               LEFT JOIN itemDataValues dv ON dd.valueID = dv.valueID
               LEFT JOIN itemData doid ON i.itemID = doid.itemID AND doid.fieldID =
                   (SELECT fieldID FROM fields WHERE fieldName = 'DOI')
               LEFT JOIN itemDataValues doiv ON doid.valueID = doiv.valueID
               WHERE (tv.value LIKE ? OR av.value LIKE ?)
               AND i.itemTypeID NOT IN (14, 26)
           """, (f'%{term}%', f'%{term}%')).fetchall()
           for r in rows:
               results.append({"zotero_key": r[0], "title": r[1] or "",
                                "year": (r[3] or "")[:4], "doi": r[4] or "",
                                "similarity": 0.0})
       return results
   ```

   **Merge Tier 1 + Tier 2:** deduplicate by `zotero_key`; semantic hits rank first (by similarity score); Tier-2-only hits append after.

   ```python
   def merge_results(semantic: list[dict], keyword: list[dict]) -> list[dict]:
       seen = {r["zotero_key"] for r in semantic}
       extra = [r for r in keyword if r["zotero_key"] not in seen]
       return semantic + extra
   ```

   **Fallback:** if `semantic_search` returns an empty list (litmap unavailable or no results),
   fall back to the original `search_metadata` + `search_fulltext` keyword searches.

4. **Rank and suggest:** For each candidate:
   - Check if the result's abstract/title matches the claim
   - Assign relevance: **Perfect match**, **Strong**, **Moderate**, **Weak**
   - Extract a brief snippet from the paper that supports the claim
   - Write a 1-sentence justification for why this paper fits

5. **Prioritize suggestions:** Recommend:
   - Up to 2 papers for claims with no citation
   - 1 replacement paper if the current citation is unsupported
   - 1–2 supplementary papers if the citation is weak or too narrow

### Output Format

```
[Claim Location] Results section, paragraph 3

Unsupported claim: "Deep learning models outperform traditional SDMs 
in predicting species distributions."

**Suggested citations:**

1. **Max et al. 2022** — "Deep learning for species distribution modeling: 
A benchmark study"
   Relevance: Perfect match
   Snippet: "Deep neural networks achieved 12% higher AUC than MaxEnt 
   models on average across 500 species."
   Justification: Directly compares deep learning to traditional SDMs with 
   quantitative results.

2. **Brown & Kim 2021** — "Machine learning in biodiversity prediction"
   Relevance: Strong
   Snippet: "Recent advances in neural networks have improved predictive 
   accuracy for spatial distribution models."
   Justification: Broader review of ML in SDMs; supports the claim but 
   is less specific than Max et al. 2022.

---
```

---

## Stage 3: Logical Consistency Check

### Input
- The manuscript (full text)
- Citation audit and gap analysis from Stages 1–2

### Process

1. **Extract key claims:** Scan the manuscript section-by-section and list major claims:
   - Research questions and hypotheses
   - Assertions about the state of knowledge (e.g., "X is understudied")
   - Methodological choices and their justifications
   - Results and interpretations
   - Implications and future directions

2. **Check for contradictions:** 
   - Do any two claims directly contradict each other?
   - Are terms used inconsistently (e.g., "biodiversity" defined one way in intro, used differently in discussion)?
   - Are definitions circular or vague?

3. **Check for reasoning gaps:**
   - Are logical leaps made without justification? (e.g., "Study X found Y; therefore Z" without connecting Y to Z)
   - Does the conclusion follow from the results?
   - Are assumptions stated explicitly?
   - Is the scope of claims matched to the scope of evidence?

4. **Check for scope creep:**
   - Are generalizations overstated? (e.g., "This study of 10 species shows that...")
   - Are causal claims made where only correlations are shown?
   - Are statements qualified appropriately? (e.g., "may," "likely," "in this region")

5. **Flag undefined or under-defined terms:**
   - Are key concepts (e.g., "resilience," "ecosystem services") defined before use?
   - Are acronyms introduced before first use?

### Output Format

```
**Contradiction detected** (Abstract vs. Introduction)

Abstract: "Remote sensing cannot reliably measure forest biomass."
Introduction: "High-resolution satellite data enable accurate biomass estimation."

Recommendation: Clarify the distinction (e.g., "passive optical remote sensing 
cannot reliably measure biomass; active LiDAR-based approaches are more 
promising").

---

**Reasoning gap** (Methods → Results)

Methods: "We used species occurrence data from iNaturalist."
Results: "Species richness patterns aligned with predictions."

Issue: The connection between iNaturalist (which is spatially biased toward 
populated areas) and richness predictions is not established. Does this 
bias affect the conclusions?

Recommendation: Add a limitations paragraph addressing data bias.

---

**Scope creep** (Results → Discussion)

Results: "In our 10-site study, SDM accuracy was 0.82 AUC."
Discussion: "Deep learning SDMs are highly accurate for predicting global 
species distributions."

Issue: Results from 10 sites do not support a global claim.

Recommendation: Qualify: "Our results suggest that deep learning SDMs may 
achieve high accuracy; further validation across diverse regions is needed."

---
```

---

## Stage 4: Copyediting Pass

### Input
- The full manuscript

### Process

1. **Grammar & mechanics:**
   - Subject-verb agreement
   - Tense consistency (past for completed work, present for established facts)
   - Pronoun reference clarity
   - Active vs. passive voice (prefer active where possible, but passive acceptable in methods)

2. **Clarity & concision:**
   - Wordy phrases (e.g., "in order to" → "to", "due to the fact that" → "because")
   - Unclear pronoun antecedents
   - Overly complex sentences (break into 2–3 shorter sentences if needed)
   - Jargon without definition

3. **Flow & transitions:**
   - Do paragraphs flow logically?
   - Are transitions between sections smooth?
   - Do topic sentences align with paragraph content?

4. **Style & consistency:**
   - Parallel structure in lists or comparisons
   - Consistent capitalization and formatting
   - Consistent citation style (author-year format; check for mixed styles)
   - Number formatting (spell out <10; numerals ≥10; exception: start of sentence)

5. **Common scientific writing issues:**
   - Hedging (excessive "may," "might," "could" — use sparingly and intentionally)
   - Present perfect tense misuse (e.g., "Studies have shown that X" — who? when?)
   - "Data" as singular (data is plural; use "datasets" or "data points" for singular)
   - Abbreviations introduced but not used; or used before introduction

6. **Sentence-level revisions:** Provide before/after examples.

### Output Format

```
**Grammar issue** (Page 3, Results)

Original: "The results shows that deep learning models performs better 
than traditional SDMs."

Corrected: "The results show that deep learning models perform better 
than traditional SDMs."

Issue: Subject-verb agreement (plural "results" requires "show" and "perform").

---

**Clarity issue** (Page 1, Abstract)

Original: "We used remote sensing and machine learning, which is a powerful 
combination for predicting species distributions."

Revised: "We combined remote sensing with machine learning to predict 
species distributions with high accuracy."

Issue: "which is a powerful combination" is vague and wordy. The revision 
is more direct and specific.

---

**Flow issue** (Page 5, Discussion, para. 2)

Original: [Three sentences about climate change] [Abrupt shift] [One sentence 
about policy implications]

Revised: Add a transition: "These findings have important implications for 
conservation policy..." before the policy sentence.

---

**Style issue** (Inconsistent number formatting)

Original: "We sampled 10 sites across 3 regions in 4 years."

Check: Are numbers <10 and ≥10 formatted consistently? Should be either: 
"We sampled ten sites across three regions in four years" (spell out all <10) 
OR "We sampled 10 sites across 3 regions in 4 years" (numerals for all). 
Pick one and apply throughout.

---
```

---

## Integration & Output

Run all four stages in sequence. Deliver:

1. **Annotated manuscript** with inline comments (via track changes or comment blocks)
2. **Summary report** listing:
   - **Citation audit:** # faithful, # overstated, # unsupported, # missing PDFs
   - **Citation gaps:** # claims without support, # suggested citations
   - **Logical issues:** # contradictions, # reasoning gaps, # scope creep, # undefined terms
   - **Copyediting:** # grammar issues, # clarity issues, # style issues

3. **Prioritized revision checklist** (must-fix vs. nice-to-fix) so the user can tackle the most important issues first.

---

## Dependencies

- **zotero skill** — to query the Zotero library and retrieve PDFs
- **pdf-reading skill** — to extract text from PDFs and verify claims
- **file-reading skill** (if docx/pdf uploaded) — to read the manuscript
- Standard regex and text processing (built-in)

---

## Workflow Notes

- **Timing:** Expect 10–20 minutes for an 8,000-word manuscript, depending on citation count and PDF availability.
- **Zotero integration:** Assumes Doug's Zotero library is accessible at `/mnt/Zotero/` (Cowork environment) or via the zotero skill.
- **Citation format:** Works with author-year citations (Smith 2020, Jones et al. 2019). Numbered citations [1], [2] require different parsing; confirm format before beginning.
- **Tone:** Citations and logical consistency feedback should be constructive and specific; copyediting suggestions should include examples and rationales.
- **Scope:** Focuses on peer-review readiness, not format compliance. For journal-specific formatting (e.g., Nature, Ecology Letters), recommend consulting target journal's author guidelines after audit.
