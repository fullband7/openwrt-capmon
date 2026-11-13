import os
import shutil
import tempfile
import threading
import time
import zlib

from .constants import (
    BACKUP_INTERVAL,
    DEFAULT_MAX_ROUTERS,
    LOCK_STRIPES,
    REPLACE_ATTEMPTS,
    REPLACE_DELAY,
    STALE_TEMP_AGE,
)


class StorageFull(Exception):
    pass


def _sync_directory(path):
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _replace(source, target):
    for attempt in range(REPLACE_ATTEMPTS):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if os.name != "nt" or attempt == REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(REPLACE_DELAY * (attempt + 1))


class Storage:
    def __init__(self, directory, max_routers=DEFAULT_MAX_ROUTERS, backup_interval=BACKUP_INTERVAL):
        self.directory = os.path.abspath(directory)
        os.makedirs(self.directory, mode=0o700, exist_ok=True)
        self._max_routers = max_routers
        self._backup_interval = backup_interval
        self._locks = [threading.Lock() for _ in range(LOCK_STRIPES)]
        self._creation = threading.Lock()
        self._purge_stale()

    def path(self, router_id):
        return os.path.join(self.directory, router_id + ".csv")

    def lock(self, router_id):
        return self._locks[zlib.crc32(router_id.lower().encode("utf-8")) % LOCK_STRIPES]

    def read(self, router_id):
        with self.lock(router_id):
            try:
                with open(self.path(router_id), "rb") as handle:
                    return handle.read()
            except FileNotFoundError:
                return None

    def write(self, router_id, text):
        target = self.path(router_id)
        with self.lock(router_id):
            if os.path.exists(target):
                self._backup(target)
                self._commit(target, text)
                return
            with self._creation:
                if self._count() >= self._max_routers:
                    raise StorageFull()
                self._commit(target, text)

    def _count(self):
        with os.scandir(self.directory) as entries:
            return sum(1 for entry in entries if entry.name.endswith(".csv") and entry.is_file())

    def _backup(self, target):
        backup = target + ".bak"
        try:
            if time.time() - os.path.getmtime(backup) < self._backup_interval:
                return
        except OSError:
            pass
        try:
            shutil.copyfile(target, backup + ".part")
            _replace(backup + ".part", backup)
        except OSError:
            pass

    def _commit(self, target, text):
        descriptor, temporary = tempfile.mkstemp(prefix=".tmp-", suffix=".part", dir=self.directory)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            _replace(temporary, target)
            _sync_directory(self.directory)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    def _purge_stale(self):
        limit = time.time() - STALE_TEMP_AGE
        with os.scandir(self.directory) as entries:
            for entry in entries:
                if entry.name.startswith(".tmp-") and entry.name.endswith(".part"):
                    try:
                        if entry.stat().st_mtime < limit:
                            os.unlink(entry.path)
                    except OSError:
                        pass
