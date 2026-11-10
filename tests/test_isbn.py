import pytest

from kahi_impactu_utils.Utils import isbn_processor


@pytest.mark.parametrize('value, expected', [
    # ISBN-10 is converted to ISBN-13, including an X check digit
    ('0-306-40615-2', '9780306406157'),
    ('84-376-0494-X', '9788437604947'),
    ('84-376-0494-x', '9788437604947'),
    # ISBN-13 keeps its digits, with or without separators
    ('978-0-306-40615-7', '9780306406157'),
    ('978 0 306 40615 7', '9780306406157'),
    ('9780306406157', '9780306406157'),
    (9780306406157, '9780306406157'),
    # 979 prefixes have no ISBN-10 counterpart
    ('979-10-90636-07-1', '9791090636071'),
    # Labels, typographic dashes and trailing notes are ignored
    ('ISBN-13: 978-0-306-40615-7', '9780306406157'),
    ('ISBN 13 978-0-306-40615-7', '9780306406157'),
    ('isbn 0-306-40615-2', '9780306406157'),
    ('978–0–306–40615–7', '9780306406157'),
    ('9780306406157 (impreso)', '9780306406157'),
])
def test_valid_isbns_are_normalized_to_isbn13(value, expected):
    assert isbn_processor(value) == expected


@pytest.mark.parametrize('value', [
    '0', '', '   ', 'sin isbn',
    '9780306406158',     # wrong ISBN-13 check digit
    '0-306-40615-3',     # wrong ISBN-10 check digit
    '978030640615',      # 12 digits
    '97803064061577',    # 14 digits
    '123456789X123',     # X outside the ISBN-10 check position
    None, True, 3.5, [], {},
])
def test_invalid_values_return_none(value):
    assert isbn_processor(value) is None


def test_first_valid_candidate_wins():
    assert isbn_processor('9780306406158; 978-0-306-40615-7') == '9780306406157'
    assert isbn_processor('8437604946 0306406152') == '9780306406157'
    assert isbn_processor('84-376-0494-X / 978-0-306-40615-7') == '9788437604947'
