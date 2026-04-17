# Search Deduplication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deduplicate `litmap search` results so the same paper added to Zotero multiple times under different keys only appears once in the top-k output.

**Architecture:** Extract a `deduplicate_results` function into `search.py` that collapses enriched result dicts by DOI (primary) then normalised title (fallback), keeping the highest-scoring entry for each unique paper. `search_cmd` in `cli.py` fetches `top_k * 4` candidates upfront so deduplication still yields `top_k` unique results.

**Tech Stack:** Python stdlib only — no new dependencies.

---

### Task 1: Add `deduplicate_results` to `search.py` and test it

**Files:**
- Modify: `litmap/search.py` (add function after `find_similar`)
- Modify: `tests/test_search.py` (add three new tests)

---

- [ ] **Step 1: Write three failing tests in `tests/test_search.py`**

Add these tests after the existing ones. Note: `deduplicate_results` takes a list of enriched result dicts (each with `"doi"`, `"title"`, `"similarity"` keys — same shape as what `search_cmd` builds) and an integer `top_k`.

```python
from litmap.search import find_similar, extract_proper_nouns, deduplicate_results


def test_dedup_by_doi_keeps_highest_score():
    """Two entries with the same DOI → only the higher-scoring one survives."""
    results = [
        {"doi": "10.1234/abc", "title": "Paper A",  "similarity": 0.95},
        {"doi": "10.1234/abc", "title": "Paper A",  "similarity": 0.80},
        {"doi": "10.9999/xyz", "title": "Paper B",  "similarity": 0.70},
    ]
    deduped = deduplicate_results(results, top_k=10)
    assert len(deduped) == 2
    assert deduped[0]["similarity"] == 0.95
    dois = [r["doi"] for r in deduped]
    assert dois.count("10.1234/abc") == 1


def test_dedup_by_title_when_no_doi():
    """Two entries with no DOI but same title → only the first (highest score) survives."""
    results = [
        {"doi": "",  "title": "Ecology of Networks", "similarity": 0.90},
        {"doi": "",  "title": "Ecology of Networks", "similarity": 0.85},
        {"doi": "",  "title": "Climate and Change",  "similarity": 0.60},
    ]
    deduped = deduplicate_results(results, top_k=10)
    assert len(deduped) == 2
    assert deduped[0]["title"] == "Ecology of Networks"
    assert deduped[0]["similarity"] == 0.90


def test_dedup_respects_top_k():
    """After deduplication, result list is truncated to top_k."""
    results = [
        {"doi": f"10.1/{i}", "title": f"Paper {i}", "similarity": 1.0 - i * 0.01}
        for i in range(20)
    ]
    deduped = deduplicate_results(results, top_k=5)
    assert len(deduped) == 5
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd ~/src/Cowork/litmap
uv run pytest tests/test_search.py::test_dedup_by_doi_keeps_highest_score \
              tests/test_search.py::test_dedup_by_title_when_no_doi \
              tests/test_search.py::test_dedup_respects_top_k -v
```

Expected: `ImportError: cannot import name 'deduplicate_results'`

- [ ] **Step 3: Add `deduplicate_results` to `litmap/search.py`**

Add this function after `find_similar` and before the `_PROPER_NOUN_RE` definition:

```python
def deduplicate_results(
    enriched: list[dict],
    top_k: int,
) -> list[dict]:
    """Collapse duplicate papers from enriched search results.

    Deduplication key: DOI (lowercased, stripped) if non-empty,
    otherwise normalised title (lowercased, stripped).
    Input must already be sorted by descending similarity — the first
    occurrence of each canonical key is kept (highest score wins).
    Returns at most top_k entries.
    """
    seen: set[str] = set()
    unique: list[dict] = []
    for r in enriched:
        doi = (r.get("doi") or "").strip().lower()
        title = (r.get("title") or "").strip().lower()
        canon = doi if doi else title
        if not canon:
            unique.append(r)  # no dedup key available — keep as-is
            continue
        if canon not in seen:
            seen.add(canon)
            unique.append(r)
        if len(unique) == top_k:
            break
    return unique
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/test_search.py -v
```

Expected: all 9 tests pass (6 existing + 3 new).

- [ ] **Step 5: Commit**

```bash
git add litmap/search.py tests/test_search.py
git commit -m "feat: add deduplicate_results to search.py"
```

---

### Task 2: Wire deduplication into `search_cmd` in `cli.py`

**Files:**
- Modify: `litmap/cli.py` lines ~169–194 (`search_cmd`)

---

- [ ] **Step 1: Update the `find_similar` call and add deduplication**

In `litmap/cli.py`, replace the `find_similar` call and the enrichment block:

**Before (lines ~169–184):**
```python
    results = find_similar(query_vec, db_path, scope_keys=scope_keys, top_k=top_k, exclude_key=exclude_key)

    # Enrich with Zotero metadata
    all_items = {i.key: i for i in get_all_items(zotero_db)}
    enriched = []
    for r in results:
        item = all_items.get(r["key"])
        enriched.append({
            "zotero_key": r["key"],
            "title": item.title if item else r["key"],
            "authors": item.authors if item else [],
            "year": item.year if item else "",
            "abstract": item.abstract if item else "",
            "similarity": round(r["similarity"], 4),
            "doi": item.doi if item else "",
        })
```

**After:**
```python
    # Fetch extra candidates so deduplication still yields top_k unique results
    results = find_similar(query_vec, db_path, scope_keys=scope_keys, top_k=top_k * 4, exclude_key=exclude_key)

    # Enrich with Zotero metadata
    from litmap.search import deduplicate_results
    all_items = {i.key: i for i in get_all_items(zotero_db)}
    enriched_all = []
    for r in results:
        item = all_items.get(r["key"])
        enriched_all.append({
            "zotero_key": r["key"],
            "title": item.title if item else r["key"],
            "authors": item.authors if item else [],
            "year": item.year if item else "",
            "abstract": item.abstract if item else "",
            "similarity": round(r["similarity"], 4),
            "doi": item.doi if item else "",
        })

    enriched = deduplicate_results(enriched_all, top_k=top_k)
```

The import for `find_similar` is already at the top of `search_cmd`; the new `deduplicate_results` import is added inline with the other lazy imports.

- [ ] **Step 2: Run the full test suite**

```bash
uv run pytest tests/ -q
```

Expected: 35 passed (32 existing + 3 new).

- [ ] **Step 3: Commit**

```bash
git add litmap/cli.py
git commit -m "feat: deduplicate search results by DOI / normalised title

Zotero libraries often contain the same paper imported multiple times
under different keys. Fetch top_k*4 candidates then collapse duplicates
(DOI-first, then lowercased title), keeping the highest-scoring entry
per unique paper before truncating to top_k."
```
