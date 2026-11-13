import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .model import PERIODS, STATES
from .widgets import (
    RIGHT,
    Bar,
    CopyField,
    Dropdown,
    EmptyBox,
    CopyButton,
    FluidGrid,
    LinkRow,
    Panel,
    StatsTable,
    Text,
    Tile,
)

BLOCKED_NOTICE = "Another router was blocked: %s. This server is paired with a different router. Use Reset Credentials to pair a new one."
ABOUT_LINE = '<p style="margin:0; line-height:165%%">%s</p>'
ABOUT_TEXT = (
    "CapMon Server Monitor is a personal project and has not yet been tested on different "
    "routers and architectures, so it may contain bugs and issues. Please visit the official "
    "GitHub page of the app to get the latest updates."
)
OFFICIAL_ICON = "github.svg"
OFFICIAL_NAME = "Official GitHub Page"
OFFICIAL_URL = "https://github.com/fullband7/openwrt-capmon"
RESET_LABEL = "Reset Credentials"
PROJECTS_TITLE = "My Other Project"
PROJECT_ICON = "foxhound.svg"
PROJECT_NAME = "Luci Theme FoxHound"
PROJECT_URL = "https://github.com/fullband7/openwrt-theme-foxhound"
CONTACT_TITLE = "Contact Me :"
CONTACT_ICON = "email.svg"
CONTACT_EMAIL = "fullband7@hotmail.com"

CHIP = {"x": 9, "y": 2, "radius": 12, "border": theme.LINE}
PILL_TONES = {
    "ok": (theme.DOWN, {"x": 11, "y": 4, "radius": 14, "border": theme.rgba(31, 169, 113, 0.5),
                        "fill": theme.rgba(31, 169, 113, 0.1)}),
    "blocked": (theme.BAD, {"x": 11, "y": 4, "radius": 14, "border": theme.rgba(229, 72, 77, 0.5),
                            "fill": theme.rgba(229, 72, 77, 0.1)}),
    "off": (theme.rgba(204, 204, 204, 0.7), {"x": 11, "y": 4, "radius": 14, "border": theme.LINE}),
}


def _faded(color, alpha):
    color = QColor(color)
    color.setAlphaF(alpha)
    return color


class NoServer(QWidget):
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        message = QLabel("No server was found to display information.")
        message.setObjectName("message")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.button = QPushButton("Refresh")
        self.button.setObjectName("primary")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self.refresh_requested)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 40, 0, 40)
        layout.addStretch(1)
        layout.addWidget(message)
        layout.addSpacing(18)
        layout.addWidget(self.button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)


class Gate(QWidget):
    refresh_requested = Signal()

    def __init__(self, content, parent=None):
        super().__init__(parent)
        self.content = content
        self.empty = NoServer()
        self.empty.refresh_requested.connect(self.refresh_requested)
        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)
        self._stack.addWidget(content)
        self._stack.addWidget(self.empty)

    def show_content(self):
        self._stack.setCurrentWidget(self.content)

    def show_empty(self):
        self.content.reset()
        self._stack.setCurrentWidget(self.empty)

    def set_busy(self, busy):
        self.empty.button.setEnabled(not busy)


class StatsPage(QWidget):
    period_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last = None
        self.period = Dropdown([(key, label) for key, _, _, label in PERIODS], "total")
        self.period.changed.connect(self.period_changed)
        self.tiles = {
            "down": Tile("Download", theme.DOWN.name(), "download.svg", theme.DOWN),
            "up": Tile("Upload", theme.UP.name(), "upload.svg", theme.UP),
            "total": Tile("Total", theme.ACCENT.name(), "total.svg"),
            "count": Tile("Clients", theme.ACCENT2.name(), "clients.svg"),
        }
        self.grid = FluidGrid(170, 12, fit=True)
        self.grid.set_items(self.tiles.values())
        self.table = StatsTable()
        self.empty = EmptyBox("")
        self.foot = Text(theme.make_font(12), _faded(theme.TEXT, 0.6))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        top = QHBoxLayout()
        top.addWidget(self.period)
        top.addStretch(1)
        layout.addLayout(top)
        layout.addSpacing(16)
        layout.addWidget(self.grid)
        layout.addSpacing(18)
        layout.addWidget(self.table)
        layout.addWidget(self.empty)
        layout.addSpacing(16)
        layout.addWidget(self.foot)
        layout.addStretch(1)

    def reset(self):
        self._last = None

    def render(self, view):
        if view == self._last:
            return
        self._last = view
        self.tiles["down"].set_value(view.down)
        self.tiles["up"].set_value(view.up)
        self.tiles["total"].set_value(view.total)
        self.tiles["count"].set_value(view.count)
        has_rows = bool(view.rows)
        self.table.set_rows(view.rows)
        self.table.setVisible(has_rows)
        self.empty.setVisible(not has_rows)
        self.empty.set_text(
            "No internet traffic has been recorded yet."
            if view.period == "total"
            else "No internet traffic was recorded for this period."
        )
        self.foot.set_text(view.since)


class PlanCard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._card = None
        self.name = Text(theme.make_font(16, QFont.Weight.Bold))
        self.ip = Text(theme.make_font(12), _faded(theme.TEXT, 0.85), line=18, box=CHIP)
        self.mac = Text(theme.make_font(12, mono=True), _faded(theme.TEXT, 0.85), line=18, box=CHIP)
        self.pill = Text(theme.make_font(12), theme.DOWN, line=18)
        self.bar = Bar()
        self.used = Text(theme.make_font(13))
        self.percent = Text(theme.make_font(13), align=RIGHT)
        self.left = Text(theme.make_font(12), _faded(theme.TEXT, 0.7))
        self.renews = Text(theme.make_font(12), _faded(theme.TEXT, 0.7), align=RIGHT)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        chips.addWidget(self.ip)
        chips.addWidget(self.mac)
        chips.addStretch(1)
        identity = QVBoxLayout()
        identity.setSpacing(0)
        identity.addWidget(self.name)
        identity.addSpacing(15)
        identity.addLayout(chips)
        head = QHBoxLayout()
        head.setSpacing(12)
        head.addLayout(identity, 1)
        head.addWidget(self.pill, 0, Qt.AlignmentFlag.AlignVCenter)
        first = QHBoxLayout()
        first.addWidget(self.used)
        first.addWidget(self.percent)
        second = QHBoxLayout()
        second.addWidget(self.left)
        second.addWidget(self.renews)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(17, 17, 17, 17)
        layout.setSpacing(0)
        layout.addLayout(head)
        layout.addSpacing(14)
        layout.addWidget(self.bar)
        layout.addSpacing(10)
        layout.addLayout(first)
        layout.addSpacing(4)
        layout.addLayout(second)

    def update_card(self, card):
        if card == self._card:
            return
        self._card = card
        self.name.set_text(card.name)
        self.ip.set_text(card.ip)
        self.mac.set_text(card.mac)
        color, box = PILL_TONES[card.state]
        self.pill.set_look(color, box)
        self.pill.set_text(STATES[card.state])
        self.bar.set_value(card.remaining / 100.0, card.tone)
        self.used.set_text(card.used_text)
        self.percent.set_text(card.percent_text)
        self.left.set_text(card.left_text)
        self.renews.set_text(card.renews)
        self.setGraphicsEffect(self._dim() if card.state == "off" else None)
        self.update()

    @staticmethod
    def _dim():
        effect = QGraphicsOpacityEffect()
        effect.setOpacity(0.7)
        return effect

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        border = theme.rgba(229, 72, 77, 0.6) if self._card and self._card.state == "blocked" else theme.LINE
        theme.draw_box(painter, self.rect(), border=border)


class AclPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._last = None
        self._cards = []
        self.tiles = {
            "active": Tile("Active plans", theme.ACCENT.name(), "plans.svg"),
            "blocked": Tile("Blocked", theme.BAD.name(), "blocked.svg"),
            "usage": Tile("Plan usage", theme.DOWN.name(), "usage.svg", theme.DOWN),
        }
        self.grid = FluidGrid(170, 12, fit=True)
        self.grid.set_items(self.tiles.values())
        self.cards = FluidGrid(330, 14)
        self.empty = EmptyBox("No data plans yet.")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.grid)
        layout.addSpacing(18)
        layout.addWidget(self.cards)
        layout.addWidget(self.empty)
        layout.addStretch(1)

    def reset(self):
        self._last = None

    def render(self, view):
        if view == self._last:
            return
        self._last = view
        self.tiles["active"].set_value(view.active)
        self.tiles["blocked"].set_value(view.blocked, theme.BAD if view.blocked_count else None)
        self.tiles["usage"].set_value(view.usage)
        while len(self._cards) < len(view.cards):
            self._cards.append(PlanCard())
        surplus = self._cards[len(view.cards):]
        del self._cards[len(view.cards):]
        for widget, card in zip(self._cards, view.cards):
            widget.update_card(card)
        self.cards.set_items(self._cards)
        for widget in surplus:
            widget.deleteLater()
        self.cards.setVisible(bool(view.cards))
        self.empty.setVisible(not view.cards)


class SettingsPage(QWidget):
    reset_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last = None
        self.address = CopyField("Server Address")
        self.token = CopyField("Token", secret=True)
        self.pin = CopyField("Certificate Pin", secret=True)
        self.reset = QPushButton(RESET_LABEL)
        self.reset.setObjectName("reset")
        self.reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset.clicked.connect(self.reset_requested)
        self.warning = QLabel()
        self.warning.setObjectName("warning")
        self.warning.setTextFormat(Qt.TextFormat.PlainText)
        self.warning.setWordWrap(True)
        self.warning.hide()
        title = Text(theme.make_font(18, QFont.Weight.Bold), line=24)
        title.set_text("Server Connection")
        subtitle = Text(theme.make_font(13), _faded(theme.TEXT, 0.65), line=20)
        subtitle.set_text("Use these details to connect your router to this server.")
        panel = Panel()
        inner = QVBoxLayout(panel)
        inner.setContentsMargins(24, 22, 24, 24)
        inner.setSpacing(0)
        inner.addWidget(title)
        inner.addSpacing(2)
        inner.addWidget(subtitle)
        inner.addSpacing(22)
        inner.addWidget(self.address)
        inner.addSpacing(18)
        inner.addWidget(self.token)
        inner.addSpacing(18)
        inner.addWidget(self.pin)
        inner.addSpacing(20)
        inner.addWidget(self.reset, 0, Qt.AlignmentFlag.AlignLeft)
        inner.addSpacing(6)
        inner.addWidget(self.warning)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(panel)
        layout.addStretch(1)

    def conceal(self):
        self.token.conceal()
        self.pin.conceal()

    def set_busy(self, busy):
        self.reset.setEnabled(not busy)
        self.reset.setText("Resetting..." if busy else RESET_LABEL)

    def render(self, view):
        if view == self._last:
            return
        self._last = view
        self.address.set_value(view.url, "Unavailable")
        self.token.set_value(view.token, view.token_hint)
        self.pin.set_value(view.pin, view.pin_hint)
        if view.error:
            message = "The server could not start: " + view.error
        elif view.blocked:
            message = BLOCKED_NOTICE % view.blocked
        else:
            message = ""
        self.warning.setText(message)
        self.warning.setVisible(bool(message))


class AboutPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        panel = Panel()
        inner = QVBoxLayout(panel)
        inner.setContentsMargins(24, 22, 24, 22)
        inner.setSpacing(0)
        body = QLabel(ABOUT_LINE % html.escape(ABOUT_TEXT).replace("\n", "<br>"))
        body.setObjectName("paragraph")
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setWordWrap(True)
        inner.addWidget(body)
        inner.addSpacing(12)
        inner.addWidget(LinkRow(OFFICIAL_ICON, OFFICIAL_NAME, OFFICIAL_URL), 0, Qt.AlignmentFlag.AlignLeft)
        inner.addSpacing(26)
        self._section(inner, PROJECTS_TITLE, LinkRow(PROJECT_ICON, PROJECT_NAME, PROJECT_URL))
        inner.addSpacing(22)
        contact = QWidget()
        line = QHBoxLayout(contact)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(8)
        line.addWidget(LinkRow(CONTACT_ICON, CONTACT_EMAIL, "mailto:" + CONTACT_EMAIL))
        line.addWidget(CopyButton(CONTACT_EMAIL))
        line.addStretch(1)
        self._section(inner, CONTACT_TITLE, contact)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(panel)
        layout.addStretch(1)

    @staticmethod
    def _section(layout, heading, row):
        title = Text(theme.make_font(16, QFont.Weight.Bold), line=22)
        title.set_text(heading)
        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(row, 0, Qt.AlignmentFlag.AlignLeft)
