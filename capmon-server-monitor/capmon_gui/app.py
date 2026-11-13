import argparse
import os
import shutil
import sys

from PySide6.QtCore import QEvent, QLockFile, QStandardPaths, Qt
from PySide6.QtGui import QGuiApplication, QSurfaceFormat
from PySide6.QtWidgets import QApplication

from capmon.constants import DEFAULT_PORT
from capmon.paths import app_dir
from capmon.runtime import ServerRuntime

from . import hardening, theme
from .model import Store
from .notify import Notifier
from .window import MainWindow, app_icon

APP_NAME = "CapMonServerMonitor"
APP_ID = "CapMon.ServerMonitor"
LEGACY_NAME = "TrafficSyncGUI"
STATE_FILE = "notified.json"
SAMPLES = 4


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="capmon_server_monitor")
    parser.add_argument(
        "--data-dir",
        default=os.environ.get("TRAFFIC_SYNC_DATA", os.path.join(app_dir(), "data")),
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-tls", action="store_true")
    parser.add_argument("--reset-token", action="store_true")
    parser.add_argument("--allow-capture", action="store_true")
    return parser.parse_args(argv)


def prepare():
    hardening.protect_process()
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    surface = QSurfaceFormat()
    surface.setSamples(SAMPLES)
    QSurfaceFormat.setDefaultFormat(surface)


def state_dir():
    base = app_dir()
    target = os.path.join(base, STATE_FILE)
    if not os.path.exists(target):
        roaming = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        for source in (
            os.path.join(roaming, STATE_FILE),
            os.path.join(os.path.dirname(roaming), LEGACY_NAME, STATE_FILE),
        ):
            if os.path.isfile(source):
                try:
                    shutil.copyfile(source, target)
                except OSError:
                    continue
                break
    return base


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    prepare()
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())
    app.setStyleSheet(theme.STYLE)
    app.setFont(theme.make_font(13))
    hints = app.styleHints()
    if hasattr(hints, "setColorScheme"):
        hints.setColorScheme(Qt.ColorScheme.Dark)
    state = state_dir()
    lock = QLockFile(os.path.join(state, APP_NAME + ".lock"))
    if not lock.tryLock(100):
        return 0
    runtime = ServerRuntime(args.data_dir, args.host, args.port, not args.no_tls, args.reset_token)
    runtime.start()
    window = MainWindow(
        Store(args.data_dir),
        Notifier(os.path.join(state, STATE_FILE)),
        runtime,
        protect=not args.allow_capture,
    )
    app.aboutToQuit.connect(lock.unlock)
    window.show()
    code = app.exec()
    runtime.stop()
    window.deleteLater()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    del window
    return code
