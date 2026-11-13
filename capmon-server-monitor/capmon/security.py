import hashlib
import hmac
import secrets
import threading
import time
from collections import OrderedDict


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token():
    return secrets.token_urlsafe(24)


class Authenticator:
    def __init__(self, admin_hash, routers):
        self._admin = bytes.fromhex(admin_hash) if admin_hash else None
        self._routers = {key.lower(): bytes.fromhex(value) for key, value in routers.items()}

    def verify(self, router_id, supplied):
        digest = hashlib.sha256(supplied.encode("utf-8")).digest()
        if router_id is not None:
            expected = self._routers.get(router_id.lower(), self._admin)
            return expected is not None and hmac.compare_digest(digest, expected)
        candidates = list(self._routers.values())
        if self._admin is not None:
            candidates.append(self._admin)
        return any([hmac.compare_digest(digest, item) for item in candidates])


class FailureThrottle:
    def __init__(self, limit, window, capacity):
        self._limit = limit
        self._window = window
        self._capacity = capacity
        self._records = OrderedDict()
        self._guard = threading.Lock()

    def _expire(self, now):
        while self._records:
            address, (count, started) = next(iter(self._records.items()))
            if now - started <= self._window:
                break
            del self._records[address]

    def blocked(self, address):
        now = time.monotonic()
        with self._guard:
            self._expire(now)
            record = self._records.get(address)
            return record is not None and record[0] >= self._limit

    def record(self, address):
        now = time.monotonic()
        with self._guard:
            self._expire(now)
            record = self._records.get(address)
            if record is not None:
                self._records[address] = (record[0] + 1, record[1])
                return
            if len(self._records) >= self._capacity:
                self._records.popitem(last=False)
            self._records[address] = (1, now)

    def clear(self, address):
        with self._guard:
            self._records.pop(address, None)
