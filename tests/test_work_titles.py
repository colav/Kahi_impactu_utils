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


PALEOLITICO = "Paleolítico Medio del Guadalquivir: las industrias de pequeñas lascas del yacimiento de Tarazona III"
NUMANCIA = "EL USO DE PLANTAS EN NUMANCIA DURANTE LA II EDAD DEL HIERRO Y EPOCA ROMANA IMPERIAL"
CONDILAR_ES = "Evaluación del manejo quirúrgico en hiperplasia condilar: desde el diagnóstico hasta la monitorización del tratamiento"
CONDILAR_EN = "Evaluation of Surgical Management in Condylar Hyperplasia: From Diagnosis to Treatment Monitoring"
PAZ = "Construcción de paz e innovación pedagógica en Colombia"


@pytest.mark.parametrize("left,right,expected", [
    (COCHRANE, COCHRANE, True),
    (COCHRANE, COCHRANE.upper(), True),
    (COCHRANE, COCHRANE.replace("randomised", "randomized"), True),
    (COCHRANE, COCHRANE.replace("assessing", "assesing"), True),
    (COCHRANE, EXTRACTS, False),
    (ROBOTS, "DISENO DE UN ESCENARIO EN LINEA PARA ROBOTS TELEOPERADOS DESDE INTERNET", True),
    ("Risk <i>assessment</i> &amp; clinical trials", "Risk assessment & clinical trials", True),
    ("Marine biodiversity assessment in Pacific reefs", "Controlled publication title", False),
    ("Editorial", "Editorial", True),
    ("Editorial", "Editorials", True),
    ("The long term effects of aspirin on cardiovascular mortality in older adults",
     "The long term effects of aspirin on cardiovascular morbidity in older adults", True),
    ("A study of clinical outcomes after freezing samples at −25 degrees Celsius",
     "A study of clinical outcomes after freezing samples at -25 degrees Celsius", True),
    # Subtitles, appended author names or a translation in parentheses contain the title.
    (PAZ, PAZ + " (Peacebuilding and Pedagogical Innovation in Colombia)", True),
    ("Early Prediction of MMSE & CSI‐D Scores with AI",
     "Early Prediction of MMSE & CSI-D Scores with AI Daniel Crovo, Paola Ruiz Puentes", True),
    ("El turismo comunitario urbano como forma de reexistencia cultural y laboral",
     "El turismo comunitario urbano como forma de re-existencia cultural y laboral. El modelo de Barrio Egipto", True),
    # Containment needs a real title, not a word.
    ("London", "Challenging The City Scale. London", False),
    # Dotless i and combining marks fold to the same letters.
    ("Türkiye'de sağlık hizmetlerinin değerlendirilmesi: bir alan araştırması",
     "TÜRKİYE'DE SAĞLIK HİZMETLERİNİN DEĞERLENDİRİLMESİ: BİR ALAN ARAŞTIRMASI", True),
    # Unrelated titles in the same language stay apart even with a shared DOI.
    (PALEOLITICO, NUMANCIA, False),
    (COCHRANE, "", False),
    ("", "", False),
])
def test_title_identity_cases(left, right, expected):
    assert identity.work_titles_match(titles(left), titles(right)) is expected
    assert identity.work_titles_match(titles(right), titles(left)) is expected


@pytest.mark.parametrize("left_year,right_year,expected", [
    (2023, 2023, True), (2023, 2024, True), (None, 2023, False), (2019, 2023, False),
])
def test_translations_require_compatible_years(left_year, right_year, expected):
    assert identity.work_titles_match(titles(CONDILAR_ES), titles(CONDILAR_EN),
                                      left_year, right_year) is expected


def test_declared_languages_decide_translation_without_detection():
    incoming = [{"title": CONDILAR_ES, "lang": "es"}]
    stored = [{"title": CONDILAR_EN, "lang": "en"}]
    assert identity.work_titles_match(incoming, stored, 2023, 2023)
    assert not identity.work_titles_match(incoming, [{"title": CONDILAR_EN, "lang": "es"}], 2023, 2023)


def test_select_work_prefers_the_closest_title_and_uses_years():
    exact = {"_id": "exact", "titles": titles(CONDILAR_ES), "year_published": 2023}
    translated = {"_id": "translated", "titles": titles(CONDILAR_EN), "year_published": 2023}
    assert identity._select_work([translated, exact], titles(CONDILAR_ES), True, 2023) is exact
    assert identity._select_work([translated], titles(CONDILAR_ES), True, 2023) is translated
    assert identity._select_work([translated], titles(CONDILAR_ES), True, 2015) is None


def test_strict_mode_accepts_only_close_wording():
    assert identity.work_titles_match(titles(COCHRANE), titles(COCHRANE.replace("assessing", "assesing")), strict=True)
    assert not identity.work_titles_match(titles(PAZ), titles(PAZ + " (Peacebuilding and Pedagogical Innovation in Colombia)"), strict=True)
    assert not identity.work_titles_match(titles(CONDILAR_ES), titles(CONDILAR_EN), 2023, 2023, strict=True)


def test_short_or_uncertain_titles_do_not_count_as_translations():
    assert not identity.work_titles_match(titles("Libro con identificador y título específico"),
                                          titles("Capítulo totalmente distinto"), 2024, 2024)


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
