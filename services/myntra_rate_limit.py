"""Small in-process limiter for event ingestion; production may replace it with shared storage."""
from collections import defaultdict, deque
from threading import Lock
from time import monotonic

WINDOW_SECONDS = 60
MAX_REQUESTS = 60
_requests = defaultdict(deque)
_lock = Lock()

def allow(user_id: str) -> bool:
    now = monotonic()
    with _lock:
        bucket = _requests[user_id]
        while bucket and now - bucket[0] >= WINDOW_SECONDS: bucket.popleft()
        if len(bucket) >= MAX_REQUESTS: return False
        bucket.append(now); return True
