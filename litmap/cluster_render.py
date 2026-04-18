"""Rendering for litmap cluster outputs: dendrograms and outlines."""
from __future__ import annotations

import json
from pathlib import Path


def render_outline_json(outline: dict) -> str:
    """Return the outline as pretty-printed JSON (2-space indent)."""
    return json.dumps(outline, indent=2, ensure_ascii=False)


def render_outline_markdown(outline: dict) -> str:
    """Return the outline as Markdown."""
    lines: list[str] = []
    header_src = outline["input"].get("collection") \
                or outline["input"].get("manuscript") \
                or "Zotero library"
    n = outline["input"]["n_papers"]
    lines.append(f"# litmap cluster — {header_src} ({n} papers)")
    lines.append("")

    for c in outline["clusters"]:
        size = c["size"]
        s = "paper" if size == 1 else "papers"
        lines.append(f"## {c['cluster_id']}. {c['label']}  ({size} {s})")
        lines.append("")
        if c["subclusters"]:
            for sc in c["subclusters"]:
                sc_size = sc["size"]
                ss = "paper" if sc_size == 1 else "papers"
                lines.append(
                    f"### {c['cluster_id']}.{sc['subcluster_id']} {sc['label']}  ({sc_size} {ss})"
                )
                _append_papers(lines, sc["papers"])
                lines.append("")
        else:
            _append_papers(lines, c["papers"])
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _append_papers(lines: list[str], papers: list[dict]) -> None:
    for p in papers:
        ref = _short_ref(p)
        lines.append(f"- {ref} — *{p['title']}*")
        if p.get("existing_subcollections"):
            lines.append(f"  [in: {', '.join(p['existing_subcollections'])}]")


def _short_ref(paper: dict) -> str:
    authors = paper.get("authors") or []
    year = paper.get("year") or "n.d."
    if not authors:
        return f"({year})"
    if len(authors) == 1:
        return f"{authors[0]} {year}"
    return f"{authors[0]} et al. {year}"


import numpy as np


def render_dendrogram_html(
    linkage: np.ndarray,
    keys: list[str],
    items: list,
    assignments: list[dict],
) -> str:
    """Plotly HTML string; leaves labelled by short refs, hover shows title + key,
    colour-coded by level-1 cluster id."""
    import plotly.figure_factory as ff

    items_by_key = {i.key: i for i in items}
    cluster_by_key = {a["key"]: a["cluster_id"] for a in assignments}

    def short_ref(k):
        it = items_by_key.get(k)
        if not it:
            return k
        authors = getattr(it, "authors", []) or []
        year = getattr(it, "year", "") or ""
        first = authors[0] if authors else "?"
        return f"{first} {year}".strip()

    labels = [short_ref(k) for k in keys]

    top_k = len(set(cluster_by_key.values()))
    colour_threshold = linkage[-top_k, 2] if top_k >= 2 else linkage[-1, 2]

    fig = ff.create_dendrogram(
        np.arange(len(keys)).reshape(-1, 1),
        labels=labels,
        linkagefun=lambda _: linkage,
        color_threshold=colour_threshold,
    )
    fig.update_layout(
        title=f"litmap cluster — {len(keys)} papers, {top_k} top clusters",
        margin=dict(l=40, r=40, t=60, b=120),
    )
    for trace in fig.data:
        trace.hoverinfo = "text"
    leaf_x = list(range(5, len(keys) * 10, 10))
    hover_texts = []
    for k in keys:
        it = items_by_key.get(k)
        hover_texts.append(f"{k}<br>{getattr(it, 'title', '')}")
    import plotly.graph_objects as go
    fig.add_trace(go.Scatter(
        x=leaf_x, y=[0] * len(keys),
        mode="markers",
        marker=dict(size=10, opacity=0.0),
        hovertext=hover_texts,
        hoverinfo="text",
        showlegend=False,
    ))

    return fig.to_html(include_plotlyjs="cdn", full_html=True)


def render_dendrogram_static(
    linkage: np.ndarray,
    keys: list[str],
    items: list,
    assignments: list[dict],
    path: Path,
) -> None:
    """Write <path>.pdf and <path>.png (300 DPI) using matplotlib."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from scipy.cluster.hierarchy import dendrogram as _dendrogram

    items_by_key = {i.key: i for i in items}

    def short_ref(k):
        it = items_by_key.get(k)
        if not it:
            return k
        authors = getattr(it, "authors", []) or []
        year = getattr(it, "year", "") or ""
        first = authors[0] if authors else "?"
        return f"{first} {year}".strip()

    labels = [short_ref(k) for k in keys]
    top_k = len({a["cluster_id"] for a in assignments})
    colour_threshold = linkage[-top_k, 2] if top_k >= 2 else linkage[-1, 2]

    fig, ax = plt.subplots(figsize=(max(8, len(keys) * 0.25), 6))
    _dendrogram(
        linkage,
        labels=labels,
        leaf_rotation=90,
        color_threshold=colour_threshold,
        ax=ax,
    )
    ax.set_title(f"litmap cluster — {len(keys)} papers, {top_k} top clusters")
    ax.set_ylabel("Cosine distance")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    fig.tight_layout()

    path = Path(path)
    fig.savefig(str(path) + ".pdf", dpi=300, bbox_inches="tight")
    fig.savefig(str(path) + ".png", dpi=300, bbox_inches="tight")
    plt.close(fig)
