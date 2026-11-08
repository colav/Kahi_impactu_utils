"""Bibliographic title cases: presentation variants and distinct publications."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest

from kahi_impactu_utils import Work as identity
from test_work_doi import collection


COCHRANE = "The Cochrane Collaboration's tool for assessing risk of bias in randomised trials"
EXTRACTS = "EXTRACTOS ALERGENICOS PARA INMUNOTERAPIA EN LATINOAMERICA. ALLERGEN EXTRACTS FOR IMMUNOTHERAPY IN LATIN AMERIC"
ROBOTS = 'DISEÑO DE UN ESCENARIO "EN LÍNEA" PARA ROBOTS TELEOPERADOS DESDE INTERNET'


def titles(value):
    return [{"title": value}]


@pytest.mark.parametrize("left,right,expected", [
    (COCHRANE, COCHRANE, True),
    (COCHRANE, COCHRANE.upper(), True),
    (COCHRANE, COCHRANE.replace("randomised", "randomized"), True),
    (COCHRANE, COCHRANE.replace("assessing", "assesing"), True),
    (COCHRANE, EXTRACTS, False),
    ("Assessment of β receptor signalling in clinical trials",
     "Assessment of b receptor signalling in clinical trials", False),
    ("Clinical assessment of outcomes in patients with p < 0.05",
     "Clinical assessment of outcomes in patients with p > 0.05", False),
    ("Clinical assessment of outcomes in patients with p < 0.05",
     "Clinical assessment of outcomes in patients with p <= 0.05", False),
    (ROBOTS, "DISENO DE UN ESCENARIO EN LINEA PARA ROBOTS TELEOPERADOS DESDE INTERNET", True),
    ("Risk <i>assessment</i> &amp; clinical trials", "Risk assessment & clinical trials", True),
    ("Marine biodiversity assessment in Pacific reefs", "Controlled publication title", False),
    ("Editorial", "Editorial", True),
    ("Editorial", "Editorials", False),
    ("Clinical assessment of health outcomes in 2011 randomized trials",
     "Clinical assessment of health outcomes in 2018 randomized trials", False),
    ("Clinical assessment of health outcomes in randomized trials",
     "Clinical assessment of health outcomes not in randomized trials", False),
    ("The long term effects of aspirin on cardiovascular mortality in older adults",
     "The long term effects of aspirin on cardiovascular morbidity in older adults", False),
    ("A study of clinical outcomes after freezing samples at -25 degrees Celsius",
     "A study of clinical outcomes after freezing samples at 25 degrees Celsius", False),
    ("A study of clinical outcomes after freezing samples at −25 degrees Celsius",
     "A study of clinical outcomes after freezing samples at -25 degrees Celsius", True),
    ("A study of clinical outcomes after freezing samples at +/-25 degrees Celsius",
     "A study of clinical outcomes after freezing samples at -25 degrees Celsius", False),
    (COCHRANE, "", False),
    ("", "", False),
])
def test_title_identity_cases(left, right, expected):
    assert identity.work_titles_match(titles(left), titles(right)) is expected
    assert identity.work_titles_match(titles(right), titles(left)) is expected


def test_matching_any_declared_translation_preserves_documents():
    incoming = titles("Ensayos clínicos controlados")
    stored = titles("Controlled clinical trials") + titles("Ensayos clínicos controlados")
    before = deepcopy(stored)
    assert identity.work_titles_match(incoming, stored)
    assert stored == before


@pytest.mark.parametrize("legacy_flag", [False, True])
def test_one_doi_candidate_always_requires_a_matching_title(legacy_flag):
    work = {"_id": "original", "titles": titles(COCHRANE)}
    assert identity._select_work([work], titles(EXTRACTS), legacy_flag) is None
    assert identity._select_work([work], titles(COCHRANE), legacy_flag) is work


def test_missing_title_never_confirms_identity():
    work = {"_id": "original", "titles": titles(COCHRANE)}
    with pytest.raises(identity.AmbiguousWorkDOI):
        identity._select_work([work], [], True)
    assert identity._select_work([{"_id": "missing", "titles": []}], titles(COCHRANE), True) is None


def test_distinct_titles_same_doi_are_idempotent_and_isolated(collection):
    doi = "https://doi.org/10.1136/bmj.d5928"
    original = {"doi": doi, "titles": titles(COCHRANE), "authors": [{"id": "original-author"}]}
    imported = {"doi": doi, "titles": titles(EXTRACTS), "authors": [{"id": "ciarp-author"}]}
    original_id, _ = identity.insert_work_by_doi(collection, original)
    other_id, _ = identity.insert_work_by_doi(collection, imported)
    inserted, owner = identity.insert_work_by_doi(collection, imported)
    assert inserted is None and owner["_id"] == other_id
    assert collection.count_documents({"doi": doi}) == 2
    assert collection.find_one({"_id": original_id})["authors"] == original["authors"]
    assert collection.find_one({"_id": other_id})["authors"] == imported["authors"]
    assert collection.count_documents({"_doi_key": {"$exists": True}}) == 0


def test_concurrent_doi_inserts_keep_distinct_titles_in_separate_works(collection):
    def write(index):
        entry = {"doi": "https://doi.org/10.1136/bmj.d5928",
                 "titles": titles(COCHRANE if index % 2 else EXTRACTS)}
        return identity.insert_work_by_doi(collection, entry)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(write, range(24)))
    assert sum(inserted is not None for inserted, _ in results) == 2
    assert collection.count_documents({}) == 2
