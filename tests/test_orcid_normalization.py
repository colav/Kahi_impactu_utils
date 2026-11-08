import pytest

from kahi_impactu_utils.Utils import get_id_from_url, parse_orcid_id_from_url


@pytest.mark.parametrize('value', [
    '0000-0003-4636-2392',
    'https://orcid.org/0000-0003-4636-2392,',
    'https://orcid.org/0000-0003-4636-2392?lang=es',
    'https://orcid.org/0000-0003-4636-2392  Print view',
])
def test_recovers_same_orcid(value):
    assert parse_orcid_id_from_url(value) == 'https://orcid.org/0000-0003-4636-2392'


def test_shared_dispatch_canonicalizes_check_character():
    assert get_id_from_url('https://orcid.org/0000-0002-7175-928x') == (
        'https://orcid.org/0000-0002-7175-928X')


def test_does_not_repair_invalid_checksum():
    value = 'https://orcid.org/0000-0000-3017-3127'
    assert parse_orcid_id_from_url(value) == value
