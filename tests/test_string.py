import warnings

from bs4 import MarkupResemblesLocatorWarning

from kahi_impactu_utils.String import parse_mathml


def test_parse_mathml_ignores_locator_like_plain_text():
    values = ('report/file.pdf', 'https://example.org/document')

    with warnings.catch_warnings():
        warnings.simplefilter('error', MarkupResemblesLocatorWarning)
        assert [parse_mathml(value) for value in values] == list(values)


def test_parse_mathml_still_parses_math_markup():
    value = 'Equation<math><mi>x</mi></math>'

    assert parse_mathml(value) == 'Equation x'
