"""
rate_limiter.algorithms
------------------------
Four classic rate limiting algorithms, implemented from scratch with
only the standard library. Each class exposes a single method:

    allow(key: str) -> bool

`key` is whatever you want to limit on (IP address, user id, API key...).
Each algorithm keeps its own per-key state in memory (a dict), which is
fine for a single-process demo. For production/multi-process use, swap
the in-memory dict for Redis (see README for notes on that).

Algorithms included:
1. FixedWindowLimiter      - simplest, but bursts at window edges
2. SlidingWindowLogLimiter - exact, but O(n) memory per key
3. SlidingWindowCounterLimiter - approximate, O(1) memory, smooths edges
4. TokenBucketLimiter      - allows bursts up to bucket size, smooth refill
"""

import time
import threading
from collections import deque, defaultdict


class FixedWindowLimiter:
    """
    Divides time into fixed windows (e.g. every 60s). Counts requests
    per key per window. Resets the count when a new window starts.

    Weakness: a client can send `limit` requests at the end of one
    window and `limit` more at the start of the next -> 2x burst.
    """

    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window = window_seconds
        self._counts = defaultdict(lambda: [0, 0.0])  # key -> [count, window_start]
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            count, window_start = self._counts[key]
            if now - window_start >= self.window:
                # new window
                count, window_start = 0, now
            if count < self.limit:
                self._counts[key] = [count + 1, window_start]
                return True
            self._counts[key] = [count, window_start]
            return False


class SlidingWindowLogLimiter:
    """
    Keeps a timestamp log (deque) of every accepted request per key.
    On each call, drops timestamps older than `window_seconds`, then
    checks whether the remaining count is under the limit.

    Exact / no edge-burst problem, but memory grows with request rate
    (O(limit) per key in the worst case).
    """

    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window = window_seconds
        self._logs = defaultdict(deque)  # key -> deque[timestamps]
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            log = self._logs[key]
            cutoff = now - self.window
            while log and log[0] <= cutoff:
                log.popleft()
            if len(log) < self.limit:
                log.append(now)
                return True
            return False


class SlidingWindowCounterLimiter:
    """
    Approximates the sliding log using two fixed windows (current +
    previous) and a weighted average based on how far into the current
    window we are. O(1) memory per key, smooths out the fixed-window
    edge-burst problem without the memory cost of the exact log.

    estimated_count = prev_window_count * (1 - elapsed_fraction)
                       + curr_window_count
    """

    def __init__(self, limit: int, window_seconds: float):
        self.limit = limit
        self.window = window_seconds
        # key -> [curr_window_start, curr_count, prev_count]
        self._state = defaultdict(lambda: [0.0, 0, 0])
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            curr_start, curr_count, prev_count = self._state[key]

            elapsed_windows = (now - curr_start) / self.window if curr_start else 1
            if curr_start == 0.0:
                # first ever request for this key
                curr_start, curr_count, prev_count = now, 0, 0
            elif elapsed_windows >= 2:
                # more than a full window has passed since curr window
                # started -> both windows are stale, reset
                curr_start, curr_count, prev_count = now, 0, 0
            elif elapsed_windows >= 1:
                # we've rolled into a new window
                curr_start = curr_start + self.window
                prev_count = curr_count
                curr_count = 0

            elapsed_fraction = (now - curr_start) / self.window
            estimated = prev_count * (1 - elapsed_fraction) + curr_count

            if estimated < self.limit:
                curr_count += 1
                self._state[key] = [curr_start, curr_count, prev_count]
                return True

            self._state[key] = [curr_start, curr_count, prev_count]
            return False


class TokenBucketLimiter:
    """
    Each key gets a bucket holding up to `capacity` tokens. Tokens
    refill continuously at `refill_rate` tokens/second. Each request
    consumes 1 token; if the bucket is empty, the request is denied.

    Allows short bursts up to `capacity` while enforcing a long-run
    average rate of `refill_rate` requests/second. This is what most
    production APIs (Stripe, GitHub, AWS) use in some form.
    """

    def __init__(self, capacity: int, refill_rate: float):
        """
        capacity: max tokens the bucket can hold (max burst size)
        refill_rate: tokens added per second (steady-state rate limit)
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._buckets = defaultdict(lambda: [capacity, time.time()])  # key -> [tokens, last_refill]
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        with self._lock:
            tokens, last_refill = self._buckets[key]
            now = time.time()
            # max(0, ...) guards against the bucket having just been
            # created with a timestamp fractionally later than `now`
            elapsed = max(0.0, now - last_refill)
            tokens = min(self.capacity, tokens + elapsed * self.refill_rate)

            if tokens >= 1:
                tokens -= 1
                self._buckets[key] = [tokens, now]
                return True

            self._buckets[key] = [tokens, now]
            return False

    def tokens_remaining(self, key: str) -> float:
        """Handy for setting X-RateLimit-Remaining style headers."""
        with self._lock:
            tokens, last_refill = self._buckets[key]
            now = time.time()
            elapsed = max(0.0, now - last_refill)
            return min(self.capacity, tokens + elapsed * self.refill_rate)
