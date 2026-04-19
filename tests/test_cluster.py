from pathlib import Path

import numpy as np
import pytest

from litmap.cluster import compute_hierarchy


def test_compute_hierarchy_shape():
    rng = np.random.default_rng(0)
    matrix = rng.random((10, 768)).astype(np.float32)
    linkage = compute_hierarchy(matrix)
    assert linkage.shape == (9, 4)
    assert (linkage[:, 2] >= 0).all()


from litmap.cluster import cut_levels


def _three_cluster_matrix():
    """9 vectors forming 3 tight, well-separated clusters of 3."""
    rng = np.random.default_rng(42)
    centres = np.array([
        [1.0] + [0.0] * 767,
        [0.0, 1.0] + [0.0] * 766,
        [0.0, 0.0, 1.0] + [0.0] * 765,
    ], dtype=np.float32)
    rows = []
    for c in centres:
        for _ in range(3):
            jitter = rng.normal(scale=0.01, size=768).astype(np.float32)
            rows.append(c + jitter)
    return np.stack(rows)  # shape (9, 768)


def test_cut_levels_three_synthetic_clusters():
    matrix = _three_cluster_matrix()
    keys = [f"k{i}" for i in range(9)]
    linkage = compute_hierarchy(matrix)
    assignments = cut_levels(
        linkage, keys, matrix, top_k=3, subcluster_threshold=99999
    )
    assert all(a["subcluster_id"] is None for a in assignments)
    cluster_ids = {a["cluster_id"] for a in assignments}
    assert cluster_ids == {1, 2, 3}
    from collections import Counter
    counts = Counter(a["cluster_id"] for a in assignments)
    assert all(c == 3 for c in counts.values())
    assert [a["key"] for a in assignments] == keys


def test_cut_levels_respects_subcluster_threshold():
    matrix = _three_cluster_matrix()
    keys = [f"k{i}" for i in range(9)]
    linkage = compute_hierarchy(matrix)
    assignments = cut_levels(
        linkage, keys, matrix, top_k=1, subcluster_threshold=100
    )
    assert all(a["cluster_id"] == 1 for a in assignments)
    assert all(a["subcluster_id"] is None for a in assignments)


def test_cut_levels_splits_large_cluster():
    matrix = _three_cluster_matrix()
    keys = [f"k{i}" for i in range(9)]
    linkage = compute_hierarchy(matrix)
    assignments = cut_levels(
        linkage, keys, matrix, top_k=1, subcluster_threshold=5
    )
    assert all(a["cluster_id"] == 1 for a in assignments)
    subcluster_ids = {a["subcluster_id"] for a in assignments}
    assert None not in subcluster_ids
    assert len(subcluster_ids) >= 2


from dataclasses import dataclass
from litmap.cluster import label_clusters


@dataclass
class _Item:
    """Minimal stand-in for litmap.zotero.Item — just the fields label_clusters reads."""
    key: str
    title: str
    abstract: str


def test_label_clusters_extracts_distinctive_terms():
    items = [
        _Item("k1", "Species distribution",      "MaxEnt ecology modelling biogeography"),
        _Item("k2", "Species distribution",      "ecology habitat modelling biogeography"),
        _Item("k3", "Species distribution",      "MaxEnt habitat ecology modelling"),
        _Item("k4", "Genome assembly",           "sequencing annotation bioinformatics"),
        _Item("k5", "Genome annotation",         "sequencing assembly bioinformatics"),
        _Item("k6", "Sequencing pipelines",      "genome assembly annotation bioinformatics"),
    ]
    assignments = [
        {"key": "k1", "cluster_id": 1, "subcluster_id": None},
        {"key": "k2", "cluster_id": 1, "subcluster_id": None},
        {"key": "k3", "cluster_id": 1, "subcluster_id": None},
        {"key": "k4", "cluster_id": 2, "subcluster_id": None},
        {"key": "k5", "cluster_id": 2, "subcluster_id": None},
        {"key": "k6", "cluster_id": 2, "subcluster_id": None},
    ]
    labels = label_clusters(items, assignments, level="cluster")

    assert set(labels) == {1, 2}
    label1 = labels[1].lower()
    label2 = labels[2].lower()
    assert any(term in label1 for term in ("species", "ecology", "modelling", "maxent", "biogeography", "habitat"))
    assert any(term in label2 for term in ("genome", "sequencing", "annotation", "assembly", "bioinformatics"))
    assert label1 != label2
    assert label1.count(" · ") == 2


def test_label_clusters_single_paper_fallback():
    items = [_Item("k1", "A fascinating analysis of citation networks in ecology", "")]
    assignments = [{"key": "k1", "cluster_id": 1, "subcluster_id": None}]
    labels = label_clusters(items, assignments, level="cluster")
    assert labels[1] == "A fascinating analysis of citation"


from litmap.cluster import build_outline


def _mk_item(key, title="T", abstract="A", authors=None, year="2020", doi=""):
    @dataclass
    class Full:
        key: str
        title: str
        abstract: str
        authors: list
        year: str
        doi: str
    return Full(key, title, abstract, authors or [], year, doi)


def test_build_outline_structure():
    items = [
        _mk_item("k1", title="Paper one"),
        _mk_item("k2", title="Paper two"),
        _mk_item("k3", title="Paper three"),
        _mk_item("k4", title="Paper four"),
        _mk_item("k5", title="Paper five"),
    ]
    assignments = [
        {"key": "k1", "cluster_id": 1, "subcluster_id": 1},
        {"key": "k2", "cluster_id": 1, "subcluster_id": 1},
        {"key": "k3", "cluster_id": 1, "subcluster_id": 2},
        {"key": "k4", "cluster_id": 2, "subcluster_id": None},
        {"key": "k5", "cluster_id": 2, "subcluster_id": None},
    ]
    outline = build_outline(
        items=items,
        assignments=assignments,
        cluster_labels={1: "alpha", 2: "beta"},
        subcluster_labels={(1, 1): "alpha-a", (1, 2): "alpha-b"},
        existing_subcollections={},
        input_meta={"collection": None, "manuscript": None, "union": False, "n_papers": 5},
        params={"top_clusters": 2, "subcluster_threshold": 3},
    )

    assert outline["input"]["n_papers"] == 5
    assert outline["params"]["top_clusters"] == 2
    assert len(outline["clusters"]) == 2

    c1 = outline["clusters"][0]
    assert c1["cluster_id"] == 1
    assert c1["label"] == "alpha"
    assert c1["size"] == 3
    assert c1["papers"] == []
    assert len(c1["subclusters"]) == 2
    assert c1["size"] == sum(sc["size"] for sc in c1["subclusters"]) + len(c1["papers"])

    c2 = outline["clusters"][1]
    assert c2["cluster_id"] == 2
    assert c2["label"] == "beta"
    assert c2["size"] == 2
    assert c2["subclusters"] == []
    assert len(c2["papers"]) == 2
    assert {p["zotero_key"] for p in c2["papers"]} == {"k4", "k5"}


def test_build_outline_existing_subcollections_attached():
    items = [_mk_item("k1"), _mk_item("k2")]
    assignments = [
        {"key": "k1", "cluster_id": 1, "subcluster_id": None},
        {"key": "k2", "cluster_id": 1, "subcluster_id": None},
    ]
    outline = build_outline(
        items=items,
        assignments=assignments,
        cluster_labels={1: "x"},
        subcluster_labels={},
        existing_subcollections={"k1": ["A", "B"], "k2": []},
        input_meta={"collection": None, "manuscript": None, "union": False, "n_papers": 2},
        params={"top_clusters": 1, "subcluster_threshold": 100},
    )
    papers = outline["clusters"][0]["papers"]
    by_key = {p["zotero_key"]: p for p in papers}
    assert by_key["k1"]["existing_subcollections"] == ["A", "B"]
    assert by_key["k2"]["existing_subcollections"] == []


import json as _json
from litmap.cluster_render import render_outline_json, render_outline_markdown


def _sample_outline() -> dict:
    return {
        "input": {"collection": "My Papers", "manuscript": None, "union": False, "n_papers": 3},
        "params": {"top_clusters": 2, "subcluster_threshold": 10},
        "clusters": [
            {
                "cluster_id": 1,
                "label": "ecology · species",
                "size": 2,
                "subclusters": [],
                "papers": [
                    {
                        "zotero_key": "k1",
                        "title": "Species distribution",
                        "authors": ["Valavi", "Elith"],
                        "year": "2022",
                        "doi": "10.1/geb",
                        "existing_subcollections": ["Chapter 2"],
                    },
                    {
                        "zotero_key": "k2",
                        "title": "Habitat suitability",
                        "authors": ["Guisan"],
                        "year": "2017",
                        "doi": "",
                        "existing_subcollections": [],
                    },
                ],
            },
            {
                "cluster_id": 2,
                "label": "genome · sequencing",
                "size": 1,
                "subclusters": [],
                "papers": [
                    {
                        "zotero_key": "k3",
                        "title": "Assembly methods",
                        "authors": ["Smith"],
                        "year": "2021",
                        "doi": "",
                        "existing_subcollections": [],
                    }
                ],
            },
        ],
    }


def test_render_outline_json_roundtrip():
    outline = _sample_outline()
    text = render_outline_json(outline)
    assert _json.loads(text) == outline


def test_render_outline_markdown_snapshot():
    text = render_outline_markdown(_sample_outline())
    expected = (
        "# litmap cluster — My Papers (3 papers)\n\n"
        "## 1. ecology · species  (2 papers)\n\n"
        "- Valavi et al. 2022 — *Species distribution*\n"
        "  [in: Chapter 2]\n"
        "- Guisan 2017 — *Habitat suitability*\n\n"
        "## 2. genome · sequencing  (1 paper)\n\n"
        "- Smith 2021 — *Assembly methods*\n"
    )
    assert text == expected


from litmap.cluster_render import (
    render_dendrogram_html,
    render_dendrogram_static,
)


def _items_for(keys):
    """Build minimal Items matching a list of keys."""
    return [_mk_item(k, title=f"Title {k}", authors=["Author"], year="2020") for k in keys]


def test_render_dendrogram_html_smoke():
    matrix = _three_cluster_matrix()
    keys = [f"k{i}" for i in range(9)]
    linkage = compute_hierarchy(matrix)
    assignments = cut_levels(linkage, keys, matrix, top_k=3, subcluster_threshold=99999)
    items = _items_for(keys)
    html = render_dendrogram_html(linkage, keys, items, assignments)
    assert "<div" in html
    assert "plotly" in html.lower()
    assert "k0" in html  # leaf hovertext must include at least one zotero_key


def test_render_dendrogram_static_writes_pdf_and_png(tmp_path):
    matrix = _three_cluster_matrix()
    keys = [f"k{i}" for i in range(9)]
    linkage = compute_hierarchy(matrix)
    assignments = cut_levels(linkage, keys, matrix, top_k=3, subcluster_threshold=99999)
    items = _items_for(keys)
    base = tmp_path / "dendro"
    render_dendrogram_static(linkage, keys, items, assignments, base, formats={"pdf", "png"})
    assert (tmp_path / "dendro.pdf").exists()
    assert (tmp_path / "dendro.png").exists()
    assert (tmp_path / "dendro.pdf").stat().st_size > 0
    assert (tmp_path / "dendro.png").stat().st_size > 0


def test_render_dendrogram_static_pdf_only(tmp_path):
    matrix = _three_cluster_matrix()
    keys = [f"k{i}" for i in range(9)]
    linkage = compute_hierarchy(matrix)
    assignments = cut_levels(linkage, keys, matrix, top_k=3, subcluster_threshold=99999)
    items = _items_for(keys)
    base = tmp_path / "dendro"
    render_dendrogram_static(linkage, keys, items, assignments, base, formats={"pdf"})
    assert (tmp_path / "dendro.pdf").exists()
    assert (tmp_path / "dendro.pdf").stat().st_size > 0
    assert not (tmp_path / "dendro.png").exists()


def test_render_dendrogram_static_png_only(tmp_path):
    matrix = _three_cluster_matrix()
    keys = [f"k{i}" for i in range(9)]
    linkage = compute_hierarchy(matrix)
    assignments = cut_levels(linkage, keys, matrix, top_k=3, subcluster_threshold=99999)
    items = _items_for(keys)
    base = tmp_path / "dendro"
    render_dendrogram_static(linkage, keys, items, assignments, base, formats={"png"})
    assert (tmp_path / "dendro.png").exists()
    assert (tmp_path / "dendro.png").stat().st_size > 0
    assert not (tmp_path / "dendro.pdf").exists()


def test_linkage_cache_round_trips(tmp_path):
    matrix = _three_cluster_matrix()
    linkage = compute_hierarchy(matrix)
    path = tmp_path / "saved.linkage.npy"
    np.save(path, linkage)
    loaded = np.load(path)
    assert loaded.shape == linkage.shape
    assert np.allclose(loaded, linkage)


from typer.testing import CliRunner
from litmap.cli import app


def test_cluster_cmd_smoke(tmp_path, zotero_db, embeddings_db):
    """End-to-end: fixture has 3 real papers; cluster them and write all outputs."""
    import sqlite3
    v1 = np.array([1.0] + [0.0] * 767, dtype=np.float32)
    v2 = np.array([0.0, 1.0] + [0.0] * 766, dtype=np.float32)
    v3 = np.array([0.0, 0.0, 1.0] + [0.0] * 765, dtype=np.float32)
    conn = sqlite3.connect(embeddings_db)
    for key, vec in [("AAAA0001", v1), ("AAAA0002", v2), ("AAAA0004", v3)]:
        conn.execute(
            "INSERT OR REPLACE INTO embeddings VALUES (?, ?, datetime('now'))",
            (key, vec.tobytes()),
        )
    conn.commit()
    conn.close()

    out_base = tmp_path / "smoke"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "cluster",
            "--top-clusters", "2",
            "--subcluster-threshold", "99999",
            "--output", str(out_base),
            "--db-path", str(embeddings_db),
            "--zotero-db", str(zotero_db),
        ],
    )
    assert result.exit_code == 0, result.output

    for ext in (".json", ".md", ".html", ".pdf", ".png", ".linkage.npy"):
        p = Path(str(out_base) + ext)
        assert p.exists(), f"missing {p}"
        assert p.stat().st_size > 0


def test_cluster_cmd_warns_on_unembedded_papers(
    tmp_path, zotero_db, embeddings_db, monkeypatch
):
    """If some papers in the requested set lack embeddings, warn but proceed."""
    import sqlite3
    import litmap.cli as cli_module

    # Skip auto-sync so unembedded papers stay unembedded (no real model call).
    monkeypatch.setattr(cli_module, "_auto_sync", lambda *a, **k: None)

    # Add a 4th journalArticle to zotero with no embedding. The full set then
    # has 4 papers but only 3 are embedded, so 1 should be skipped with a warning.
    conn = sqlite3.connect(zotero_db)
    conn.executescript("""
        INSERT INTO items VALUES (5, 2, 1, 'AAAA0005');
        INSERT INTO itemDataValues VALUES (401, 'Unembedded Paper');
        INSERT INTO itemDataValues VALUES (402, 'Abstract unembedded');
        INSERT INTO itemDataValues VALUES (403, '2024');
        INSERT INTO itemDataValues VALUES (404, '10.9999/zzz');
        INSERT INTO itemData VALUES (5, 1, 401);
        INSERT INTO itemData VALUES (5, 2, 402);
        INSERT INTO itemData VALUES (5, 6, 403);
        INSERT INTO itemData VALUES (5, 8, 404);
    """)
    conn.commit()
    conn.close()

    # Seed embeddings for 3 of the 4 journalArticle papers.
    v1 = np.array([1.0] + [0.0] * 767, dtype=np.float32)
    v2 = np.array([0.0, 1.0] + [0.0] * 766, dtype=np.float32)
    v3 = np.array([0.0, 0.0, 1.0] + [0.0] * 765, dtype=np.float32)
    conn = sqlite3.connect(embeddings_db)
    for key, vec in [("AAAA0001", v1), ("AAAA0002", v2), ("AAAA0004", v3)]:
        conn.execute(
            "INSERT OR REPLACE INTO embeddings VALUES (?, ?, datetime('now'))",
            (key, vec.tobytes()),
        )
    conn.commit()
    conn.close()

    out_base = tmp_path / "warn"
    try:
        runner = CliRunner(mix_stderr=False)
    except TypeError:
        # Newer click: stdout/stderr are always separate.
        runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "cluster",
            "--top-clusters", "2",
            "--subcluster-threshold", "99999",
            "--output", str(out_base),
            "--db-path", str(embeddings_db),
            "--zotero-db", str(zotero_db),
        ],
    )
    assert result.exit_code == 0, (result.stdout, result.stderr)
    combined = (result.stdout or "") + (result.stderr or "")
    assert "1 of 4 papers have no embedding" in combined
    assert "litmap sync" in combined


def test_cluster_cmd_creates_nested_output_dir(tmp_path, zotero_db, embeddings_db):
    """--output pointing into a non-existent directory should not crash."""
    import sqlite3
    v1 = np.array([1.0] + [0.0] * 767, dtype=np.float32)
    v2 = np.array([0.0, 1.0] + [0.0] * 766, dtype=np.float32)
    v3 = np.array([0.0, 0.0, 1.0] + [0.0] * 765, dtype=np.float32)
    conn = sqlite3.connect(embeddings_db)
    for key, vec in [("AAAA0001", v1), ("AAAA0002", v2), ("AAAA0004", v3)]:
        conn.execute(
            "INSERT OR REPLACE INTO embeddings VALUES (?, ?, datetime('now'))",
            (key, vec.tobytes()),
        )
    conn.commit()
    conn.close()

    out_base = tmp_path / "nested" / "dir" / "base"
    assert not out_base.parent.exists()

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "cluster",
            "--top-clusters", "2",
            "--subcluster-threshold", "99999",
            "--output", str(out_base),
            "--db-path", str(embeddings_db),
            "--zotero-db", str(zotero_db),
        ],
    )
    assert result.exit_code == 0, result.output

    for ext in (".json", ".md", ".html", ".pdf", ".png", ".linkage.npy"):
        p = Path(str(out_base) + ext)
        assert p.exists(), f"missing {p}"
        assert p.stat().st_size > 0


def test_cluster_cmd_collection_and_manuscript_without_union_errors(
    tmp_path, zotero_db, embeddings_db, monkeypatch
):
    """--collection + --manuscript without --union must exit 1 with helpful message."""
    import litmap.cli as cli_module
    monkeypatch.setattr(cli_module, "_auto_sync", lambda *a, **k: None)

    dummy_manuscript = tmp_path / "dummy.tex"
    dummy_manuscript.write_text("")

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "cluster",
            "--collection", "My Papers",
            "--manuscript", str(dummy_manuscript),
            "--output", str(tmp_path / "out"),
            "--db-path", str(embeddings_db),
            "--zotero-db", str(zotero_db),
        ],
    )
    assert result.exit_code == 1, result.output
    assert "pass --union" in result.output


def test_cluster_cmd_fewer_than_two_embedded_errors(
    tmp_path, zotero_db, embeddings_db, monkeypatch
):
    """If only 1 of the fixture's papers has an embedding, cluster must exit 1."""
    import sqlite3
    import litmap.cli as cli_module
    # Skip auto-sync so no real embedding happens; we control what is embedded.
    monkeypatch.setattr(cli_module, "_auto_sync", lambda *a, **k: None)

    v1 = np.array([1.0] + [0.0] * 767, dtype=np.float32)
    conn = sqlite3.connect(embeddings_db)
    conn.execute(
        "INSERT OR REPLACE INTO embeddings VALUES (?, ?, datetime('now'))",
        ("AAAA0001", v1.tobytes()),
    )
    conn.commit()
    conn.close()

    try:
        runner = CliRunner(mix_stderr=False)
    except TypeError:
        runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "cluster",
            "--output", str(tmp_path / "out"),
            "--db-path", str(embeddings_db),
            "--zotero-db", str(zotero_db),
        ],
    )
    assert result.exit_code == 1, (result.stdout, getattr(result, "stderr", ""))
    combined = (result.stdout or "") + (getattr(result, "stderr", "") or "")
    assert "fewer than 2 embedded papers" in combined


def test_cluster_cmd_format_pdf_only(tmp_path, zotero_db, embeddings_db):
    """--format pdf writes .pdf but NOT .png."""
    import sqlite3
    v1 = np.array([1.0] + [0.0] * 767, dtype=np.float32)
    v2 = np.array([0.0, 1.0] + [0.0] * 766, dtype=np.float32)
    v3 = np.array([0.0, 0.0, 1.0] + [0.0] * 765, dtype=np.float32)
    conn = sqlite3.connect(embeddings_db)
    for key, vec in [("AAAA0001", v1), ("AAAA0002", v2), ("AAAA0004", v3)]:
        conn.execute(
            "INSERT OR REPLACE INTO embeddings VALUES (?, ?, datetime('now'))",
            (key, vec.tobytes()),
        )
    conn.commit()
    conn.close()

    out_base = tmp_path / "pdfonly"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "cluster",
            "--top-clusters", "2",
            "--subcluster-threshold", "99999",
            "--output", str(out_base),
            "--format", "pdf",
            "--db-path", str(embeddings_db),
            "--zotero-db", str(zotero_db),
        ],
    )
    assert result.exit_code == 0, result.output
    assert Path(str(out_base) + ".pdf").exists()
    assert not Path(str(out_base) + ".png").exists()
    assert not Path(str(out_base) + ".html").exists()
    assert not Path(str(out_base) + ".json").exists()
    assert not Path(str(out_base) + ".md").exists()


def test_cluster_cmd_format_png_only(tmp_path, zotero_db, embeddings_db):
    """--format png writes .png but NOT .pdf."""
    import sqlite3
    v1 = np.array([1.0] + [0.0] * 767, dtype=np.float32)
    v2 = np.array([0.0, 1.0] + [0.0] * 766, dtype=np.float32)
    v3 = np.array([0.0, 0.0, 1.0] + [0.0] * 765, dtype=np.float32)
    conn = sqlite3.connect(embeddings_db)
    for key, vec in [("AAAA0001", v1), ("AAAA0002", v2), ("AAAA0004", v3)]:
        conn.execute(
            "INSERT OR REPLACE INTO embeddings VALUES (?, ?, datetime('now'))",
            (key, vec.tobytes()),
        )
    conn.commit()
    conn.close()

    out_base = tmp_path / "pngonly"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "cluster",
            "--top-clusters", "2",
            "--subcluster-threshold", "99999",
            "--output", str(out_base),
            "--format", "png",
            "--db-path", str(embeddings_db),
            "--zotero-db", str(zotero_db),
        ],
    )
    assert result.exit_code == 0, result.output
    assert Path(str(out_base) + ".png").exists()
    assert not Path(str(out_base) + ".pdf").exists()


def test_cluster_cmd_invalid_format_rejected(tmp_path, zotero_db, embeddings_db):
    """--format svg must exit non-zero (invalid format)."""
    out_base = tmp_path / "bad"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "cluster",
            "--top-clusters", "2",
            "--subcluster-threshold", "99999",
            "--output", str(out_base),
            "--format", "svg",
            "--db-path", str(embeddings_db),
            "--zotero-db", str(zotero_db),
        ],
    )
    assert result.exit_code != 0
