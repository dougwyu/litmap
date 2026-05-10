from __future__ import annotations
from pathlib import Path
from typing import Optional

import numpy as np
import plotly.graph_objects as go
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from adjustText import adjust_text

from litmap.zotero import Item

# Colormap for nodes (continuous, mapped to x-coordinate)
_CMAP = "viridis"
_MANUSCRIPT_COLOR = "#e74c3c"
_MANUSCRIPT_MARKER = "star"
_NODE_SIZE = 8
_MANUSCRIPT_SIZE = 16
_EDGE_COLOR = "rgba(150,150,150,0.4)"


def _build_item_index(items: list[Item]) -> dict[str, Item]:
    return {i.key: i for i in items}


def _edge_traces(layout: dict, edges: list[tuple], alpha_base: float = 0.4):
    """Return a single Plotly scatter trace for all edges."""
    xs, ys = [], []
    for key_a, key_b, sim in edges:
        if key_a not in layout or key_b not in layout:
            continue
        x0, y0 = layout[key_a]
        x1, y1 = layout[key_b]
        xs += [x0, x1, None]
        ys += [y0, y1, None]
    return go.Scatter(
        x=xs, y=ys,
        mode="lines",
        line=dict(color=_EDGE_COLOR, width=1),
        hoverinfo="skip",
        showlegend=False,
    )


def render_html(
    layout: dict[str, tuple[float, float]],
    edges: list[tuple[str, str, float]],
    items: list[Item],
    manuscript_key: Optional[str] = None,
    cluster_annotations: Optional[dict] = None,
) -> str:
    idx = _build_item_index(items)
    xs_paper, ys_paper, texts_paper, hovers_paper, colors = [], [], [], [], []
    xs_ms, ys_ms, texts_ms, hovers_ms = [], [], [], []

    # Gather x-values for colormap normalisation
    all_x = [v[0] for v in layout.values()]
    x_min, x_max = min(all_x), max(all_x)
    x_range = x_max - x_min or 1.0

    for key, (x, y) in layout.items():
        item = idx.get(key)
        label = item.title[:40] + "…" if item and len(item.title) > 40 else (item.title if item else key)
        hover = (
            f"<b>{item.title}</b><br>"
            f"{', '.join(item.authors[:2])} {item.year}"
            if item else key
        )
        if key == manuscript_key:
            xs_ms.append(x); ys_ms.append(y)
            texts_ms.append(label); hovers_ms.append(hover)
        else:
            norm_x = (x - x_min) / x_range
            colors.append(norm_x)
            xs_paper.append(x); ys_paper.append(y)
            texts_paper.append(label); hovers_paper.append(hover)

    fig = go.Figure()
    fig.add_trace(_edge_traces(layout, edges))
    fig.add_trace(go.Scatter(
        x=xs_paper, y=ys_paper,
        mode="markers+text",
        marker=dict(size=_NODE_SIZE, color=colors, colorscale=_CMAP, showscale=False),
        text=texts_paper, textposition="top center",
        hovertext=hovers_paper, hoverinfo="text",
        textfont=dict(size=8),
        name="Papers",
    ))
    if xs_ms:
        fig.add_trace(go.Scatter(
            x=xs_ms, y=ys_ms,
            mode="markers+text",
            marker=dict(size=_MANUSCRIPT_SIZE, color=_MANUSCRIPT_COLOR, symbol="star"),
            text=texts_ms, textposition="top center",
            hovertext=hovers_ms, hoverinfo="text",
            textfont=dict(size=10, color=_MANUSCRIPT_COLOR),
            name="Manuscript",
        ))

    # Cluster label annotations
    if cluster_annotations:
        ann_xs, ann_ys, ann_texts = [], [], []
        for _cid, (cx, cy, label) in cluster_annotations.items():
            ann_xs.append(cx)
            ann_ys.append(cy)
            ann_texts.append(f"<b>{label}</b>")
        fig.add_trace(go.Scatter(
            x=ann_xs, y=ann_ys,
            mode="text",
            text=ann_texts,
            textfont=dict(size=13, color="#1a6b6b", family="Arial Black, sans-serif"),
            hoverinfo="skip",
            showlegend=False,
        ))

    fig.update_layout(
        showlegend=False,
        xaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        yaxis=dict(showticklabels=False, showgrid=False, zeroline=False),
        plot_bgcolor="white",
        margin=dict(l=20, r=20, t=20, b=20),
    )
    return fig.to_html(full_html=True, include_plotlyjs="cdn")


def render_static(
    layout: dict[str, tuple[float, float]],
    edges: list[tuple[str, str, float]],
    items: list[Item],
    manuscript_key: Optional[str] = None,
    path: Path = Path("litmap_output"),
    dpi: int = 300,
    cluster_annotations: Optional[dict] = None,
) -> None:
    idx = _build_item_index(items)
    all_x = [v[0] for v in layout.values()]
    x_min, x_max = min(all_x), max(all_x)
    x_range = x_max - x_min or 1.0

    fig, ax = plt.subplots(figsize=(10, 8))

    # Draw edges
    for key_a, key_b, sim in edges:
        if key_a not in layout or key_b not in layout:
            continue
        x0, y0 = layout[key_a]
        x1, y1 = layout[key_b]
        ax.plot([x0, x1], [y0, y1], color="grey", alpha=0.3 + 0.4 * sim, linewidth=0.8, zorder=1)

    # Draw nodes + collect label artists
    cmap = plt.get_cmap(_CMAP)
    label_artists = []
    for key, (x, y) in layout.items():
        item = idx.get(key)
        label = item.title[:30] + "…" if item and len(item.title) > 30 else (item.title if item else key)
        if key == manuscript_key:
            ax.scatter(x, y, s=150, color=_MANUSCRIPT_COLOR, marker="*", zorder=3)
            t = ax.text(x, y, label, fontsize=7, color=_MANUSCRIPT_COLOR, zorder=4)
        else:
            norm_x = (x - x_min) / x_range
            color = cmap(norm_x)
            ax.scatter(x, y, s=30, color=color, zorder=2)
            t = ax.text(x, y, label, fontsize=6, zorder=3)
        label_artists.append(t)

    adjust_text(label_artists, ax=ax, arrowprops=dict(arrowstyle="-", color="grey", lw=0.5))

    # Cluster label annotations
    if cluster_annotations:
        for _cid, (cx, cy, label) in cluster_annotations.items():
            ax.text(
                cx, cy, label,
                fontsize=9, fontweight="bold",
                color="#1a6b6b",
                ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#1a6b6b", alpha=0.85, linewidth=0.8),
                zorder=5,
            )

    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.tight_layout()

    png_path = Path(str(path) + ".png")
    pdf_path = Path(str(path) + ".pdf")
    fig.savefig(png_path, dpi=dpi, bbox_inches="tight")
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)
