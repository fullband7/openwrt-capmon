import os
import threading
import time
from dataclasses import dataclass, field, replace

from .config import Settings
from .constants import (
    DEFAULT_MAX_ROUTERS,
    DEFAULT_PORT,
    DEFAULT_WORKERS,
    FAIL_LIMIT,
    FAIL_TRACKED,
    FAIL_WINDOW,
    RE_TOKEN,
)
from .netinfo import lan_addresses
from .pairing import RouterGate
from .paths import app_dir
from .security import Authenticator, FailureThrottle, hash_token
from .server import Services, SyncServer
from .storage import Storage
from .tls import build_context, ensure_certificate, public_key_pin


@dataclass(frozen=True, slots=True)
class ConnectionInfo:
    running: bool = False
    scheme: str = "https"
    address: str = ""
    port: int = 0
    token: str = field(default="", repr=False)
    pin: str = ""
    error: str = ""
    blocked: str = ""


class ServerRuntime:
    def __init__(self, data_dir=None, host="0.0.0.0", port=DEFAULT_PORT, tls=True, reset_token=False):
        base = app_dir()
        self.data_dir = data_dir or os.path.join(base, "data")
        self.config_path = os.path.join(base, "config.json")
        self.token_path = os.path.join(base, "admin_token.txt")
        self.cert_path = os.path.join(base, "certs", "server.crt")
        self.key_path = os.path.join(base, "certs", "server.key")
        self.host = host
        self.port = port
        self.tls = tls
        self.reset_token = reset_token
        self.ready = threading.Event()
        self.last_store = 0.0
        self._info = ConnectionInfo(scheme="https" if tls else "http", port=port)
        self._server = None
        self._thread = None
        self._starter = None
        self._resetting = False
        self._lock = threading.Lock()

    @property
    def info(self):
        return self._info

    def start(self):
        if self._starter is None:
            self._starter = threading.Thread(target=self._boot, name="server-boot", daemon=True)
            self._starter.start()

    def reset_credentials(self):
        with self._lock:
            if self._resetting:
                return False
            self._resetting = True
        self.ready.clear()
        threading.Thread(target=self._reset, name="server-reset", daemon=True).start()
        return True

    def _reset(self):
        try:
            starter = self._starter
            if starter is not None:
                starter.join(timeout=15)
            self.stop()
            if self.tls:
                for path in (self.cert_path, self.key_path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
            self.reset_token = True
            self._boot()
        finally:
            self.reset_token = False
            self._resetting = False
            self.ready.set()

    def stop(self):
        server = self._server
        self._server = None
        if server is not None:
            try:
                server.shutdown()
            finally:
                server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None

    def _stored_token(self, settings):
        try:
            with open(self.token_path, "r", encoding="utf-8") as handle:
                value = handle.read().strip()
        except OSError:
            return ""
        if RE_TOKEN.match(value) and hash_token(value) == settings.admin_hash:
            return value
        return ""

    def _save_token(self, token):
        descriptor = os.open(self.token_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(token)

    def _resolve_token(self, settings):
        supplied = os.environ.pop("TRAFFIC_SYNC_TOKEN", "")
        if supplied and not self.reset_token:
            settings.ensure_admin(supplied)
            return supplied
        if not self.reset_token:
            known = self._stored_token(settings)
            if known:
                return known
            if settings.admin_hash:
                return ""
        return settings.ensure_admin("", self.reset_token) or ""

    def _boot(self):
        scheme = "https" if self.tls else "http"
        address = ""
        token = ""
        pin = ""
        try:
            settings = Settings(self.config_path)
            token = self._resolve_token(settings)
            if self.reset_token:
                settings.unpair()
            if token and token != self._stored_token(settings):
                self._save_token(token)
            storage = Storage(self.data_dir, max_routers=DEFAULT_MAX_ROUTERS)
            addresses = lan_addresses() if self.host in ("0.0.0.0", "::") else [self.host]
            address = addresses[0]
            context = None
            if self.tls:
                ensure_certificate(self.cert_path, self.key_path, addresses)
                context = build_context(self.cert_path, self.key_path)
                pin = public_key_pin(self.cert_path)
            services = Services(
                storage,
                Authenticator(settings.admin_hash, settings.routers),
                FailureThrottle(FAIL_LIMIT, FAIL_WINDOW, FAIL_TRACKED),
                on_store=self._stored,
                gate=RouterGate(settings, on_block=self._blocked),
            )
            server = SyncServer((self.host, self.port), services, DEFAULT_WORKERS, context)
        except Exception as exc:
            self._info = ConnectionInfo(False, scheme, address, self.port, token, pin, str(exc) or exc.__class__.__name__)
            self.ready.set()
            return
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, name="server", daemon=True)
        self._thread.start()
        self._info = ConnectionInfo(True, scheme, address, self.port, token, pin)
        self.ready.set()

    def _blocked(self, router_id, address):
        self._info = replace(self._info, blocked="%s (%s)" % (router_id, address))

    def _stored(self, router_id):
        self.last_store = time.time()
