"""
Demo Flask app: one endpoint per algorithm so you can hammer each
with curl/Postman and see the 429s kick in differently.

Run:
    pip install flask    
    python app.py

Try (from another terminal):
    for i in {1..10}; do curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/token-bucket; done
"""

from flask import Flask, jsonify
from algorithms import (
    FixedWindowLimiter,
    SlidingWindowLogLimiter,
    SlidingWindowCounterLimiter,
    TokenBucketLimiter,
)
from middleware import rate_limit

app = Flask(__name__)

# 5 requests per 10 seconds, four different strategies
fixed_window = FixedWindowLimiter(limit=5, window_seconds=10)
sliding_log = SlidingWindowLogLimiter(limit=5, window_seconds=10)
sliding_counter = SlidingWindowCounterLimiter(limit=5, window_seconds=10)
token_bucket = TokenBucketLimiter(capacity=5, refill_rate=0.5)  # burst 5, refill 1 per 2s


@app.route("/fixed-window")
@rate_limit(fixed_window)
def fixed_window_route():
    return jsonify({"algorithm": "fixed_window", "ok": True})


@app.route("/sliding-log")
@rate_limit(sliding_log)
def sliding_log_route():
    return jsonify({"algorithm": "sliding_window_log", "ok": True})


@app.route("/sliding-counter")
@rate_limit(sliding_counter)
def sliding_counter_route():
    return jsonify({"algorithm": "sliding_window_counter", "ok": True})


@app.route("/token-bucket")
@rate_limit(token_bucket)
def token_bucket_route():
    return jsonify({"algorithm": "token_bucket", "ok": True})


@app.route("/")
def index():
    return jsonify({
        "message": "Rate limiter demo. Try hitting these endpoints repeatedly:",
        "endpoints": [
            "/fixed-window",
            "/sliding-log",
            "/sliding-counter",
            "/token-bucket",
        ],
        "limit": "5 requests per 10 seconds (each endpoint tracked independently)",
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
