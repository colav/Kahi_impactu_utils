from unittest.mock import MagicMock, patch

from kahi_impactu_utils.Elastic import size_similarity_pool


def handler():
    h = MagicMock()
    h.es = MagicMock()
    return h


def test_pool_grows_to_the_configured_concurrency():
    h = handler()
    old = h.es
    with patch("kahi_impactu_utils.Elastic.Elasticsearch") as es:
        assert size_similarity_pool(h, "http://es:9200", ("u", "p"), 32) == 32
    es.assert_called_once()
    assert es.call_args.kwargs["connections_per_node"] == 32
    assert es.call_args.kwargs["basic_auth"] == ("u", "p")
    old.close.assert_called_once()
    assert h.es is es.return_value


def test_default_pool_is_kept_for_low_concurrency():
    h = handler()
    old = h.es
    with patch("kahi_impactu_utils.Elastic.Elasticsearch") as es:
        assert size_similarity_pool(h, "http://es:9200", None, 8) == 10
    es.assert_not_called()
    assert h.es is old
