"""Thread-safe minimum-interval rate limiter."""

from __future__ import annotations

import threading
import time


class RateLimiter:
    def __init__(self, min_interval: float = 0.5) -> None:
        self.min_interval = max(0.0, min_interval)
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                time.sleep(wait)
            self._next_allowed = time.monotonic() + self.min_interval

