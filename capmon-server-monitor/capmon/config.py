import ipaddress
import json
import os

from .constants import RE_HEX, RE_TOKEN
from .protocol import valid_router_id
from .security import hash_token, new_token


class Settings:
    def __init__(self, path):
        self.path = path
        self.admin_hash = ""
        self.routers = {}
        self.paired = None
        self._dirty = False
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("invalid configuration file")
        stored = data.get("token_hash", "")
        if isinstance(stored, str) and RE_HEX.match(stored):
            self.admin_hash = stored
        routers = data.get("routers", {})
        if isinstance(routers, dict):
            for key, value in routers.items():
                if valid_router_id(key) and isinstance(value, str) and RE_HEX.match(value):
                    self.routers[key.lower()] = value
        paired = data.get("paired")
        if isinstance(paired, dict):
            identifier = paired.get("id")
            address = paired.get("address")
            if isinstance(identifier, str) and valid_router_id(identifier) and isinstance(address, str):
                try:
                    ipaddress.ip_address(address)
                except ValueError:
                    pass
                else:
                    self.paired = {"id": identifier.lower(), "address": address}
        if "token" in data:
            legacy = data["token"]
            if isinstance(legacy, str) and RE_TOKEN.match(legacy) and not self.admin_hash:
                self.admin_hash = hash_token(legacy)
            self._dirty = True

    def _flush(self):
        payload = {"token_hash": self.admin_hash, "routers": self.routers}
        if self.paired is not None:
            payload["paired"] = self.paired
        temporary = self.path + ".tmp"
        directory = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(directory, exist_ok=True)
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
        self._dirty = False

    def ensure_admin(self, supplied="", reset=False):
        generated = None
        if supplied:
            if not RE_TOKEN.match(supplied):
                raise ValueError("token must be 16 to 128 letters, digits, dots, dashes or underscores")
            digest = hash_token(supplied)
            if digest != self.admin_hash:
                self.admin_hash = digest
                self._dirty = True
        elif reset or not self.admin_hash:
            generated = new_token()
            self.admin_hash = hash_token(generated)
            self._dirty = True
        if self._dirty:
            self._flush()
        return generated

    def pair(self, router_id, address):
        self.paired = {"id": router_id, "address": address}
        self._flush()

    def unpair(self):
        if self.paired is not None:
            self.paired = None
            self._flush()

    def add_router(self, router_id):
        if not valid_router_id(router_id):
            raise ValueError("invalid router id")
        token = new_token()
        self.routers[router_id.lower()] = hash_token(token)
        self._flush()
        return token
