"""In-memory login rate limiter (single process only; documented limitation)."""
from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable

Key = tuple[str, str]  # (client ip, username)


class LoginRateLimiter:
    MAX_KEYS = 10_000

    def __init__(
        self,
        max_failures: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.window = window_seconds
        self._clock = clock
        self._failures: dict[Key, deque[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: Key, now: float) -> deque[float] | None:
        q = self._failures.get(key)
        if q is None:
            return None
        while q and now - q[0] >= self.window:
            q.popleft()
        if not q:
            del self._failures[key]
            return None
        return q

    def retry_after(self, key: Key) -> int:
        """0 = allowed. Otherwise seconds to wait."""
        with self._lock:
            now = self._clock()
            q = self._prune(key, now)
            if q is None or len(q) < self.max_failures:
                return 0
            return max(1, math.ceil(q[0] + self.window - now))

    def record_failure(self, key: Key) -> None:
        with self._lock:
            now = self._clock()
            if len(self._failures) >= self.MAX_KEYS and key not in self._failures:
                for k in list(self._failures):
                    self._prune(k, now)
            q = self._prune(key, now)
            if q is None:
                q = self._failures.setdefault(key, deque())
            q.append(now)

    def reset(self, key: Key) -> None:
        with self._lock:
            self._failures.pop(key, None)