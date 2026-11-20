"""Classify product URLs by the kind of site that serves them.

Used for the ``source`` label of ``works.external_urls`` entries. The rules
look only at the URL (host and path); journal pages that cannot be told
apart by URL keep the default label.
"""
from urllib.parse import urlparse

URL_SOURCE_RULES = (
    # (label, host test, path test); first match wins
    ("handle", lambda host, path: host == "hdl.handle.net" or "/handle/" in path),
    ("doi", lambda host, path: host in ("doi.org", "dx.doi.org")),
    ("scielo", lambda host, path: "scielo" in host),
    ("doaj", lambda host, path: host == "doaj.org"),
    ("dialnet", lambda host, path: host == "dialnet.unirioja.es"),
    ("redalyc", lambda host, path: "redalyc.org" in host),
    ("arxiv", lambda host, path: host == "arxiv.org"),
    ("pmc", lambda host, path: (host == "ncbi.nlm.nih.gov" and path.startswith("/pmc")) or host == "pmc.ncbi.nlm.nih.gov" or host == "europepmc.org"),
)


def url_host_and_path(url):
    """Return (host, path) lower-cased, without a leading ``www.``."""
    if not url or not isinstance(url, str):
        return "", ""
    value = url.strip()
    if "://" not in value:
        value = "http://" + value
    parsed = urlparse(value)
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host.split(":", 1)[0], (parsed.path or "").lower()


def url_source_kind(url, default="open_access"):
    """Return the ``source`` label for a product URL (handle, doi, scielo,
    doaj, dialnet, redalyc, arxiv, pmc) or ``default`` when no rule matches."""
    host, path = url_host_and_path(url)
    if not host:
        return default
    for label, test in URL_SOURCE_RULES:
        if test(host, path):
            return label
    return default
