"""Bound paid demo requests in one server process, without retaining chat content.

Use a shared limiter at the proxy/provider for multiple workers or replicas. These
in-memory limits reset when the process restarts; they are not a billing cap.
"""
from collections import deque
from contextlib import contextmanager
import math
import threading
import time

from fastapi import HTTPException


class DemoBudget:
    def __init__(self, *, hourly, per_client, concurrent, clock=time.monotonic):
        self.hourly = hourly
        self.per_client = per_client
        self.concurrent = concurrent
        self._clock = clock
        self._calls = deque()
        self._active = 0
        self._lock = threading.Lock()

    @contextmanager
    def reserve(self, client):
        now = self._clock()
        with self._lock:
            while self._calls and now - self._calls[0][0] >= 3600:
                self._calls.popleft()
            own = [stamp for stamp, caller in self._calls if caller == client]
            oldest = None
            if len(self._calls) >= self.hourly:
                oldest = self._calls[0][0]
            elif len(own) >= self.per_client:
                oldest = own[0]
            if oldest is not None:
                raise HTTPException(429, "The demo's hourly quota is full. Please try later.",
                                    headers={"Retry-After": str(max(1, math.ceil(3600 - (now - oldest))))})
            if self._active >= self.concurrent:
                raise HTTPException(429, "The demo is busy. Please try again shortly.",
                                    headers={"Retry-After": "2"})
            # Count admitted attempts, including provider errors. Rejected attempts
            # never call the provider and do not consume more memory.
            self._calls.append((now, client))
            self._active += 1
        try:
            yield
        finally:
            with self._lock:
                self._active -= 1
