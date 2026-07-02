"""
rate_limiter.middleware
-------------------------
Flask integration: a decorator that wraps a route with any limiter
from algorithms.py and returns proper 429 responses + rate-limit
headers.
"""

from functools import wraps
from flask import request, jsonify, g


def rate_limit(limiter, key_func=None):
    """
    Decorator factory. Usage:

        bucket = TokenBucketLimiter(capacity=5, refill_rate=1)

        @app.route("/api/data")
        @rate_limit(bucket)
        def get_data():
            return jsonify({"ok": True})

    key_func: optional callable(request) -> str to determine the
    rate-limit key. Defaults to client IP address.
    """
    def default_key_func(req):
        # X-Forwarded-For first, in case you're behind a proxy/load balancer
        return req.headers.get("X-Forwarded-For", req.remote_addr) or "unknown"

    resolve_key = key_func or default_key_func

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = resolve_key(request)
            allowed = limiter.allow(key)

            if not allowed:
                resp = jsonify({
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please slow down and try again shortly.",
                })
                resp.status_code = 429
                resp.headers["Retry-After"] = "1"
                return resp

            return fn(*args, **kwargs)
        return wrapper
    return decorator
