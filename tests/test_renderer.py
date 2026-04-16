import numpy as np
import pytest
from pathlib import Path
from litmap.zotero import Item
from litmap.renderer import render_html, render_static


@pytest.fixture
def sample_data():
    items = [
        Item("k1", "Ecology of Networks", "Abstract 1", ["Smith, J."], "2021", "10.1/a"),
        Item("k2", "Climate and Change",  "Abstract 2", ["Jones, B."], "2022", "10.2/b"),
        Item("k3", "Biodiversity Loss",   "Abstract 3", ["Lee, C."],   "2020", "10.3/c"),
    ]
    layout = {
        "k1": (0.1, 0.2),
        "k2": (0.8, 0.7),
        "k3": (0.5, 0.5),
    }
    edges = [("k1", "k3", 0.85), ("k2", "k3", 0.72)]
    return items, layout, edges


def test_render_html_returns_html_string(sample_data):
    items, layout, edges = sample_data
    html = render_html(layout, edges, items)
    assert isinstance(html, str)
    assert "<html" in html.lower() or "plotly" in html.lower()


def test_render_html_manuscript_node_labelled(sample_data):
    items, layout, edges = sample_data
    html = render_html(layout, edges, items, manuscript_key="k1")
    assert "Ecology of Networks" in html


def test_render_static_creates_files(sample_data, tmp_path):
    items, layout, edges = sample_data
    out = tmp_path / "fig"
    render_static(layout, edges, items, path=out)
    assert (tmp_path / "fig.png").exists()
    assert (tmp_path / "fig.pdf").exists()


def test_render_static_manuscript_node_present(sample_data, tmp_path):
    items, layout, edges = sample_data
    out = tmp_path / "fig"
    # Should not raise
    render_static(layout, edges, items, manuscript_key="k1", path=out)
    assert (tmp_path / "fig.png").exists()
