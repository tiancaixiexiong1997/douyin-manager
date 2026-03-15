"""登录限流器（按客户端 IP）。"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from app.config import settings


class LoginRateLimiter:
    def __init__(self, window_seconds: int, max_attempts: int) -> None:
        self._window_seconds = max(10, int(window_seconds))
        self._max_attempts = max(1, int(max_attempts))
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _trim(self, key: str, now: float) -> deque[float]:
        queue = self._events[key]
        threshold = now - self._window_seconds
        while queue and queue[0] < threshold:
            queue.popleft()
        return queue

    def hit(self, key: str) -> tuple[bool, int]:
        """记录一次尝试，返回 (是否允许, 需等待秒数)。"""
        now = time.time()
        with self._lock:
            queue = self._trim(key, now)
            if len(queue) >= self._max_attempts:
                retry_after = max(1, int(self._window_seconds - (now - queue[0])))
                return False, retry_after
            queue.append(now)
            return True, 0

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)


login_rate_limiter = LoginRateLimiter(
    window_seconds=settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
    max_attempts=settings.AUTH_RATE_LIMIT_MAX_ATTEMPTS,
)
