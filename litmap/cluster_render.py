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
