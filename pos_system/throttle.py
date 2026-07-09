from django.core.cache import cache


def register_attempt(key: str, window_seconds: int) -> int:
    """Record one attempt for `key` and return the new attempt count within the window."""
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=window_seconds)
        count = 1
    return count


def too_many_attempts(key: str, *, limit: int, window_seconds: int) -> bool:
    """Check whether `key` has already exceeded `limit` attempts within the window, without recording a new attempt."""
    count = cache.get(key, 0)
    return count >= limit


def throttle(key: str, *, limit: int, window_seconds: int) -> bool:
    """Register an attempt for `key` and return True if it should now be blocked (limit exceeded)."""
    count = register_attempt(key, window_seconds)
    return count > limit


def reset_throttle(key: str) -> None:
    cache.delete(key)
