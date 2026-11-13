import json
import logging
import os
import re
import socket
import ssl
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import TCPServer
from urllib.parse import parse_qs, urlsplit

from .constants import (
    FAIL_WINDOW,
    MAX_BODY,
    REQUEST_DEADLINE,
    RE_LENGTH,
    SOCKET_TIMEOUT,
)
from .protocol import RowError, parse_payload, render_csv, valid_router_id
from .storage import StorageFull

LOG = logging.getLogger("capmon")
RE_PRINTABLE = re.compile(r"[^\x20-\x7e]")
MAX_TOKEN_LENGTH = 256
ACCEPT_WAIT = 2.0
MAX_PER_ADDRESS = 8


class Services:
    def __init__(self, storage, authenticator, throttle, on_store=None, gate=None):
        self.gate = gate
        self.storage = storage
        self.authenticator = authenticator
        self.throttle = throttle
        self.on_store = on_store


class SyncServer(HTTPServer):
    daemon_threads = True
    allow_reuse_address = os.name != "nt"
    request_queue_size = 64

    def __init__(self, address, services, workers, context=None):
        self.address_family = socket.AF_INET6 if ":" in address[0] else socket.AF_INET
        self.dual_stack = address[0] == "::"
        self.services = services
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="sync")
        self._slots = threading.BoundedSemaphore(workers * 4)
        self._active = {}
        self._per_address = {}
        self._guard = threading.Lock()
        self._stopped = threading.Event()
        super().__init__(address, Handler)
        if context is not None:
            self.socket = context.wrap_socket(
                self.socket, server_side=True, do_handshake_on_connect=False
            )
        threading.Thread(target=self._reap, name="reaper", daemon=True).start()

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        if self.dual_stack:
            self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.socket.getsockname()[:2]

    def process_request(self, request, client_address):
        if not self._slots.acquire(timeout=ACCEPT_WAIT):
            self.shutdown_request(request)
            return
        address = client_address[0]
        with self._guard:
            if self._per_address.get(address, 0) >= MAX_PER_ADDRESS:
                self._slots.release()
                self.shutdown_request(request)
                return
            self._per_address[address] = self._per_address.get(address, 0) + 1
            self._active[request] = [time.monotonic() + REQUEST_DEADLINE, address]
        try:
            self._pool.submit(self._serve, request, client_address)
        except RuntimeError:
            self._release(request)
            self.shutdown_request(request)

    def _serve(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)
            self._release(request)

    def _release(self, request):
        with self._guard:
            entry = self._active.pop(request, None)
            if entry is not None:
                remaining = self._per_address.get(entry[1], 1) - 1
                if remaining > 0:
                    self._per_address[entry[1]] = remaining
                else:
                    self._per_address.pop(entry[1], None)
        self._slots.release()

    def _reap(self):
        while not self._stopped.wait(1.0):
            now = time.monotonic()
            with self._guard:
                expired = [item for item, entry in self._active.items() if entry[0] < now]
                for item in expired:
                    self._active[item][0] = float("inf")
            for item in expired:
                try:
                    item.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def handle_error(self, request, client_address):
        error = sys.exc_info()[1]
        if isinstance(error, (OSError, ValueError)):
            LOG.debug("connection error from %s: %s", client_address[0], error)
        else:
            LOG.exception("unhandled error from %s", client_address[0])

    def server_close(self):
        self._stopped.set()
        self._pool.shutdown(wait=False, cancel_futures=True)
        super().server_close()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "TrafficSync"
    sys_version = ""

    def version_string(self):
        return self.server_version

    def setup(self):
        self.request.settimeout(SOCKET_TIMEOUT)
        if isinstance(self.request, ssl.SSLSocket):
            self.request.do_handshake()
        super().setup()

    def log_message(self, fmt, *args):
        LOG.info("%s %s", self.client_address[0], RE_PRINTABLE.sub("?", fmt % args))

    def send_error(self, code, message=None, explain=None):
        phrase = self.responses.get(code, ("error",))[0]
        self.fail(code, phrase.lower())

    def reply(self, code, body=b"", content_type="application/json", headers=None):
        if isinstance(body, dict):
            body = json.dumps(body)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.close_connection = True
        self.send_response(code)
        if code != 204:
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Connection", "close")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if body and code != 204 and self.command != "HEAD":
            self.wfile.write(body)

    def fail(self, code, message, headers=None):
        self.reply(code, {"ok": False, "error": message}, headers=headers)

    def authenticate(self, router_id):
        services = self.server.services
        address = self.client_address[0]
        if services.throttle.blocked(address):
            self.fail(429, "too many attempts", {"Retry-After": str(FAIL_WINDOW)})
            return False
        supplied = self.headers.get("X-Auth-Token", "")
        if len(supplied) <= MAX_TOKEN_LENGTH and services.authenticator.verify(router_id, supplied):
            services.throttle.clear(address)
            return True
        services.throttle.record(address)
        self.fail(401, "unauthorized")
        return False

    def dispatch(self):
        try:
            parts = urlsplit(self.path)
            query = parse_qs(parts.query, keep_blank_values=True, max_num_fields=8)
        except ValueError:
            return self.fail(400, "bad request")
        identifiers = query.get("id", [])
        if len(identifiers) > 1:
            return self.fail(400, "invalid id")
        router_id = identifiers[0] if identifiers else None
        if not self.authenticate(router_id):
            return
        gate = self.server.services.gate
        if gate is not None and not gate.check(router_id, self.client_address[0]):
            return self.fail(403, "this server is paired with another router")
        action = {
            ("GET", "/api/ping"): self.handle_ping,
            ("GET", "/api/data"): self.handle_fetch,
            ("POST", "/api/sync"): self.handle_store,
        }.get((self.command, parts.path))
        if action is None:
            return self.fail(404, "not found")
        action(router_id)

    def do_GET(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch()

    def handle_ping(self, router_id):
        self.reply(200, {"ok": True})

    def handle_fetch(self, router_id):
        if not valid_router_id(router_id):
            return self.fail(400, "invalid id")
        data = self.server.services.storage.read(router_id)
        if data is None:
            return self.reply(204)
        self.reply(200, data, "text/csv; charset=utf-8")

    def handle_store(self, router_id):
        if not valid_router_id(router_id):
            return self.fail(400, "invalid id")
        if "Transfer-Encoding" in self.headers:
            return self.fail(400, "unsupported encoding")
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not RE_LENGTH.match(lengths[0]):
            return self.fail(411, "length required")
        size = int(lengths[0])
        if size > MAX_BODY:
            return self.fail(413, "payload too large")
        raw = self.rfile.read(size)
        if len(raw) != size:
            return self.fail(400, "incomplete body")
        try:
            rows = parse_payload(raw, router_id)
        except RowError as exc:
            return self.fail(400, str(exc))
        gate = self.server.services.gate
        if gate is not None and not gate.claim(router_id, self.client_address[0]):
            return self.fail(403, "this server is paired with another router")
        try:
            self.server.services.storage.write(router_id, render_csv(rows))
        except StorageFull:
            return self.fail(507, "storage full")
        except OSError:
            LOG.exception("cannot store data for %s", router_id)
            return self.fail(500, "storage error")
        callback = self.server.services.on_store
        if callback is not None:
            callback(router_id)
        self.reply(200, {"ok": True, "rows": len(rows)})
