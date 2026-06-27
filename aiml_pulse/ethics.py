"""Rate Limiter and HTTP etiquette"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable


class RateLimiter:
    """Simple token-bucket rate limiter (thread-safe)."""

    def __init__(self, rate_per_second: float, capacity: int | None = None) -> None:
        self.rate = rate_per_second
        self.capacity = capacity if capacity is not None else max(1, int(rate_per_second))
        self._tokens = float(self.capacity)
        self._last = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        self._last = now
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)

    def acquire(self, tokens: float = 1.0) -> None:
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                deficit = tokens - self._tokens
                wait_seconds = deficit / self.rate
            time.sleep(max(wait_seconds, 0.01))

    def __call__(self, func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            self.acquire()
            return func(*args, **kwargs)

        return wrapper


# Module-level limiter: 1 request per second across all sources.
default_limiter = RateLimiter(rate_per_second=1.0, capacity=4)


def default_user_agent() -> str:
    from aiml_pulse.config import load_settings

    return load_settings().user_agent