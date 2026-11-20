from datetime import datetime

import pytest

from kahi_impactu_utils.Utils import normalize_publication_year


@pytest.mark.parametrize('value, expected', [
    (1799, None), (1800, 1800), (2026, 2026), (2027, 2027),
    (2028, 2028), (2029, None), (2030, None),
    (' 2028 ', 2028), ('1799', None), ('2029', None),
    (2024.0, 2024), (2024.5, None), (float('nan'), None),
    (float('inf'), None), (float('-inf'), None),
    (None, None), ('', None), ('unknown', None), ('2024-01-01', None),
    (0, None), (-1, None), (True, None), (False, None), ({}, None), ([], None),
])
def test_publication_year_limits_and_types(value, expected):
    assert normalize_publication_year(value, current_year=2026) == expected


def test_upper_limit_moves_with_current_year():
    assert normalize_publication_year(2029, current_year=2027) == 2029
    assert normalize_publication_year(2030, current_year=2027) is None
    year = datetime.now().year
    assert normalize_publication_year(year + 2) == year + 2
    assert normalize_publication_year(year + 3) is None
