import pytest

from kahi_impactu_utils.Urls import url_host_and_path, url_source_kind


@pytest.mark.parametrize("url, expected", [
    ("http://hdl.handle.net/10495/6956", "handle"),
    ("https://repositorio.ucaldas.edu.co/handle/ucaldas/22330", "handle"),
    ("https://doi.org/10.14201/8946", "doi"),
    ("http://dx.doi.org/10.1/abc", "doi"),
    ("https://www.scielo.org.co/scielo.php?pid=S0120", "scielo"),
    ("https://www.scielo.br/j/rbz/a/x/?format=pdf", "scielo"),
    ("https://doaj.org/article/abc", "doaj"),
    ("https://dialnet.unirioja.es/servlet/articulo?codigo=1", "dialnet"),
    ("https://www.redalyc.org/articulo.oa?id=1", "redalyc"),
    ("https://arxiv.org/abs/1234.5678", "arxiv"),
    ("https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123/", "pmc"),
    ("https://pmc.ncbi.nlm.nih.gov/articles/PMC123/", "pmc"),
    ("https://europepmc.org/article/MED/1", "pmc"),
    ("https://revistas.udea.edu.co/index.php/vitae/article/view/1", "open_access"),
    ("https://www.mdpi.com/2073-4395/10/1/1/pdf", "open_access"),
    ("", "open_access"),
    (None, "open_access"),
])
def test_url_source_kind(url, expected):
    assert url_source_kind(url) == expected


def test_default_label_is_configurable():
    assert url_source_kind("https://example.org/x", default="url") == "url"


def test_url_host_and_path():
    assert url_host_and_path("HTTPS://WWW.Example.org:8080/Path/X") == ("example.org", "/path/x")
    assert url_host_and_path("hdl.handle.net/1/2") == ("hdl.handle.net", "/1/2")
