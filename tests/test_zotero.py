from litmap.zotero import get_all_items, get_collection, get_item, Item


def test_get_all_items_excludes_attachments(zotero_db):
    items = get_all_items(zotero_db)
    assert len(items) == 3
    keys = {i.key for i in items}
    assert 'AAAA0003' not in keys  # attachment excluded


def test_get_all_items_fields(zotero_db):
    items = get_all_items(zotero_db)
    item = next(i for i in items if i.key == 'AAAA0001')
    assert item.title == 'Ecology of Networks'
    assert item.abstract == 'Abstract about ecology'
    assert item.year == '2021'
    assert item.doi == '10.1234/eco'
    assert 'Smith' in item.authors[0]


def test_get_collection(zotero_db):
    items = get_collection('My Papers', zotero_db)
    assert len(items) == 2


def test_get_collection_unknown_returns_empty(zotero_db):
    items = get_collection('Nonexistent', zotero_db)
    assert items == []


def test_get_item_by_key(zotero_db):
    item = get_item('AAAA0001', zotero_db)
    assert item is not None
    assert item.title == 'Ecology of Networks'


def test_get_item_by_doi(zotero_db):
    item = get_item('10.5678/cli', zotero_db)
    assert item is not None
    assert item.key == 'AAAA0002'


def test_get_item_unknown_returns_none(zotero_db):
    assert get_item('NOTEXIST', zotero_db) is None


def test_author_order_respects_orderindex(zotero_db_multiauthor):
    """authors[0] must be the Zotero first author (orderIndex=0), not insertion order.

    The fixture inserts creators with creatorID 10 (Zhao, orderIndex=2), 11 (Apple,
    orderIndex=1), 12 (Muller-Karger, orderIndex=0) in that order — so GROUP_CONCAT
    without ORDER BY would yield Zhao first. The fix adds ORDER BY ic.orderIndex, which
    must return Muller-Karger as authors[0].
    """
    items = get_all_items(zotero_db_multiauthor)
    assert len(items) == 1
    item = items[0]
    assert len(item.authors) == 3
    assert item.authors[0] == "Muller-Karger, Frank E."
    assert item.authors[1] == "Apple, Alice"
    assert item.authors[2] == "Zhao, Xavier"


def test_get_subcollection_map_returns_direct_collections_only(zotero_db):
    from litmap.zotero import get_subcollection_map

    mapping = get_subcollection_map(zotero_db)

    # Attachment (AAAA0003) must be excluded
    assert "AAAA0003" not in mapping

    # Item 1 is in both My Papers and Sub A
    assert set(mapping["AAAA0001"]) == {"My Papers", "Sub A"}
    # Item 2 is only in My Papers
    assert mapping["AAAA0002"] == ["My Papers"]
    # Item 4 is only in Sub A
    assert mapping["AAAA0004"] == ["Sub A"]
