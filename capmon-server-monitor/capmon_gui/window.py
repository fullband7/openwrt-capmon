import time

from PySide6.QtCore import QEvent, QRect, Qt, QTimer
from PySide6.QtGui import QAction, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from capmon import __version__

from . import hardening, theme
from .chrome import NAME, Frame, Header, LoadingOverlay, Outline, TitleBar
from .model import SYNC_WINDOW, acl_view, connection_view, stats_view
from .pages import AboutPage, AclPage, Gate, SettingsPage, StatsPage
from .widgets import RIGHT, ConfirmDialog, Dropdown, Text, logo_pixmap

TITLE = NAME
INTERVAL_MS = 5000
LOADING_MS = 3000
SETTLE_MS = 1000
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
TABS = ("Statistics", "Access Control", "App Settings", "About")


def app_icon():
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(logo_pixmap(size))
    return icon


def scrolled(page):
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.viewport().setAutoFillBackground(False)
    area.setWidget(page)
    page.setAutoFillBackground(False)
    return area


class MainWindow(QMainWindow):
    def __init__(self, store, notifier, runtime, protect=True):
        super().__init__()
        self.protect = protect
        self._protected = False
        self.store = store
        self.notifier = notifier
        self.runtime = runtime
        self.snapshots = {}
        self.period = "total"
        self.overlay = None
        self._loading_elapsed = False
        self._settled = False
        self._blocked_seen = ""
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowSystemMenuHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle(TITLE)
        self.setWindowIcon(app_icon())
        self.setFixedSize(theme.WIDTH + 2 * theme.MARGIN, theme.HEIGHT + 2 * theme.MARGIN)
        self._build()
        self._build_tray()
        self.timer = QTimer(self)
        self.timer.setInterval(INTERVAL_MS)
        self.timer.timeout.connect(self.refresh)
        self.refresh()
        self.timer.start()
        QApplication.instance().applicationStateChanged.connect(self._app_state)
        QTimer.singleShot(LOADING_MS, self._loading_done)
        QTimer.singleShot(SETTLE_MS, self._settle)

    def _build(self):
        margin = theme.MARGIN
        self.root = Frame()
        root = QVBoxLayout(self.root)
        root.setContentsMargins(margin, margin, margin, margin)
        root.setSpacing(0)
        self.header = Header()
        root.addWidget(self.header)
        shell = QVBoxLayout()
        shell.setContentsMargins(32, 32, 32, 32)
        shell.addWidget(self._build_main())
        root.addLayout(shell, 1)
        self.setCentralWidget(self.root)
        area = QRect(margin, margin, theme.WIDTH, theme.HEIGHT)
        self.titlebar = TitleBar(self.root)
        self.titlebar.setGeometry(margin, margin, theme.WIDTH, theme.TITLEBAR)
        self.titlebar.minimize_requested.connect(self.hide)
        self.titlebar.close_requested.connect(self.close)
        self.version = Text(
            theme.make_font(14, QFont.Weight.Medium), theme.rgba(204, 204, 204, 0.6), align=RIGHT, line=18, parent=self.root
        )
        self.version.set_text("v" + __version__)
        self.version.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.version.setGeometry(margin + theme.WIDTH - 32 - 200, margin + theme.HEIGHT - 25, 200, 18)
        self.overlay = LoadingOverlay(self.root)
        self.overlay.setGeometry(area)
        self.outline = Outline(self.root)
        self.outline.setGeometry(area)
        self.titlebar.raise_()
        self.outline.raise_()

    def _build_main(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        bar = QFrame()
        bar.setObjectName("tabbar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(10, 10, 10, 10)
        row.setSpacing(8)
        self.tabs = QButtonGroup(self)
        for index, label in enumerate(TABS):
            button = QPushButton(label)
            button.setObjectName("tab")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.tabs.addButton(button, index)
            row.addWidget(button)
        self.tabs.button(0).setChecked(True)
        self.tabs.idClicked.connect(self._switch)
        row.addStretch(1)
        self.routers = Dropdown([], "", width=220, height=36)
        self.routers.changed.connect(lambda _: self.render())
        self.routers.hide()
        row.addWidget(self.routers)
        self.stats = StatsPage()
        self.stats.period_changed.connect(self._period)
        self.acl = AclPage()
        self.settings = SettingsPage()
        self.settings.reset_requested.connect(self._confirm_reset)
        self._reset_timer = QTimer(self)
        self._reset_timer.setInterval(250)
        self._reset_timer.timeout.connect(self._poll_reset)
        self.about = AboutPage()
        self.gates = (Gate(self.stats), Gate(self.acl))
        for gate in self.gates:
            gate.refresh_requested.connect(self._manual_refresh)
        self.pages = QStackedWidget()
        self.pages.addWidget(scrolled(self.gates[0]))
        self.pages.addWidget(scrolled(self.gates[1]))
        self.pages.addWidget(scrolled(self.settings))
        self.pages.addWidget(scrolled(self.about))
        layout.addWidget(bar)
        layout.addWidget(self.pages, 1)
        return page

    def _build_tray(self):
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(TITLE)
        menu = QMenu(self)
        show = QAction("Open", menu)
        show.triggered.connect(self.restore)
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit)
        menu.addAction(show)
        menu.addSeparator()
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.messageClicked.connect(self.restore)
        self.tray.show()

    def _tray_activated(self, reason):
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.restore()

    def restore(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.render()

    def quit(self):
        self.close()

    def showEvent(self, event):
        super().showEvent(event)
        if self.protect and not self._protected:
            self._protected = hardening.protect_window(self)
        self.render()

    def _app_state(self, state):
        if state != Qt.ApplicationState.ApplicationActive:
            self.settings.conceal()

    def _settle(self):
        self._settled = True

    def changeEvent(self, event):
        if self._settled and event.type() == QEvent.Type.WindowStateChange and self.isMinimized():
            QTimer.singleShot(0, self.hide)
        super().changeEvent(event)

    def closeEvent(self, event):
        self.settings.conceal()
        hardening.release_secret()
        self.timer.stop()
        self.tray.hide()
        self.runtime.stop()
        event.accept()
        QApplication.quit()

    def _confirm_reset(self):
        dialog = ConfirmDialog(
            "Do you want to reset the credentials?",
            "A new token and certificate will be generated. Routers using the old token or pin must be updated.",
            self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if self.runtime.reset_credentials():
            self.settings.conceal()
            self.settings.set_busy(True)
            self._reset_timer.start()

    def _poll_reset(self):
        if not self.runtime.ready.is_set():
            return
        self._reset_timer.stop()
        self.settings.set_busy(False)
        self.settings.conceal()
        self.render()
        error = self.runtime.info.error
        if error:
            self.tray.showMessage(
                "Server could not start", error, QSystemTrayIcon.MessageIcon.Warning, 10000
            )

    def _loading_done(self):
        self._loading_elapsed = True
        self._finish_loading()

    def _finish_loading(self):
        if self.overlay is None or not self._loading_elapsed:
            return
        if not self.runtime.ready.is_set():
            QTimer.singleShot(150, self._finish_loading)
            return
        overlay = self.overlay
        self.overlay = None
        overlay.finish()
        error = self.runtime.info.error
        if error:
            self.tray.showMessage(
                "Server could not start", error, QSystemTrayIcon.MessageIcon.Warning, 10000
            )

    def _switch(self, index):
        self.pages.setCurrentIndex(index)
        self.render()

    def _period(self, period):
        self.period = period
        self.render()

    def _manual_refresh(self):
        for gate in self.gates:
            gate.set_busy(True)
        QTimer.singleShot(400, self._after_refresh)

    def _after_refresh(self):
        self.refresh()
        for gate in self.gates:
            gate.set_busy(False)

    def refresh(self):
        self.snapshots = self.store.scan()
        for title, body in self.notifier.check(self.snapshots):
            self.tray.showMessage(title, body, QSystemTrayIcon.MessageIcon.Warning, 10000)
        self._update_sync()
        self._announce_block()
        if self.isVisible():
            self.render()

    def _announce_block(self):
        blocked = self.runtime.info.blocked
        if not blocked:
            self._blocked_seen = ""
        elif blocked != self._blocked_seen:
            self._blocked_seen = blocked
            self.tray.showMessage(
                "Router blocked",
                "%s tried to connect but this server is paired with another router." % blocked,
                QSystemTrayIcon.MessageIcon.Warning,
                10000,
            )

    def _update_sync(self):
        last = max(self.runtime.last_store, self.store.latest)
        self.header.badge.set_synced(last > 0 and time.time() - last <= SYNC_WINDOW)

    def _selected(self):
        ids = list(self.snapshots)
        choice = self.routers.value()
        return choice if choice in self.snapshots else ids[0]

    def render(self):
        index = self.pages.currentIndex()
        if index >= 2:
            self.routers.hide()
            if index == 2:
                self.settings.render(connection_view(self.runtime.info))
            return
        gate = self.gates[index]
        if not self.snapshots:
            self.routers.hide()
            gate.show_empty()
            return
        gate.show_content()
        selected = self._selected()
        self.routers.set_items([(rid, rid) for rid in self.snapshots], selected)
        self.routers.setVisible(len(self.snapshots) > 1)
        snapshot = self.snapshots[selected]
        if index == 0:
            self.stats.render(stats_view(snapshot, self.period))
        else:
            self.acl.render(acl_view(snapshot))
