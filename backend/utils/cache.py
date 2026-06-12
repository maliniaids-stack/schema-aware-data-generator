"""
backend/utils/cache.py
JSON-based caching utility for LLM column mappings.
Stores schema-hash → Faker mapping to avoid redundant Groq API calls.
"""

import os
import json

CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "mapper_cache.json")


def load_cache() -> dict:
    """Load the mapper cache from disk. Returns empty dict on failure."""
    path = os.path.abspath(CACHE_FILE)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    """Persist the mapper cache to disk."""
    path = os.path.abspath(CACHE_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def get_cache_path() -> str:
    """Return the resolved path to the cache file."""
    return os.path.abspath(CACHE_FILE)
