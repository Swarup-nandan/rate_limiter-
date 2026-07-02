"""
Quick tests for each algorithm. Run with:
    pip install pytest
    pytest test_algorithms.py -v
"""

import time
import pytest
from algorithms import (
    FixedWindowLimiter,
    SlidingWindowLogLimiter,
    SlidingWindowCounterLimiter,
    TokenBucketLimiter,
)


def test_fixed_window_allows_up_to_limit():
    limiter = FixedWindowLimiter(limit=3, window_seconds=1)
    results = [limiter.allow("user1") for _ in range(5)]
    assert results == [True, True, True, False, False]


def test_fixed_window_resets_after_window():
    limiter = FixedWindowLimiter(limit=2, window_seconds=0.3)
    assert limiter.allow("user1") is True
    assert limiter.allow("user1") is True
    assert limiter.allow("user1") is False
    time.sleep(0.35)
    assert limiter.allow("user1") is True


def test_sliding_log_allows_up_to_limit():
    limiter = SlidingWindowLogLimiter(limit=3, window_seconds=1)
    results = [limiter.allow("user1") for _ in range(5)]
    assert results == [True, True, True, False, False]


def test_sliding_log_expires_old_entries():
    limiter = SlidingWindowLogLimiter(limit=2, window_seconds=0.3)
    assert limiter.allow("user1") is True
    assert limiter.allow("user1") is True
    assert limiter.allow("user1") is False
    time.sleep(0.35)
    assert limiter.allow("user1") is True


def test_sliding_counter_allows_up_to_limit():
    limiter = SlidingWindowCounterLimiter(limit=3, window_seconds=1)
    results = [limiter.allow("user1") for _ in range(5)]
    assert results == [True, True, True, False, False]


def test_token_bucket_allows_burst_up_to_capacity():
    limiter = TokenBucketLimiter(capacity=3, refill_rate=1)
    results = [limiter.allow("user1") for _ in range(5)]
    assert results == [True, True, True, False, False]


def test_token_bucket_refills_over_time():
    limiter = TokenBucketLimiter(capacity=1, refill_rate=10)  # 1 token per 0.1s
    assert limiter.allow("user1") is True
    assert limiter.allow("user1") is False
    time.sleep(0.15)
    assert limiter.allow("user1") is True


def test_keys_are_independent():
    limiter = TokenBucketLimiter(capacity=1, refill_rate=0.1)
    assert limiter.allow("alice") is True
    assert limiter.allow("bob") is True  # separate bucket, not affected by alice
    assert limiter.allow("alice") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
