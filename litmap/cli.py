from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="Semantic map and search for Zotero libraries.")

_DEFAULT_DB    = Path.home() / "LitLake" / "embeddings.db"
_DEFAULT_ZOTERO = Path.home() / "Zotero" / "zotero.sqlite"


def _auto_sync(db_path: Path, zotero_db: Path) -> None:
    # Read-only consumer mode: when LITMAP_NO_SYNC is set, skip the implicit
    # pre-search sync so a machine whose embeddings.db is received via Syncthing
    # (receive-only folder) never writes to it -> no "Local Additions". The
    # explicit `litmap sync` / `sync-fulltext` commands are unaffected.
    import os
    if os.environ.get("LITMAP_NO_SYNC"):
        return
    from litmap.embedder import sync
    sync(db_path, zotero_db)


@app.command("map")
def map_cmd(
    collection: Optional[str] = typer.Option(None, "--collection", "-c", help="Zotero collection name"),
    manuscript: Optional[Path] = typer.Option(None, "--manuscript", "-m", help="Manuscript file (PDF/DOCX/LaTeX)"),
    union: bool = typer.Option(False, "--union", help="Use collection ∪ bibliography as paper set"),
    output: Path = typer.Option(Path("litmap_output"), "--output", "-o", help="Output base name"),
    n_neighbors: int = typer.Option(3, "--n-neighbors", help="UMAP n_neighbors"),
    edge_k: int = typer.Option(3, "--edge-k", help="k-NN edges per node"),
    fmt: str = typer.Option("all", "--format", "-f", help="html | pdf | png | all"),
    label_clusters: bool = typer.Option(True, "--label-clusters/--no-label-clusters", help="Annotate HDBSCAN clusters with TF-IDF keywords"),
    min_cluster_size: int = typer.Option(5, "--min-cluster-size", help="HDBSCAN min_cluster_size [default: 5]"),
    center_manuscript: bool = typer.Option(False, "--center-manuscript", help="Bias manuscript node toward centre of UMAP layout"),
    db_path: Path = typer.Option(_DEFAULT_DB, hidden=True),
    zotero_db: Path = typer.Option(_DEFAULT_ZOTERO, hidden=True),
):
    """Generate a 2D semantic map of papers."""
    from litmap.zotero import get_collection, get_all_items
    from litmap.manuscript import parse_bibliography, extract_manuscript_text, match_items_to_zotero
    from litmap.embedder import embed_text, load_all_fulltext_embeddings as load_all_embeddings, init_db
    from litmap.layout import compute_layout, build_graph, cluster_labels
    from litmap.renderer import render_html, render_static
    import numpy as np

    Path(output).parent.mkdir(parents=True, exist_ok=True)

    _auto_sync(db_path, zotero_db)

    # --- Assemble paper set -------------------------------------------------
    items = []
    manuscript_key = None

    if collection and manuscript and union:
        coll_items = get_collection(collection, zotero_db)
        bib_entries = parse_bibliography(manuscript)
        bib_items, _ = match_items_to_zotero(bib_entries, zotero_db)
        seen = {i.key for i in coll_items}
        extra = [i for i in bib_items if i.key not in seen]
        items = coll_items + extra
    elif collection and manuscript:
        items = get_collection(collection, zotero_db)
    elif collection:
        items = get_collection(collection, zotero_db)
    elif manuscript:
        bib_entries = parse_bibliography(manuscript)
        items, _ = match_items_to_zotero(bib_entries, zotero_db)
    else:
        typer.echo("Error: provide --collection and/or --manuscript", err=True)
        raise typer.Exit(1)

    if not items:
        typer.echo("No papers found.", err=True)
        raise typer.Exit(1)

    # --- Add manuscript node ------------------------------------------------
    if manuscript:
        ms_text = extract_manuscript_text(manuscript)
        ms_vec = embed_text(ms_text, db_path)
        manuscript_key = "__manuscript__"
        from litmap.zotero import Item
        ms_item = Item(
            key=manuscript_key,
            title=manuscript.stem,
            abstract="",
            authors=[],
            year="",
            doi="",
        )
        items = items + [ms_item]
        # Store manuscript embedding temporarily
        import sqlite3
        from datetime import datetime, timezone
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT OR REPLACE INTO embeddings (zotero_key, vector, embedded_at) VALUES (?, ?, ?)",
            (manuscript_key, ms_vec.tobytes(), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        conn.close()

    # --- Load embeddings ----------------------------------------------------
    keys = [i.key for i in items]
    matrix, loaded_keys = load_all_embeddings(db_path, scope_keys=keys)
    dropped = len(keys) - len(loaded_keys)
    if dropped > 0:
        typer.echo(
            f"Note: {dropped} of {len(keys)} papers have no embedding yet and were skipped. "
            f"Run `litmap sync` to embed them.",
            err=True,
        )
    if len(loaded_keys) < 2:
        typer.echo("Need at least 2 embedded papers.", err=True)
        raise typer.Exit(1)

    # Re-align items to loaded_keys order
    key_order = {k: idx for idx, k in enumerate(loaded_keys)}
    items = [i for i in items if i.key in key_order]

    # --- Layout + graph -----------------------------------------------------
    center_key = manuscript_key if (center_manuscript and manuscript_key) else None
    layout = compute_layout(matrix, loaded_keys, n_neighbors=n_neighbors, center_key=center_key)
    edges = build_graph(matrix, loaded_keys, k=edge_k)

    # --- Cluster labels -----------------------------------------------------
    annotations = {}
    if label_clusters and len(loaded_keys) >= min_cluster_size * 2:
        annotations = cluster_labels(layout, items, min_cluster_size=min_cluster_size)
        typer.echo(f"Found {len(annotations)} clusters.", err=True)

    # --- Render -------------------------------------------------------------
    if fmt in ("html", "all"):
        html = render_html(layout, edges, items, manuscript_key, cluster_annotations=annotations)
        html_path = Path(str(output) + ".html")
        html_path.write_text(html)
        typer.echo(f"Wrote {html_path}")
    if fmt in ("png", "pdf", "all"):
        render_static(layout, edges, items, manuscript_key, path=output, cluster_annotations=annotations)
        typer.echo(f"Wrote {output}.png and {output}.pdf")


@app.command("search")
def search_cmd(
    query: Optional[str] = typer.Option(None, "--query", "-q", help="Sentence or passage to search"),
    paper: Optional[str] = typer.Option(None, "--paper", "-p", help="Title or DOI of a Zotero paper"),
    collection: Optional[str] = typer.Option(None, "--collection", "-c", help="Scope to collection"),
    top_k: int = typer.Option(10, "--top-k", "-k", help="Number of results"),
    fmt: str = typer.Option("table", "--format", "-f", help="table | json"),
    db_path: Path = typer.Option(_DEFAULT_DB, hidden=True),
    zotero_db: Path = typer.Option(_DEFAULT_ZOTERO, hidden=True),
):
    """Find papers semantically similar to a query or focal paper."""
    from litmap.embedder import embed_text, init_db
    from litmap.search import find_similar, deduplicate_results
    from litmap.zotero import get_all_items, get_collection, get_item
    import numpy as np

    _auto_sync(db_path, zotero_db)

    exclude_key = None
    query_text = query

    if paper:
        focal = get_item(paper, zotero_db)
        if focal is None:
            # Suggest close matches
            all_items = get_all_items(zotero_db)
            from difflib import get_close_matches
            titles = [i.title for i in all_items]
            suggestions = get_close_matches(paper, titles, n=3, cutoff=0.5)
            typer.echo(f"Paper not found: {paper!r}", err=True)
            if suggestions:
                typer.echo("Did you mean:", err=True)
                for s in suggestions:
                    typer.echo(f"  {s}", err=True)
            raise typer.Exit(1)
        exclude_key = focal.key
        query_text = f"{focal.title} {focal.abstract}"

    if not query_text:
        typer.echo("Error: provide --query or --paper", err=True)
        raise typer.Exit(1)

    query_vec = embed_text(query_text, db_path)

    scope_keys = None
    if collection:
        items = get_collection(collection, zotero_db)
        scope_keys = [i.key for i in items]

    # Fetch extra candidates so deduplication still yields top_k unique results
    results = find_similar(query_vec, db_path, scope_keys=scope_keys, top_k=top_k * 4, exclude_key=exclude_key)

    # Enrich with Zotero metadata
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

    if fmt == "json":
        out = {"query": query_text[:120], "results": enriched}
        typer.echo(json.dumps(out, ensure_ascii=False))
    else:
        for i, r in enumerate(enriched, 1):
            authors = ", ".join(r["authors"][:2])
            typer.echo(f"{i:2}. [{r['similarity']:.3f}] {r['title'][:60]}")
            typer.echo(f"     {authors} {r['year']}  {r['doi']}")


@app.command("info")
def info_cmd(
    paper: str = typer.Argument(help="Title fragment, DOI, or Zotero key"),
    db_path: Path = typer.Option(_DEFAULT_DB, hidden=True),
    zotero_db: Path = typer.Option(_DEFAULT_ZOTERO, hidden=True),
):
    """Show embedding status for a paper."""
    import sqlite3
    from litmap.zotero import get_item, get_all_items
    from difflib import get_close_matches

    # Try exact match first (key or DOI)
    item = get_item(paper, zotero_db)

    # Fall back to fuzzy title match
    if item is None:
        all_items = get_all_items(zotero_db)
        titles = [i.title for i in all_items]
        matches = get_close_matches(paper, titles, n=1, cutoff=0.3)
        if matches:
            item = next(i for i in all_items if i.title == matches[0])

    if item is None:
        typer.echo(f"No paper found matching: {paper!r}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Title:      {item.title}")
    typer.echo(f"Authors:    {', '.join(item.authors[:3])}{' et al.' if len(item.authors) > 3 else ''}")
    typer.echo(f"Year:       {item.year}")
    typer.echo(f"DOI:        {item.doi or '—'}")
    typer.echo(f"Zotero key: {item.key}")
    typer.echo(f"PDF:        {item.pdf_path or '—'}")

    conn = sqlite3.connect(db_path)

    row = conn.execute(
        "SELECT embedded_at FROM embeddings WHERE zotero_key = ?", (item.key,)
    ).fetchone()
    typer.echo(f"\nTitle+abstract embedded: {'yes, ' + row[0][:10] if row else 'no'}")

    row = conn.execute(
        "SELECT n_tokens, n_chunks, embedded_at FROM fulltext_embeddings WHERE zotero_key = ?",
        (item.key,)
    ).fetchone()
    if row:
        typer.echo(f"Full-text embedded:      yes, {row[2][:10]} ({row[0]} tokens, {row[1]} chunk{'s' if row[1] != 1 else ''})")
    else:
        typer.echo("Full-text embedded:      no")

    conn.close()


@app.command("sync")
def sync_cmd(
    force: bool = typer.Option(False, "--force", help="Re-embed all papers, even those already in the cache"),
    db_path: Path = typer.Option(_DEFAULT_DB, hidden=True),
    zotero_db: Path = typer.Option(_DEFAULT_ZOTERO, hidden=True),
):
    """Sync Zotero items into embeddings DB. Use --force to regenerate all embeddings."""
    from litmap.embedder import sync
    count = sync(db_path, zotero_db, force=force)
    if count == 0:
        typer.echo("Already up to date.")
    else:
        typer.echo(f"Embedded {count} new papers.")


@app.command("sync-fulltext")
def sync_fulltext_cmd(
    collection: Optional[str] = typer.Option(None, "--collection", "-c", help="Scope to a Zotero collection"),
    force: bool = typer.Option(False, "--force", help="Re-embed even already-processed PDFs"),
    max_tokens: int = typer.Option(3000, "--max-tokens", help="Max tokens per chunk (default 3000; up to 8000)"),
    db_path: Path = typer.Option(_DEFAULT_DB, hidden=True),
    zotero_db: Path = typer.Option(_DEFAULT_ZOTERO, hidden=True),
):
    """Embed full PDF text for Zotero items with a local PDF attachment.

    Vectors are stored in the fulltext_embeddings table and automatically
    preferred over title+abstract embeddings in search, map, and cluster.
    Safe to interrupt and resume — already-embedded papers are skipped.
    Use --collection to process only a subset of your library.
    """
    from litmap.embedder import sync_fulltext, init_db
    init_db(db_path)
    n_embedded, n_no_pdf = sync_fulltext(db_path, zotero_db, force=force, max_tokens=max_tokens, collection=collection)
    scope = f"collection '{collection}'" if collection else "full library"
    typer.echo(f"Embedded {n_embedded} PDFs from {scope}. ({n_no_pdf} items had no local PDF and were skipped.)")


@app.command("cluster")
def cluster_cmd(
    collection: Optional[str] = typer.Option(None, "--collection", "-c", help="Zotero collection name"),
    manuscript: Optional[Path] = typer.Option(None, "--manuscript", "-m", help="Manuscript file (PDF/DOCX/LaTeX)"),
    union: bool = typer.Option(False, "--union", help="Use collection ∪ bibliography as paper set"),
    top_clusters: Optional[int] = typer.Option(None, "--top-clusters", help="Number of level-1 clusters"),
    subcluster_threshold: int = typer.Option(20, "--subcluster-threshold", help="Min cluster size that triggers level-2"),
    output: Path = typer.Option(Path("litmap_cluster"), "--output", "-o", help="Output base path"),
    fmt: str = typer.Option("all", "--format", "-f", help="html | pdf | png | md | json | all"),
    db_path: Path = typer.Option(_DEFAULT_DB, hidden=True),
    zotero_db: Path = typer.Option(_DEFAULT_ZOTERO, hidden=True),
):
    """Semantic hierarchical clustering of a paper set."""
    VALID_FORMATS = {"html", "pdf", "png", "md", "json", "all"}
    if fmt not in VALID_FORMATS:
        typer.echo(f"Error: --format must be one of {sorted(VALID_FORMATS)}", err=True)
        raise typer.Exit(1)

    from litmap.zotero import get_collection, get_all_items, get_subcollection_map
    from litmap.manuscript import parse_bibliography, match_items_to_zotero
    from litmap.embedder import load_all_fulltext_embeddings as load_all_embeddings
    from litmap.cluster import compute_hierarchy, cut_levels, label_clusters, build_outline
    from litmap.cluster_render import (
        render_dendrogram_html, render_dendrogram_static,
        render_outline_json, render_outline_markdown,
    )
    import numpy as np

    Path(output).parent.mkdir(parents=True, exist_ok=True)

    _auto_sync(db_path, zotero_db)

    if collection and manuscript and not union:
        typer.echo("Error: pass --union to cluster both --collection and --manuscript, or pick one.", err=True)
        raise typer.Exit(1)

    if collection and manuscript and union:
        coll_items = get_collection(collection, zotero_db)
        bib_entries = parse_bibliography(manuscript)
        bib_items, _ = match_items_to_zotero(bib_entries, zotero_db)
        seen = {i.key for i in coll_items}
        extra = [i for i in bib_items if i.key not in seen]
        items = coll_items + extra
    elif collection:
        items = get_collection(collection, zotero_db)
    elif manuscript:
        bib_entries = parse_bibliography(manuscript)
        items, _ = match_items_to_zotero(bib_entries, zotero_db)
    else:
        items = get_all_items(zotero_db)

    if not items or len(items) < 2:
        typer.echo("Error: need at least 2 papers to cluster.", err=True)
        raise typer.Exit(1)

    keys = [i.key for i in items]
    matrix, loaded_keys = load_all_embeddings(db_path, scope_keys=keys)
    dropped = len(keys) - len(loaded_keys)
    if dropped > 0:
        typer.echo(
            f"Note: {dropped} of {len(keys)} papers have no embedding yet and were skipped. "
            f"Run `litmap sync` to embed them.",
            err=True,
        )
    if len(loaded_keys) < 2:
        typer.echo("Error: fewer than 2 embedded papers found. Run `litmap sync` first.", err=True)
        raise typer.Exit(1)
    key_order = {k: i for i, k in enumerate(loaded_keys)}
    items = [i for i in items if i.key in key_order]
    items.sort(key=lambda it: key_order[it.key])
    keys = [i.key for i in items]

    n = len(keys)
    top_k = top_clusters if top_clusters is not None else max(2, round((n / 2) ** 0.5))
    top_k = min(top_k, n)

    linkage = compute_hierarchy(matrix)
    assignments = cut_levels(linkage, keys, matrix, top_k, subcluster_threshold)
    cluster_labels = label_clusters(items, assignments, level="cluster")
    subcluster_labels = label_clusters(items, assignments, level="subcluster")
    subcols = get_subcollection_map(zotero_db)

    outline = build_outline(
        items=items,
        assignments=assignments,
        cluster_labels=cluster_labels,
        subcluster_labels=subcluster_labels,
        existing_subcollections=subcols,
        input_meta={
            "collection": collection,
            "manuscript": str(manuscript) if manuscript else None,
            "union": union,
            "n_papers": n,
        },
        params={"top_clusters": top_k, "subcluster_threshold": subcluster_threshold},
    )

    want = {"html", "pdf", "png", "md", "json"} if fmt == "all" else {fmt}

    if "json" in want:
        json_path = Path(str(output) + ".json")
        json_path.write_text(render_outline_json(outline))
        np.save(str(output) + ".linkage.npy", linkage)
        typer.echo(f"Wrote {json_path}")
        typer.echo(f"Wrote {output}.linkage.npy")

    if "md" in want:
        md_path = Path(str(output) + ".md")
        md_path.write_text(render_outline_markdown(outline))
        typer.echo(f"Wrote {md_path}")

    if "html" in want:
        html_path = Path(str(output) + ".html")
        html_path.write_text(render_dendrogram_html(linkage, keys, items, assignments))
        typer.echo(f"Wrote {html_path}")

    static_formats = want & {"pdf", "png"}
    if static_formats:
        render_dendrogram_static(linkage, keys, items, assignments, output, formats=static_formats)
        for f in sorted(static_formats):
            typer.echo(f"Wrote {output}.{f}")
