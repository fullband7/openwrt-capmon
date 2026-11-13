import logging
import threading

LOG = logging.getLogger("capmon")


class RouterGate:
    def __init__(self, settings, enforce=True, on_block=None):
        self._settings = settings
        self._enforce = enforce
        self._on_block = on_block
        self._guard = threading.Lock()

    def _matches(self, paired, router_id, address):
        return paired["id"] == router_id.lower() and paired["address"] == address

    def _blocked(self, router_id, address):
        if self._on_block is not None:
            self._on_block(router_id, address)
        return False

    def check(self, router_id, address):
        if not self._enforce or router_id is None:
            return True
        with self._guard:
            paired = self._settings.paired
            if paired is None or self._matches(paired, router_id, address):
                return True
        return self._blocked(router_id, address)

    def claim(self, router_id, address):
        if not self._enforce:
            return True
        with self._guard:
            paired = self._settings.paired
            if paired is None:
                try:
                    self._settings.pair(router_id.lower(), address)
                except OSError:
                    LOG.warning("cannot save the paired router")
                return True
            if self._matches(paired, router_id, address):
                return True
        return self._blocked(router_id, address)
