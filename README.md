# Rate Limiter

A from-scratch rate limiter implementing four classic algorithms, plus a
Flask middleware/demo to see them protecting real routes.

## Structure

```
rate_limiter/
├── algorithms.py       # the four limiter implementations (pure Python, no deps)
├── middleware.py        # Flask decorator that wraps a route with a limiter
├── app.py                # demo Flask app, one endpoint per algorithm
├── test_algorithms.py    # pytest unit tests
└── README.md
```

## Setup

```bash
pip install flask pytest
python app.py
```

Then in another terminal:

```bash
for i in {1..10}; do
  curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/token-bucket
done
```

You should see `200` for the first few requests, then `429` once the limit
is hit.

Run tests:

```bash
pytest test_algorithms.py -v
```

## Algorithms, and when to use which

| Algorithm | Memory/key | Burst behavior | Notes |
|---|---|---|---|
| **Fixed Window** | O(1) | Can allow 2x limit at window boundary | Simplest, cheapest. Fine for coarse limits. |
| **Sliding Window Log** | O(limit) | Exact, no edge burst | Most accurate, but memory scales with traffic. |
| **Sliding Window Counter** | O(1) | Approximate, smooths edges | Good middle ground — what Cloudflare/Kong roughly use. |
| **Token Bucket** | O(1) | Allows controlled bursts up to bucket size | Most common in production APIs (Stripe, GitHub, AWS). Use this by default. |

## Using it in your own routes

```python
from algorithms import TokenBucketLimiter
from middleware import rate_limit

# 10 requests burst, refilling at 2/sec (steady-state = 2 req/s)
limiter = TokenBucketLimiter(capacity=10, refill_rate=2)

@app.route("/api/messages")
@rate_limit(limiter)
def send_message():
    ...
```

By default the limiter keys on client IP (`X-Forwarded-For` if present,
else `remote_addr`). To limit per logged-in user instead:

```python
@rate_limit(limiter, key_func=lambda req: req.headers.get("Authorization", "anon"))
def my_route():
    ...
```

## Going to production / multi-process

Everything here stores state in an in-memory `dict` on the limiter
instance, which works for a single Python process. If you run multiple
workers (gunicorn with >1 worker, multiple containers, etc.) each process
has its own counts, so the *effective* limit becomes `limit × num_workers`.

To fix that, swap the in-memory dict for Redis:
- **Fixed window**: `INCR` + `EXPIRE` on a key like `rl:{key}:{window_id}`.
- **Token bucket**: store `tokens` and `last_refill` as a Redis hash, do the
  refill math in a Lua script (`EVAL`) so the read-modify-write is atomic.
- **Sliding window log**: a Redis sorted set (`ZADD`, `ZREMRANGEBYSCORE`,
  `ZCARD`) keyed per-user — this maps almost 1:1 to the in-memory deque
  version here.

Happy to build the Redis-backed version next if you want to plug this into
your chat app for connection/message throttling — could be a good fit for
your Flask+SocketIO project to stop a client from spamming socket events.
