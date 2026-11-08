import pytest

from kahi_impactu_utils.String import has_dash, normalize_dashes
from kahi_impactu_utils.Utils import normalize_name, split_name_part, split_names


@pytest.mark.parametrize("raw, expected", [
    ("A Alonso‐Herrero", "A Alonso Herrero"),      # U+2010 hyphen
    ("A Al–Lehibi", "A Al Lehibi"),                # U+2013 en dash
    ("Jean‑Pierre", "Jean Pierre"),                # U+2011 non-breaking hyphen
    ("Adalira Saenz-ludlow", "Adalira Saenz ludlow"),   # ASCII hyphen
    ("Alexander Patrick Cooman -", "Alexander Patrick Cooman"),  # dash-only token
    ("García  Márquez", "García Márquez"),  # no dash: intact
    ("", ""),
    (None, None),
])
def test_normalize_dashes_to_space(raw, expected):
    assert normalize_dashes(raw) == expected


def test_normalize_dashes_canonical_hyphen():
    assert normalize_dashes("A Alonso‐Herrero", replacement="-") == "A Alonso-Herrero"
    assert normalize_dashes("Cooman -", replacement="-") == "Cooman"
    assert normalize_dashes("Al – Lehibi", replacement="-") == "Al Lehibi"


def test_has_dash():
    assert has_dash("Alonso‐Herrero")
    assert has_dash("Saenz-ludlow")
    assert not has_dash("Alonso Herrero")
    assert not has_dash("")


@pytest.mark.parametrize("raw, first, last", [
    ("A Alonso‐Herrero", ["A"], ["Alonso", "Herrero"]),
    ("A Al–Lehibi", ["A"], ["Al", "Lehibi"]),
    ("Jean‑Pierre Dupont", ["Jean", "Pierre"], ["Dupont"]),
    ("Adalira Saenz-ludlow", ["Adalira"], ["Saenz", "Ludlow"]),
    ("Alexander Patrick Cooman -", ["Alexander", "Patrick"], ["Cooman"]),
])
def test_split_names_handles_every_dash(raw, first, last):
    parsed = split_names(raw)
    assert parsed["first_names"] == first
    assert parsed["last_names"] == last
    assert not has_dash(parsed["full_name"])
    assert not any(has_dash(x) for x in parsed["first_names"] + parsed["last_names"])


def test_split_names_without_dash_is_unchanged():
    parsed = split_names("Gabriel García Márquez")
    assert parsed["first_names"] == ["Gabriel"]
    assert parsed["last_names"] == ["García", "Márquez"]


def test_split_name_part_splits_dashes():
    assert split_name_part("Jean‑Pierre") == ["Jean", "Pierre"]
    assert split_name_part("María De La Cruz-López") == ["María", "De La Cruz", "López"]


def test_normalize_name_compares_dashed_and_spaced_names_equal():
    assert normalize_name("Alonso‐Herrero") == normalize_name("Alonso Herrero")
    assert normalize_name("Saenz-Ludlow") == "saenz ludlow"
