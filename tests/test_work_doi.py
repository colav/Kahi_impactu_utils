import os
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier, local
from threading import Event
from time import sleep
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

import kahi_impactu_utils.Work as identity


@pytest.fixture
def collection():
    url = os.environ.get("KAHI_TEST_MONGODB_URL")
    if not url:
        pytest.skip("Set KAHI_TEST_MONGODB_URL for isolated MongoDB tests")
    client = MongoClient(url, serverSelectionTimeoutMS=5000)
    name = "kahi_doi_test_" + uuid4().hex
    try:
        works = client[name].works
        identity.ensure_work_doi_indexes(works)
        yield works
    finally:
        client.drop_database(name)
        client.close()


@pytest.mark.parametrize("value", [None, "", "https://doi.org/", "10.123/bad", "invalid"])
def test_invalid_doi_does_not_become_identity(value):
    entry = {"doi": value, "external_ids": []}
    assert identity.prepare_work_doi(entry, "openalex") is None
    assert "_doi_key" not in entry
    assert entry["doi"] == value


def test_missing_ids_doi_is_repaired():
    entry = {"doi": "https://doi.org/10.1182/BLOOD.V130.SUPPL_1.4862.4862",
             "external_ids": [{"source": "openalex", "id": "W2914737132"}]}
    doi = identity.prepare_work_doi(entry, "openalex")
    identity.prepare_work_doi(entry, "openalex")
    assert doi == "https://doi.org/10.1182/blood.v130.suppl_1.4862.4862"
    assert len(entry["external_ids"]) == 2
    assert entry["external_ids"][-1] == {
        "provenance": "openalex", "source": "doi", "id": doi}


@pytest.mark.parametrize("document", [
    {"doi": "https://doi.org/10.4000/LHOMME.22296", "external_ids": []},
    {"doi": "", "external_ids": [{"source": "doi", "id": "10.4000/LHOMME.22296"}]},
    {"doi": "http://dx.doi.org/10.4000/LHOMME.22296", "external_ids": []},
])
def test_legacy_lookup_and_adoption_preserve_metadata(collection, document):
    document["titles"] = [{"title": "Shared publication title"}]
    old_id = collection.insert_one(document).inserted_id
    entry = {"doi": "10.4000/lhomme.22296", "external_ids": [],
             "titles": [{"title": "Shared publication title"}]}
    identity.prepare_work_doi(entry, "scienti")
    inserted, owner = identity.insert_work_by_doi(collection, entry)
    assert inserted is None and owner["_id"] == old_id
    assert collection.count_documents({}) == 1
    assert "_doi_key" not in collection.find_one()
    for key, value in document.items():
        assert collection.find_one()[key] == (entry["doi"] if key == "doi" and not value else value)


def test_ambiguous_historical_doi_stops_without_merge(collection):
    collection.insert_many([
        {"doi": "https://doi.org/10.4000/lhomme.22296"},
        {"external_ids": [{"id": "10.4000/LHOMME.22296"}]},
    ])
    before = list(collection.find())
    entry = {"doi": "10.4000/lhomme.22296"}
    identity.prepare_work_doi(entry, "openalex")
    with pytest.raises(identity.AmbiguousWorkDOI):
        identity.insert_work_by_doi(collection, entry)
    assert list(collection.find()) == before


def test_stale_claim_cannot_replace_a_different_doi(collection):
    work_id = collection.insert_one({"doi": "", "external_ids": []}).inserted_id
    stale = collection.find_one({"_id": work_id})
    identity.claim_work_doi(collection, deepcopy(stale), "10.4000/first")
    before = collection.find_one({"_id": work_id})
    with pytest.raises(identity.AmbiguousWorkDOI):
        identity.claim_work_doi(collection, stale, "10.4000/second")
    assert collection.find_one({"_id": work_id}) == before


def test_concurrent_different_doi_claims_have_only_one_winner(collection):
    work_id = collection.insert_one({"doi": "", "external_ids": []}).inserted_id
    stale = collection.find_one({"_id": work_id})
    barrier = Barrier(2)

    def claim(value):
        barrier.wait(timeout=10)
        try:
            identity.claim_work_doi(collection, deepcopy(stale), value)
            return "claimed", identity.canonical_work_doi(value)
        except identity.AmbiguousWorkDOI:
            return "conflict", None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ["10.4000/first", "10.4000/second"]))
    assert sorted(status for status, _ in results) == ["claimed", "conflict"]
    winner = next(doi for status, doi in results if status == "claimed")
    assert collection.find_one({"_id": work_id})["doi"] == winner


def test_parallel_inserts_keep_one_work_and_all_source_ids(collection, monkeypatch):
    # Force every worker past an empty lookup before any upsert, as in the ETL race.
    workers = 16
    barrier = Barrier(workers)

    def write(index):
        source = "openalex" if index % 2 == 0 else "scienti"
        entry = {"doi": "10.4000/LHOMME.22296", "titles": [{"title": "The shared publication"}],
                 "external_ids": [{"source": source, "id": str(index)}]}
        identity.prepare_work_doi(entry, source)
        barrier.wait(timeout=10)
        inserted, owner = identity.insert_work_by_doi(collection, entry)
        if owner is not None:
            identity.merge_work_identifiers(collection, owner, entry)
        return inserted

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(write, range(workers)))
    assert sum(value is not None for value in results) == 1
    assert collection.count_documents({}) == 1
    work = collection.find_one()
    assert len(work["titles"]) == 1
    assert {ext["id"] for ext in work["external_ids"] if ext["source"] != "doi"} == {
        str(index) for index in range(workers)}


def test_unrelated_unique_index_failure_is_not_swallowed():
    collection = MagicMock()
    collection.find.return_value.limit.return_value = []
    collection.insert_one.side_effect = DuplicateKeyError(
        "different index", details={"keyPattern": {"other": 1}})
    entry = {"doi": "10.4000/lhomme.22296"}
    identity.prepare_work_doi(entry, "openalex")
    with pytest.raises(DuplicateKeyError):
        identity.insert_work_by_doi(collection, entry)
    collection.find_one.assert_not_called()


def test_expired_lease_recovers_same_reserved_object_id(collection, monkeypatch):
    coordinate = identity._coordinate_doi
    monkeypatch.setattr(identity, "_coordinate_doi", lambda col, doi: coordinate(col, doi, lease_seconds=0.03))
    started, release = Event(), Event()
    insert = collection.insert_one

    def delayed(document, *args, **kwargs):
        if document["external_ids"][0]["id"] == "first":
            started.set()
            assert release.wait(timeout=5)
        return insert(document, *args, **kwargs)

    monkeypatch.setattr(collection, "insert_one", delayed)

    def write(identifier):
        entry = {"doi": "10.4000/lhomme.22296", "titles": [{"title": "Shared title"}],
                 "external_ids": [{"source": "openalex", "id": identifier}]}
        identity.prepare_work_doi(entry, "openalex")
        inserted, winner = identity.insert_work_by_doi(collection, entry)
        if winner is not None:
            identity.merge_work_identifiers(collection, winner, entry)
        return inserted

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(write, "first")
        assert started.wait(timeout=5)
        sleep(0.06)
        second = pool.submit(write, "second")
        try:
            second_id = second.result(timeout=5)
        finally:
            release.set()
        assert first.result(timeout=5) is None
    assert collection.count_documents({}) == 1
    work = collection.find_one()
    assert work["_id"] == second_id and "_doi_key" not in work
    assert {item["id"] for item in work["external_ids"] if item["source"] != "doi"} == {"first", "second"}


def test_openalex_source_and_doi_conflict_stops_without_modification(collection, monkeypatch):
    import kahi_openalex_works.process_one as oa

    collection.insert_many([
        {"doi": "10.4000/first", "titles": [{"title": "Work"}], "external_ids": [{"source": "openalex", "id": "W1"}]},
        {"doi": "10.4000/second", "titles": [{"title": "Work"}], "external_ids": [{"source": "openalex", "id": "W2"}]},
    ])
    before = list(collection.find())
    update = MagicMock()
    monkeypatch.setattr(oa, "process_one_update", update)
    oa.process_one({"doi": "10.4000/second", "id": "W1", "title": "Work"},
                       {"database_name": collection.database.name}, {},
                       collection.database.client, None, "threading")
    update.assert_not_called()
    assert list(collection.find()) == before


@pytest.mark.parametrize("plugin", ["openalex", "scienti"])
def test_actual_dispatch_updates_legacy_primary_doi(collection, monkeypatch, plugin):
    import kahi_openalex_works.process_one as oa
    import kahi_scienti_works.process_one as sci

    work_id = collection.insert_one({
        "doi": "https://doi.org/10.4000/LHOMME.22296", "external_ids": [],
        "titles": [{"title": "Work"}]}).inserted_id
    module = oa if plugin == "openalex" else sci
    update, insert = MagicMock(), MagicMock()
    monkeypatch.setattr(module, "process_one_update", update)
    monkeypatch.setattr(module, "process_one_insert", insert)
    if plugin == "openalex":
        oa.process_one({"doi": "10.4000/lhomme.22296", "id": "W1657564902", "title": "Work"},
                       {"database_name": collection.database.name}, {},
                       collection.database.client, None, "threading")
    else:
        sci.process_one({"TXT_NME_PROD": "Work", "TXT_DOI": "10.4000/lhomme.22296"},
                        collection.database, collection, {}, None, similarity=False)
    insert.assert_not_called()
    update.assert_called_once()
    assert update.call_args.args[1]["_id"] == work_id
    assert collection.count_documents({}) == 1


@pytest.mark.parametrize("plugin", ["openalex", "scienti"])
def test_same_source_update_unions_identifiers_with_stale_work(collection, monkeypatch, plugin):
    import kahi_openalex_works.process_one as oa
    import kahi_scienti_works.process_one as sci

    module = oa if plugin == "openalex" else sci
    entry = {"doi": "10.4000/lhomme.22296", "titles": [{"title": "New title"}],
             "external_ids": [{"source": plugin, "id": "new"}]}
    parser = "parse_openalex" if plugin == "openalex" else "parse_scienti"
    monkeypatch.setattr(module, parser, lambda *_args, **_kwargs: deepcopy(entry))
    work_id = collection.insert_one({
        "doi": "10.4000/lhomme.22296", "year_published": 2024,
        "source": {}, "updated": [{"source": plugin}],
        "titles": [], "external_ids": [{"source": plugin, "id": "original"}],
    }).inserted_id
    stale = collection.find_one()
    collection.update_one({"_id": work_id}, {"$addToSet": {
        "external_ids": {"source": plugin, "id": "concurrent"}}})
    module.process_one_update({}, stale, collection.database, collection, {})
    stored = collection.find_one()
    assert {ext["id"] for ext in stored["external_ids"] if ext["source"] == plugin} == {
        "original", "concurrent", "new"}
    assert stored["titles"] == entry["titles"]


@pytest.mark.parametrize("first", ["openalex", "scienti"])
def test_real_import_paths_share_doi_and_keep_multiple_source_records(collection, monkeypatch, first):
    from kahi.KahiBase import KahiBase
    import kahi_openalex_works.parser as oa_parser
    import kahi_openalex_works.process_one as oa
    import kahi_scienti_works.process_one as sci

    monkeypatch.setattr(oa_parser, "lang_poll", lambda *_a, **_k: "en")
    monkeypatch.setattr(sci, "lang_poll", lambda *_a, **_k: "en")

    def scienti_parser(reg, _template, *args, **kwargs):
        entry = KahiBase.empty_work(None)
        entry.update({
            "doi": reg["TXT_DOI"], "updated": [{"source": "scienti", "time": 1}],
            "titles": [{"title": reg["TXT_NME_PROD"], "source": "scienti", "lang": "en"}],
            "external_ids": [{"source": "scienti", "id": {
                "COD_RH": reg["COD_RH"], "COD_PRODUCTO": reg["COD_PRODUCTO"]}}],
            "authors": [{"full_name": "Ana", "affiliations": [],
                         "external_ids": [{"source": "scienti", "id": {"COD_RH": "RH1"}}]}],
        })
        return entry

    monkeypatch.setattr(sci, "parse_scienti", scienti_parser)

    def import_oa(number):
        # Reproduce actual OpenAlex records whose ids dictionary omits DOI.
        raw = {"id": f"https://openalex.org/W{number}", "doi": "10.4000/LHOMME.22296",
               "ids": {"openalex": f"https://openalex.org/W{number}"},
               "title": "A work", "type": "article", "publication_year": 2024,
               "counts_by_year": [], "cited_by_count": 0, "primary_location": None,
               "biblio": {}, "authorships": [], "concepts": []}
        oa.process_one(raw, {"database_name": collection.database.name},
                       KahiBase.empty_work(None), collection.database.client, None, "threading")

    def import_sci(number):
        raw = {"COD_RH": "RH1", "COD_PRODUCTO": f"P{number}",
               "TXT_NME_PROD": "A work", "TXT_DOI": "https://doi.org/10.4000/lhomme.22296"}
        sci.process_one(raw, collection.database, collection, KahiBase.empty_work(None),
                        None, similarity=False)

    if first == "openalex":
        import_oa(1)
        import_sci(1)
    else:
        import_sci(1)
        import_oa(1)
    import_oa(2)
    import_sci(2)
    import_oa(1)
    import_sci(1)
    assert collection.count_documents({}) == 1
    work = collection.find_one()
    assert work["doi"] == "https://doi.org/10.4000/lhomme.22296"
    assert "_doi_key" not in work
    assert {ext["id"] for ext in work["external_ids"] if ext["source"] == "openalex"} == {
        "https://openalex.org/W1", "https://openalex.org/W2"}
    assert {ext["id"]["COD_PRODUCTO"] for ext in work["external_ids"] if ext["source"] == "scienti"} == {
        "P1", "P2"}
    assert {update["source"] for update in work["updated"]} == {"openalex", "scienti"}
