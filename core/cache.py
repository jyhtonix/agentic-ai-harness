"""
LLM response cache.

Reduces cost and latency by caching deterministic LLM responses.
Uses an in-memory LRU cache with optional TTL.
For production, swap with Redis-backed implementation.
"""

import hashlib
import json
import logging
import time
from collections import OrderedDict
from typing import Optional

logger = logging.getLogger("core.cache")


class LLMCache:
    """
    In-memory LRU cache for LLM responses.

    Caches by (model, messages_json, temperature) hash.
    Respects TTL and max size.
    """

    def __init__(self, max_size: int = 500, ttl_seconds: int = 3600):
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._cache: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def _make_key(self, model: str, messages: list[dict], temperature: float) -> str:
        content = json.dumps({
            "model": model,
            "messages": messages,
            "temperature": round(temperature, 2),
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, model: str, messages: list[dict], temperature: float = 0.0) -> Optional[str]:
        key = self._make_key(model, messages, temperature)
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            return None

        expiry, response = entry
        if time.time() > expiry:
            self._cache.pop(key)
            self._misses += 1
            return None

        self._cache.move_to_end(key)
        self._hits += 1
        return response

    def set(self, model: str, messages: list[dict], response: str,
            temperature: float = 0.0, ttl: Optional[int] = None) -> None:
        key = self._make_key(model, messages, temperature)
        expiry = time.time() + (ttl or self._ttl)
        self._cache[key] = (expiry, response)
        self._cache.move_to_end(key)

        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 4) if total else 0.0,
        }

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0


llm_cache = LLMCache()
