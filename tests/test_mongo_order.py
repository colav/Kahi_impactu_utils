import os
from copy import deepcopy
from uuid import uuid4

import pytest
from pymongo import MongoClient

from kahi_impactu_utils.Mongo import insert_only_update, order_document


def test_order_preserves_values_missing_fields_and_extra_fields():
    document = {"extra": {"z": 2, "a": 1}, "b": [1], "_id": "id", "a": None}
    before = deepcopy(document)
    result = order_document(document, {"a": None, "absent": [], "b": []})
    assert list(result) == ["_id", "a", "b", "extra"]
    assert result == before == document
    assert list(result["extra"]) == ["z", "a"]
    assert "absent" not in result


@pytest.mark.parametrize("campuses", [None, [], [{"id": "campus-1", "names": ["Campus Uno"]}]])
def test_affiliation_order_keeps_campuses_after_extra_fields(campuses):
    document = {"birthdate": 123, "_id": "group", "names": []}
    if campuses is not None:
        document = {"campuses": deepcopy(campuses), **document}
    before = deepcopy(document)
    result = order_document(document, {"names": [], "campuses": []})

    assert list(result) == ["_id", "names", "birthdate", "campuses"]
    assert result["campuses"] == ([] if campuses is None else campuses)
    assert {k: v for k, v in result.items() if k != "campuses"} == {
        k: v for k, v in before.items() if k != "campuses"
    }
    assert document == before


@pytest.fixture
def collection():
    url = os.environ.get("KAHI_TEST_MONGODB_URL")
    if not url:
        pytest.skip("Set KAHI_TEST_MONGODB_URL for isolated MongoDB tests")
    client = MongoClient(url)
    name = "kahi_order_test_" + uuid4().hex
    try:
        yield client[name].entities
    finally:
        client.drop_database(name)
        client.close()


def test_ordered_upsert_inserts_and_retry_preserves_existing(collection):
    document = {
        "titles": [{"title": "$literal text"}], "updated": [], "doi": "",
        "external_ids": [{"source": "test", "id": "reference"}],
        "nested": {"z": 2, "a": 1},
    }
    query = {"external_ids": {"$elemMatch": {"source": "test", "id": "reference"}}}
    first = collection.update_one(query, insert_only_update(document), upsert=True)
    assert first.upserted_id is not None
    stored = collection.find_one(query)
    assert list(stored) == ["_id", *document]
    assert {k: v for k, v in stored.items() if k != "_id"} == document
    replacement = {**document, "doi": "must not overwrite"}
    retry = collection.update_one(query, insert_only_update(replacement), upsert=True)
    assert retry.upserted_id is None
    assert retry.modified_count == 0
    assert collection.find_one(query) == stored
    assert list(collection.find_one(query)) == list(stored)
    assert collection.count_documents({}) == 1


def test_explicit_document_id_is_preserved(collection):
    document = {"titles": [], "updated": [], "_id": "persistent", "reference": "x"}
    result = collection.update_one(
        {"reference": "x"}, insert_only_update(document), upsert=True,
    )
    assert result.upserted_id == "persistent"
    assert list(collection.find_one()) == ["_id", "titles", "updated", "reference"]
