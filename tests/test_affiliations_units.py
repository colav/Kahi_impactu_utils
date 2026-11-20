import pytest

from kahi_impactu_utils.Affiliations import (
    affiliation_covers_publication, affiliation_covers_year, get_units_affiliations)

UDEA, SPLIT = "03bp5hc83", "00m31ft63"
FAC, QUIM, FIS = "03bp5hc83_3", "03bp5hc83_3_quim", "03bp5hc83_3_fis"
TS_2016, TS_2017 = 1478736000, 1486684800


class FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def _match(self, doc, query):
        for key, value in query.items():
            if key == "_id":
                if doc.get("_id") != value:
                    return False
            elif key == "external_ids.id":
                if value not in [e["id"] for e in doc.get("external_ids", [])]:
                    return False
            elif key == "affiliations.id":
                if value not in [a["id"] for a in doc.get("affiliations", [])]:
                    return False
            elif key == "relations.id":
                if value not in [r["id"] for r in doc.get("relations", [])]:
                    return False
            else:
                raise KeyError(key)
        return True

    def find_one(self, query, projection=None):
        return next((d for d in self.docs if self._match(d, query)), None)

    def count_documents(self, query):
        return sum(1 for d in self.docs if self._match(d, query))


def person():
    return {"_id": "p1", "affiliations": [
        {"id": UDEA, "name": "UdeA", "types": [{"type": "education"}],
         "start_date": TS_2016, "end_date": -1, "years": list(range(2016, 2027))},
        {"id": FAC, "name": "Facultad", "types": [{"type": "faculty"}],
         "years": list(range(2016, 2027))},
        {"id": QUIM, "name": "Quimica", "types": [{"type": "department"}],
         "start_date": TS_2016, "end_date": TS_2017, "years": [2016, 2017]},
        {"id": FIS, "name": "Fisica", "types": [{"type": "department"}],
         "years": list(range(2018, 2027))},
        {"id": "COL1", "name": "Grupo", "types": [{"type": "group"}]},
        {"id": SPLIT, "name": "Split", "types": [{"type": "education"}],
         "start_date": -1, "end_date": -1, "years": [2016, 2017]},
    ]}


def db():
    return {
        "affiliations": FakeCollection([
            {"_id": UDEA, "types": [{"type": "education"}],
             "external_ids": [{"id": "https://openalex.org/I35961687"}], "relations": []},
            {"_id": SPLIT, "types": [{"type": "education"}], "external_ids": [], "relations": []},
            {"_id": FAC, "types": [{"type": "faculty"}], "relations": [{"id": UDEA}]},
            {"_id": QUIM, "types": [{"type": "department"}], "relations": [{"id": UDEA}, {"id": FAC}]},
            {"_id": FIS, "types": [{"type": "department"}], "relations": [{"id": UDEA}, {"id": FAC}]},
            {"_id": "COL1", "types": [{"type": "group"}], "relations": [{"id": UDEA}]},
        ]),
        "person": FakeCollection([person()]),
    }


def unit_ids(units):
    return [u["id"] for u in units]


SIGNED_UDEA = [{"external_ids": [{"id": "https://openalex.org/I35961687"}], "name": "UdeA"}]
SIGNED_UDEA_BY_ID = [{"id": UDEA, "name": "UdeA"}]
SIGNED_SPLIT = [{"id": SPLIT, "name": "Split"}]


def test_covers_year_uses_years_then_dates():
    assert affiliation_covers_year({"years": [2016, 2017]}, 2017)
    assert not affiliation_covers_year({"years": [2016, 2017]}, 2018)
    assert affiliation_covers_year({"start_date": TS_2016, "end_date": -1}, 2020, current_year=2026)
    assert not affiliation_covers_year({"start_date": -1, "end_date": -1}, 2020)
    assert not affiliation_covers_year({}, 2020)
    assert not affiliation_covers_year({"years": [2020]}, None)


def test_covers_publication_with_tolerance():
    aff = {"years": [2018, 2019]}
    assert affiliation_covers_publication(aff, 2020)
    assert not affiliation_covers_publication(aff, 2021)
    assert not affiliation_covers_publication(aff, 2020, tolerance=0)
    assert not affiliation_covers_publication(aff, None)


@pytest.mark.parametrize("year, expected", [
    (2012, []),
    (2016, [FAC, QUIM]),
    (2018, [FAC, QUIM, FIS]),   # 2017 tolerated for Quimica
    (2019, [FAC, FIS]),
    (2024, [FAC, FIS]),
])
def test_units_by_year_when_work_signed_by_udea(year, expected):
    assert unit_ids(get_units_affiliations(db(), person(), SIGNED_UDEA, year)) == expected


def test_units_resolved_by_id_too():
    assert unit_ids(get_units_affiliations(db(), person(), SIGNED_UDEA_BY_ID, 2024)) == [FAC, FIS]


def test_no_units_without_parent_institution_in_work():
    assert get_units_affiliations(db(), person(), SIGNED_SPLIT, 2024) == []
    assert get_units_affiliations(db(), person(), [], 2024) == []
    assert get_units_affiliations(db(), person(), [{"id": "COL1"}], 2024) == []


def test_no_units_without_publication_year():
    assert get_units_affiliations(db(), person(), SIGNED_UDEA, None) == []
    assert get_units_affiliations(db(), person(), SIGNED_UDEA, "n/a") == []


def test_unit_without_dates_is_skipped():
    p = person()
    p["affiliations"][1] = {"id": FAC, "name": "Facultad", "types": [{"type": "faculty"}]}
    assert unit_ids(get_units_affiliations(db(), p, SIGNED_UDEA, 2024)) == [FIS]


def test_unit_of_another_institution_is_skipped():
    d = db()
    d["affiliations"].docs[4]["relations"] = [{"id": SPLIT}]   # Fisica now hangs from Split
    assert unit_ids(get_units_affiliations(d, person(), SIGNED_UDEA, 2024)) == [FAC]
