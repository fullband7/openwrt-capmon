import functools
import os
import sys
import tempfile

HOME_NAME = "CapMon"


def _is_writable(directory):
    try:
        with tempfile.TemporaryFile(dir=directory):
            return True
    except OSError:
        return False


def _fallback_dir():
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
    elif sys.platform == "darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, HOME_NAME)


def _executable_dir():
    compiled = globals().get("__compiled__")
    if compiled is not None:
        try:
            return os.path.abspath(compiled.containing_dir)
        except AttributeError:
            return os.path.dirname(os.path.abspath(sys.argv[0]))
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return None


@functools.lru_cache(maxsize=1)
def app_dir():
    base = _executable_dir()
    if base is None:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _is_writable(base):
        return base
    fallback = _fallback_dir()
    os.makedirs(fallback, exist_ok=True)
    return fallback
