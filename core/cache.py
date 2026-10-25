"""Simple in-memory cache for performance optimization."""
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional


class Cache:
    """Simple in-memory cache with TTL support."""

    def __init__(self, default_ttl: int = 300):
        """Initialize cache with default TTL in seconds."""
        self._cache: Dict[str, tuple[Any, float]] = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if it exists and is not expired."""
        if key in self._cache:
            value, expiry = self._cache[key]
            if time.time() < expiry:
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL."""
        ttl = ttl if ttl is not None else self.default_ttl
        expiry = time.time() + ttl
        self._cache[key] = (value, expiry)

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()

    def delete(self, key: str) -> bool:
        """Delete a specific key from cache."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def cleanup_expired(self) -> int:
        """Remove expired entries and return count of removed items."""
        current_time = time.time()
        expired_keys = [k for k, (_, expiry) in self._cache.items() if expiry < current_time]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)


# Global cache instance
_global_cache = Cache()


def cached(ttl: int = 300, key_func: Optional[Callable] = None):
    """Decorator to cache function results."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached_value = _global_cache.get(cache_key)
            if cached_value is not None:
                return cached_value
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            _global_cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator


def get_cache() -> Cache:
    """Get the global cache instance."""
    return _global_cache
