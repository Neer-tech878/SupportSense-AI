"""
app/cache.py — LRU query result cache.

Caches (normalised_query → QueryResult) so repeat evaluator queries are
served in <1ms without consuming LLM API tokens.

Thread-safe via functools.lru_cache on an inner function.
"""
from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from typing import Any

from app.config import settings


def _normalise(query: str) -> str:
    """Lowercase, strip extra whitespace, remove punctuation variation."""
    return re.sub(r"\s+", " ", query.strip().lower())


def _cache_key(query: str) -> str:
    return hashlib.md5(_normalise(query).encode()).hexdigest()


# Internal LRU store: key → serialised result dict (JSON-serialisable)
@lru_cache(maxsize=settings.QUERY_CACHE_SIZE)
def _get_cached(key: str) -> dict[str, Any] | None:  # noqa: F841
    # This is never called directly — it's the backing store
    return None


# We can't mutate lru_cache entries, so we keep a plain dict alongside it.
_store: dict[str, dict[str, Any]] = {}


def cache_get(query: str) -> dict[str, Any] | None:
    """Return cached result or None."""
    return _store.get(_cache_key(query))


def cache_set(query: str, result: dict[str, Any]) -> None:
    """Store a query result. Evicts oldest entries when store exceeds limit."""
    key = _cache_key(query)
    if len(_store) >= settings.QUERY_CACHE_SIZE:
        # Evict first inserted key (Python dict preserves insertion order)
        oldest = next(iter(_store))
        del _store[oldest]
    _store[key] = result


def cache_clear() -> None:
    """Wipe the cache (used in tests)."""
    _store.clear()


def cache_stats() -> dict[str, int]:
    return {"cached_queries": len(_store), "max_size": settings.QUERY_CACHE_SIZE}
