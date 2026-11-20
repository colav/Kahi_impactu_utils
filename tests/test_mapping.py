from kahi_impactu_utils.Mapping import canonical_ror_url


def test_canonical_ror_url_accepts_code_and_repairs_legacy_spacing():
    assert canonical_ror_url("02yr3f298") == "https://ror.org/02yr3f298"
    assert canonical_ror_url("https://ror.org/02yr3f298") == (
        "https://ror.org/02yr3f298")
    assert canonical_ror_url("https: //ror.org/02yr3f298") == (
        "https://ror.org/02yr3f298")
