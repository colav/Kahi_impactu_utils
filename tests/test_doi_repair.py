"""DOIs typed with repeated prefixes, embedded URLs or trailing garbage."""
import pytest

from kahi_impactu_utils.Utils import doi_processor, repair_doi
from kahi_impactu_utils.Work import canonical_work_doi


@pytest.mark.parametrize("raw,expected", [
    # repeated prefix (scholar, minciencias, scienti)
    ("10.15332/10.15332/s2339-3688.2017.0001.03", "10.15332/s2339-3688.2017.0001.03"),
    ("https://doi.org/10.17981/10.17981/ingecuc.16.2.2020.1", "10.17981/ingecuc.16.2.2020.1"),
    # DOI URL or doi: embedded after the prefix
    ("10.11144/https://doi.org/javeriana.vj139.gcmi", "10.11144/javeriana.vj139.gcmi"),
    ("http://dx.doi.org/10.14483/http://dx.doi.org/10.14483/udistrital.jour.colomb.for.2015.1.a02",
     "10.14483/udistrital.jour.colomb.for.2015.1.a02"),
    ("10.11144/doi:10.11144/Javerianacali.PPSI17-2.opee", "10.11144/javerianacali.ppsi17-2.opee"),
    # the same DOI repeated, with or without separator
    ("10.1016/j.rccar.2018.10.015https://doi.org/10.1016/j.rccar.2018.10.015", "10.1016/j.rccar.2018.10.015"),
    ("10.1016/j.neuroimage.2014.02.02210.1016/j.neuroimage.2014.02.022", "10.1016/j.neuroimage.2014.02.022"),
    (" http://dx.doi.org/10.11144/Javeriana.il15-27.gcea doi:10.11144/Javeriana.il15-27.gcea",
     "10.11144/javeriana.il15-27.gcea"),
    ('https://doi.org/10.1088/0004-637x/715/1/493\\">https://dx.doi.org/10.1088/0004-637x/715/1/493</a',
     "10.1088/0004-637x/715/1/493"),
    # trailing garbage that is not a DOI
    ("https://doi.org/10.1016/j.fuel.2022.123297.(https://www.sciencedirect.com/science/article/pii",
     "10.1016/j.fuel.2022.123297"),
    ("https://doi.org/10.1016/j.idnow.2023.104654.https://hdl.handle.net/20.500.12494/55530",
     "10.1016/j.idnow.2023.104654"),
    # untouched valid forms
    ("10.19137/semiarida.2019(02).2541", "10.19137/semiarida.2019(02).2541"),
    ("doi:10.1136/bmj.d5928", "10.1136/bmj.d5928"),
    ("https://dx.doi.org/10.1136/BMJ.D5928", "10.1136/bmj.d5928"),
])
def test_repaired_dois(raw, expected):
    assert doi_processor(raw) == f"https://doi.org/{expected}"
    assert canonical_work_doi(raw) == f"https://doi.org/{expected}"


@pytest.mark.parametrize("raw", [
    "10.1016/doi.org/",
    "10.4324/9781003344339-3, 10.4324/9781003344339-4, 10.4324/97",
    " 10.11144/Javeriana.SC18-2.cedm  : 10.11144/Javeriana.SC18-2.ce",
    "sin doi",
    "",
])
def test_unreliable_dois_are_discarded(raw):
    assert doi_processor(raw) is False
    assert canonical_work_doi(raw) is None


def test_repair_doi_requires_a_prefix():
    assert repair_doi("javeriana.vj139.gcmi") is None
    assert repair_doi(None) is None
