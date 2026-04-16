from litmap.zotero import get_all_items, get_collection, get_item, Item


def test_get_all_items_excludes_attachments(zotero_db):
    items = get_all_items(zotero_db)
    assert len(items) == 2
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
