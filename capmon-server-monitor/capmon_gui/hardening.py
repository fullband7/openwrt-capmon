import ctypes
import ctypes.util
import os
import sys

from PySide6.QtCore import QByteArray, QMimeData, QTimer
from PySide6.QtGui import QGuiApplication

UNSAFE_ENV = (
    "QT_PLUGIN_PATH",
    "QT_QPA_PLATFORM_PLUGIN_PATH",
    "QT_QPA_GENERIC_PLUGINS",
    "QT_QPA_PLATFORMTHEME",
    "QT_IM_MODULE",
    "QT_STYLE_OVERRIDE",
    "QT_DEBUG_PLUGINS",
)
CLIPBOARD_CLEAR_MS = 30000
WDA_MONITOR = 0x1
WDA_EXCLUDEFROMCAPTURE = 0x11
POLICY_EXTENSION_POINTS = 6
POLICY_IMAGE_LOAD = 10
EXTENSION_POINTS_DISABLED = 0x1
IMAGE_NO_LOW_LABEL = 0x2

_guard = {"timer": None, "text": ""}


def scrub_environment():
    for name in UNSAFE_ENV:
        os.environ.pop(name, None)


def _apply_policy(kernel, policy, flags):
    value = ctypes.c_uint32(flags)
    return bool(kernel.SetProcessMitigationPolicy(policy, ctypes.byref(value), ctypes.sizeof(value)))


def _windows_policies():
    try:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.SetProcessMitigationPolicy.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t]
        kernel.SetProcessMitigationPolicy.restype = ctypes.c_int
        _apply_policy(kernel, POLICY_EXTENSION_POINTS, EXTENSION_POINTS_DISABLED)
        _apply_policy(kernel, POLICY_IMAGE_LOAD, IMAGE_NO_LOW_LABEL)
    except (AttributeError, OSError):
        pass


def _posix_limits():
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (ImportError, ValueError, OSError):
        pass
    if sys.platform.startswith("linux"):
        try:
            ctypes.CDLL(None).prctl(4, 0, 0, 0, 0)
        except (AttributeError, OSError):
            pass


def protect_process():
    scrub_environment()
    if sys.platform == "win32":
        _windows_policies()
    else:
        _posix_limits()


def _exclude_windows(handle):
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    function = user32.SetWindowDisplayAffinity
    function.argtypes = [wintypes.HWND, wintypes.DWORD]
    function.restype = wintypes.BOOL
    return bool(function(handle, WDA_EXCLUDEFROMCAPTURE)) or bool(function(handle, WDA_MONITOR))


def _exclude_macos(view):
    library = ctypes.CDLL(ctypes.util.find_library("objc"))
    library.sel_registerName.restype = ctypes.c_void_p
    library.sel_registerName.argtypes = [ctypes.c_char_p]
    address = ctypes.cast(library.objc_msgSend, ctypes.c_void_p).value
    getter = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)(address)
    setter = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong)(address)
    window = getter(view, library.sel_registerName(b"window"))
    if not window:
        return False
    setter(window, library.sel_registerName(b"setSharingType:"), 0)
    return True


def protect_window(window):
    try:
        handle = int(window.winId())
        if sys.platform == "win32":
            return _exclude_windows(handle)
        if sys.platform == "darwin":
            return _exclude_macos(handle)
    except (AttributeError, OSError, TypeError, ValueError):
        pass
    return False


def _privacy_formats():
    if sys.platform == "win32":
        flag = QByteArray(b"\x00\x00\x00\x00")
        prefix = 'application/x-qt-windows-mime;value="%s"'
        return (
            (prefix % "ExcludeClipboardContentFromMonitorProcessing", QByteArray(b"1")),
            (prefix % "CanIncludeInClipboardHistory", flag),
            (prefix % "CanUploadToCloudClipboard", flag),
        )
    if sys.platform == "darwin":
        return (("org.nspasteboard.ConcealedType", QByteArray(b"")),)
    return (("x-kde-passwordManagerHint", QByteArray(b"secret")),)


def release_secret():
    text = _guard["text"]
    _guard["text"] = ""
    timer = _guard["timer"]
    if timer is not None:
        timer.stop()
    if text:
        clipboard = QGuiApplication.clipboard()
        if clipboard.text() == text:
            clipboard.clear()


def copy_secret(text):
    mime = QMimeData()
    mime.setText(text)
    for name, payload in _privacy_formats():
        mime.setData(name, payload)
    QGuiApplication.clipboard().setMimeData(mime)
    timer = _guard["timer"]
    if timer is None:
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(release_secret)
        _guard["timer"] = timer
    _guard["text"] = text
    timer.start(CLIPBOARD_CLEAR_MS)
