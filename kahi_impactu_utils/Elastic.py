"""Helpers for the Elasticsearch client that Mohan's Similarity creates."""
from elasticsearch import Elasticsearch

DEFAULT_POOL_SIZE = 10  # urllib3 pool created by Mohan


def size_similarity_pool(handler, es_url, es_auth, max_concurrency, request_timeout=120):
    """
    Give the Similarity handler an Elasticsearch client whose connection pool
    can serve `max_concurrency` concurrent requests.

    Mohan builds the client with urllib3's default pool of 10 connections in
    blocking mode; a plugin whose ES semaphore allows more concurrent calls
    fails with EmptyPoolError. The pool is never made smaller than the default.

    Returns the pool size in use.
    """
    size = max(DEFAULT_POOL_SIZE, int(max_concurrency))
    if size == DEFAULT_POOL_SIZE:
        return size
    previous = handler.es
    handler.es = Elasticsearch(
        es_url,
        basic_auth=es_auth,
        request_timeout=request_timeout,
        retry_on_timeout=True,
        max_retries=5,
        connections_per_node=size,
    )
    previous.close()
    return size


def similarity_pool_size(handler):
    """Connections per node of the handler's client (for checks and tests)."""
    node = handler.es.transport.node_pool.get()
    return node.pool.pool.maxsize if hasattr(node.pool, "pool") else getattr(node.pool, "maxsize", None)
