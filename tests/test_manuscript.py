import textwrap
from pathlib import Path
import pytest
from litmap.manuscript import parse_bib_text, extract_dois, match_items_to_zotero
from litmap.zotero import Item


SAMPLE_BIB = textwrap.dedent("""\
    @article{smith2021,
      author  = {Smith, Jane},
      title   = {Ecology of Networks},
      journal = {Nature},
      year    = {2021},
      doi     = {10.1234/eco},
    }
    @article{jones2022,
      author  = {Jones, Bob},
      title   = {Climate and Change},
      year    = {2022},
      doi     = {10.5678/cli},
    }
""")


def test_parse_bib_text_finds_two_entries():
    entries = parse_bib_text(SAMPLE_BIB)
    assert len(entries) == 2


def test_parse_bib_text_extracts_doi():
    entries = parse_bib_text(SAMPLE_BIB)
    dois = {e.get("doi") for e in entries}
    assert "10.1234/eco" in dois


def test_parse_bib_text_extracts_title():
    entries = parse_bib_text(SAMPLE_BIB)
    titles = {e.get("title") for e in entries}
    assert "Ecology of Networks" in titles


def test_extract_dois_from_text():
    text = "See Smith (2021) https://doi.org/10.9999/test for details."
    dois = extract_dois(text)
    assert "10.9999/test" in dois


def test_match_items_to_zotero_by_doi(zotero_db):
    entries = [{"doi": "10.1234/eco", "title": "Ecology of Networks"}]
    matched, unmatched = match_items_to_zotero(entries, zotero_db)
    assert len(matched) == 1
    assert matched[0].key == "AAAA0001"
    assert unmatched == []


def test_match_items_to_zotero_unmatched(zotero_db):
    entries = [{"doi": "10.9999/unknown", "title": "Unknown Paper"}]
    matched, unmatched = match_items_to_zotero(entries, zotero_db)
    assert matched == []
    assert len(unmatched) == 1
