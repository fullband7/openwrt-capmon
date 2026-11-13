import math
import re
import secrets
import time
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QGuiApplication,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .hardening import copy_secret

ASSETS = Path(__file__).resolve().parent / "assets"
LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
CENTER = Qt.AlignmentFlag.AlignCenter


RE_INK = re.compile(r"#000(?:000)?(?![0-9a-fA-F])|\bcurrentColor\b|\bblack\b")
RE_ROOT = re.compile(r"<svg\b")


@lru_cache(maxsize=64)
def _svg(path, color):
    try:
        source = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        source = ""
    if color and source:
        recolored = RE_INK.sub(color, source)
        if recolored == source and "fill" not in source and "stroke" not in source:
            recolored = RE_ROOT.sub('<svg fill="%s"' % color, source, count=1)
        source = recolored
    renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
    renderer.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
    return renderer


def draw_icon(painter, name, color, rect):
    _svg(str(ASSETS / "icons" / name), color).render(painter, QRectF(rect))


def logo_pixmap(size, ratio=1.0):
    pixmap = QPixmap(round(size * ratio), round(size * ratio))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _svg(str(ASSETS / "logo.svg"), "").render(painter)
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


class Logo(QWidget):
    def __init__(self, size, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        _svg(str(ASSETS / "logo.svg"), "").render(painter, QRectF(self.rect()))


class Text(QWidget):
    def __init__(self, font, color=theme.TEXT, align=LEFT, line=18, box=None, parent=None):
        super().__init__(parent)
        self._text = ""
        self._font = font
        self._color = QColor(color)
        self._align = align
        self._line = line
        self._box = box
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def text(self):
        return self._text

    def set_text(self, text):
        if text != self._text:
            self._text = text
            self.updateGeometry()
            self.update()

    def set_look(self, color, box=None):
        color = QColor(color)
        if color != self._color or box != self._box:
            self._color = color
            self._box = box
            self.update()

    def _pad(self):
        return (0, 0) if self._box is None else (self._box["x"] + 1, self._box["y"] + 1)

    def sizeHint(self):
        px, py = self._pad()
        advance = math.ceil(QFontMetricsF(self._font).horizontalAdvance(self._text))
        return QSize(advance + 2 * px, self._line + 2 * py)

    def minimumSizeHint(self):
        return QSize(0, self.sizeHint().height())

    def _metrics(self):
        return QFontMetricsF(self._font)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        px, _ = self._pad()
        area = self.rect()
        if self._box is not None:
            theme.draw_box(
                painter, area, self._box.get("radius", 12),
                self._box.get("fill", Qt.GlobalColor.transparent), self._box["border"],
            )
        area = area.adjusted(px, 0, -px, 0)
        painter.setFont(self._font)
        painter.setPen(self._color)
        painter.drawText(
            area, self._align, self._metrics().elidedText(self._text, Qt.TextElideMode.ElideRight, area.width())
        )


class Bar(QWidget):
    TONES = {
        "ok": (QColor("#00664c"), QColor("#00664c")),
        "warn": (QColor("#ffcc00"), QColor("#ffd60a")),
        "over": (QColor("#ff3b30"), QColor("#ff453a")),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fraction = 0.0
        self._tone = "ok"
        self.setFixedHeight(12)

    def set_value(self, fraction, tone):
        fraction = max(0.0, min(1.0, fraction))
        if fraction != self._fraction or tone != self._tone:
            self._fraction = fraction
            self._tone = tone
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        area = QRectF(self.rect())
        painter.setBrush(theme.LINE)
        painter.drawRoundedRect(area, 6, 6)
        width = area.width() * self._fraction
        if width <= 0:
            return
        first, second = self.TONES[self._tone]
        gradient = theme.logical(QLinearGradient(0, 0, width, 0))
        gradient.setColorAt(0, first)
        gradient.setColorAt(1, second)
        painter.setBrush(gradient)
        painter.drawRoundedRect(QRectF(0, 0, width, area.height()), 6, 6)


class Tile(QWidget):
    def __init__(self, label, color, icon, value_color=None, parent=None):
        super().__init__(parent)
        self._label = label.upper()
        self._value = ""
        self._color = color
        self._icon = icon
        self._value_color = QColor(value_color) if value_color else None
        self._label_font = theme.make_font(12, spacing=0.6)
        self._value_font = theme.make_font(26, weight=QFont.Weight.Bold)
        self.setFixedHeight(85)

    def set_value(self, text, color=None):
        color = QColor(color) if color else self._value_color
        if text != self._value or color != self._value_color:
            self._value = text
            self._value_color = color
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme.draw_box(painter, self.rect())
        width = self.width()
        painter.setOpacity(0.5)
        draw_icon(painter, self._icon, self._color, QRectF(width - 75, (self.height() - 56) // 2, 56, 56))
        painter.setOpacity(1)
        painter.setFont(self._label_font)
        label = QColor(theme.TEXT)
        label.setAlphaF(0.65)
        painter.setPen(label)
        painter.drawText(QRect(17, 15, width - 34, 18), LEFT, self._label)
        painter.setFont(self._value_font)
        painter.setPen(self._value_color or theme.TEXT)
        elided = painter.fontMetrics().elidedText(self._value, Qt.TextElideMode.ElideRight, width - 34)
        painter.drawText(QRect(17, 37, width - 34, 33), LEFT, elided)


class FluidGrid(QWidget):
    def __init__(self, min_width, gap, fit=False, parent=None):
        super().__init__(parent)
        self._min = min_width
        self._fit = fit
        self._items = []
        self._cols = 0
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(gap)
        self._gap = gap

    def set_items(self, items):
        for item in self._items:
            self._grid.removeWidget(item)
            item.hide()
        self._items = list(items)
        self._place(force=True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place()

    def _place(self, force=False):
        count = max(1, (self.width() + self._gap) // (self._min + self._gap))
        if self._fit:
            count = min(count, max(1, len(self._items)))
        if count == self._cols and not force:
            return
        for item in self._items:
            self._grid.removeWidget(item)
        for column in range(max(self._cols, count)):
            self._grid.setColumnStretch(column, 1 if column < count else 0)
        self._cols = count
        for index, item in enumerate(self._items):
            self._grid.addWidget(item, index // count, index % count)
            item.show()
        self._grid.setRowStretch(len(self._items) // count + 1, 1)


class EmptyBox(QWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._text = text
        self._font = theme.make_font(16)
        self.setFixedHeight(110)

    def set_text(self, text):
        if text != self._text:
            self._text = text
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme.draw_box(painter, self.rect(), fill=Qt.GlobalColor.transparent, dashed=True)
        painter.setFont(self._font)
        color = QColor(theme.TEXT)
        color.setAlphaF(0.65)
        painter.setPen(color)
        painter.drawText(self.rect(), CENTER, self._text)


class StatsTable(QWidget):
    FR = (2.0, 1.3, 1.5, 1.0, 1.0, 1.0)
    HEADERS = ("CLIENT", "IP ADDRESS", "MAC ADDRESS", "DOWNLOAD", "UPLOAD", "TOTAL")
    HEAD = 42
    ROW = 45

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows = ()
        self._head_font = theme.make_font(12, spacing=0.6)
        self._body = theme.make_font(13, weight=QFont.Weight.Medium)
        self._bold = theme.make_font(13, weight=QFont.Weight.Bold)
        self._mono = theme.make_font(13, mono=True)
        self.setMouseTracking(True)
        self.setFixedHeight(2 + self.HEAD)

    def set_rows(self, rows):
        if rows != self._rows:
            self._rows = rows
            self.setFixedHeight(2 + self.HEAD + self.ROW * len(rows))
            self.update()

    def _columns(self):
        inner = self.width() - 2 - 32
        free = max(0, inner - 12 * (len(self.FR) - 1))
        unit = free / sum(self.FR)
        x = 17.0
        spans = []
        for fraction in self.FR:
            spans.append((int(x), int(fraction * unit)))
            x += fraction * unit + 12
        return spans

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            index = (event.pos().y() - 1 - self.HEAD) // self.ROW
            first = self._columns()[0]
            if 0 <= index < len(self._rows) and event.pos().x() < first[0] + first[1]:
                QToolTip.showText(event.globalPos(), self._rows[index].tip, self)
            else:
                QToolTip.hideText()
            return True
        return super().event(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = self.rect()
        outline, stroke = theme.crisp(painter, QRectF(area))
        clip = QPainterPath()
        clip.addRoundedRect(outline, 14, 14)
        painter.save()
        painter.setClipPath(clip)
        painter.fillRect(area, theme.SOFT)
        spans = self._columns()
        muted = QColor(theme.TEXT)
        muted.setAlphaF(0.65)
        painter.setFont(self._head_font)
        painter.setPen(muted)
        for (x, width), title in zip(spans, self.HEADERS):
            painter.drawText(QRect(x, 1, width, self.HEAD), LEFT, title)
        first = max(0, (event.rect().top() - 1 - self.HEAD) // self.ROW)
        last = min(len(self._rows), (event.rect().bottom() - 1 - self.HEAD) // self.ROW + 1)
        for index in range(first, last):
            self._paint_row(painter, spans, index, 1 + self.HEAD + index * self.ROW)
        painter.restore()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(theme.LINE, stroke))
        painter.drawRoundedRect(outline, 14, 14)

    def _paint_row(self, painter, spans, index, top):
        row = self._rows[index]
        theme.hline(painter, 0, self.width(), top, theme.LINE)
        box = QRect(0, top + 1, 0, self.ROW - 1)
        x, width = spans[0]
        color = theme.OFFLINE
        if row.online:
            color = theme.ROUTER if row.router else theme.DOWN
            ring = QColor(color)
            ring.setAlphaF(0.2 if not row.router else 0.25)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(ring)
            painter.drawEllipse(QPoint(x + 8, top + 23), 8, 8)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(QPoint(x + 8, top + 23), 5, 5)
        values = (
            (row.name, self._bold, theme.TEXT, x + 21, width - 21),
            (row.ip, self._body, theme.TEXT, spans[1][0], spans[1][1]),
            (row.mac, self._mono, theme.TEXT, spans[2][0], spans[2][1]),
            (row.down, self._bold, theme.DOWN, spans[3][0], spans[3][1]),
            (row.up, self._bold, theme.UP, spans[4][0], spans[4][1]),
            (row.total, self._bold, theme.TEXT, spans[5][0], spans[5][1]),
        )
        for text, font, tint, left, size in values:
            painter.setFont(font)
            painter.setPen(tint)
            shown = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, max(0, size))
            painter.drawText(QRect(left, box.top(), max(0, size), box.height()), LEFT, shown)


class DropdownList(QWidget):
    chosen = Signal(object)
    ITEM = 36
    GAP = 10
    PAD = 6

    def __init__(self, owner, items, value):
        flags = (
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        super().__init__(owner, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self._items = items
        self._value = value
        self._hover = next((i for i, item in enumerate(items) if item[0] == value), 0)
        self._offset = 0
        self._font = theme.make_font(14)
        self._bold = theme.make_font(14)
        full = 2 + 2 * self.PAD + len(items) * self.ITEM + (len(items) - 1) * self.GAP
        self.resize(owner.width(), min(full, 320))
        self._full = full
        self._place(owner)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(150)
        self._fade.setStartValue(0.0)
        self._fade.setEndValue(1.0)

    def _place(self, owner):
        below = owner.mapToGlobal(QPoint(0, owner.height() + 6))
        screen = owner.screen().availableGeometry()
        if below.y() + self.height() > screen.bottom():
            below = owner.mapToGlobal(QPoint(0, -self.height() - 6))
        self.move(below)

    def showEvent(self, event):
        super().showEvent(event)
        self._fade.start()

    def _row(self, index):
        return 1 + self.PAD + index * (self.ITEM + self.GAP) - self._offset

    def _at(self, y):
        for index in range(len(self._items)):
            top = self._row(index)
            if top <= y < top + self.ITEM:
                return index
        return -1

    def wheelEvent(self, event):
        limit = max(0, self._full - self.height())
        self._offset = max(0, min(limit, self._offset - event.angleDelta().y() // 3))
        self.update()

    def mouseMoveEvent(self, event):
        index = self._at(event.position().y())
        if index >= 0 and index != self._hover:
            self._hover = index
            self.update()

    def mouseReleaseEvent(self, event):
        index = self._at(event.position().y())
        if index >= 0:
            self.chosen.emit(self._items[index][0])
            self.close()

    def keyPressEvent(self, event):
        key = event.key()
        count = len(self._items)
        if key == Qt.Key.Key_Down:
            self._hover = (self._hover + 1) % count
        elif key == Qt.Key.Key_Up:
            self._hover = (self._hover - 1) % count
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.chosen.emit(self._items[self._hover][0])
            self.close()
            return
        elif key == Qt.Key.Key_Escape:
            self.close()
            return
        top = self._row(self._hover)
        if top < 0:
            self._offset += top - 1 - self.PAD
        elif top + self.ITEM > self.height():
            self._offset += top + self.ITEM - self.height() + 1 + self.PAD
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme.draw_box(painter, self.rect(), 10, QColor(24, 31, 43, 248), theme.rgba(255, 255, 255, 0.18))
        painter.setClipRect(self.rect().adjusted(1, 1, -1, -1))
        painter.setFont(self._font)
        for index, (value, label) in enumerate(self._items):
            box = QRectF(1 + self.PAD, self._row(index), self.width() - 2 - 2 * self.PAD, self.ITEM)
            if box.bottom() < 0 or box.top() > self.height():
                continue
            if value == self._value:
                gradient = theme.logical(QLinearGradient(box.left(), 0, box.right(), 0))
                gradient.setColorAt(0, QColor("#004680"))
                gradient.setColorAt(1, QColor("#4484ba"))
                painter.setBrush(gradient)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(box, 10, 10)
            elif index == self._hover:
                painter.setBrush(theme.rgba(255, 255, 255, 0.14))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRoundedRect(box, 10, 10)
            painter.setPen(QColor("#eef1f7"))
            painter.drawText(box.adjusted(12, 0, -12, 0), LEFT, label)


class Dropdown(QWidget):
    changed = Signal(object)

    def __init__(self, items, value, width=240, height=50, parent=None):
        super().__init__(parent)
        self._items = list(items)
        self._value = value
        self._closed = 0.0
        self._font = theme.make_font(13)
        self.setFixedHeight(height)
        self.setMaximumWidth(width)
        self.setMinimumWidth(min(width, 160))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def value(self):
        return self._value

    def set_items(self, items, value):
        items = list(items)
        if items != self._items or value != self._value:
            self._items = items
            self._value = value
            self.update()

    def _label(self):
        return next((label for value, label in self._items if value == self._value), "")

    def _open(self):
        if time.monotonic() - self._closed < 0.2 or not self._items:
            return
        popup = DropdownList(self, self._items, self._value)
        popup.chosen.connect(self._choose)
        popup.destroyed.connect(self._mark_closed)
        popup.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        popup.show()

    def _mark_closed(self):
        self._closed = time.monotonic()

    def _choose(self, value):
        if value != self._value:
            self._value = value
            self.update()
            self.changed.emit(value)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._open()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_Return, Qt.Key.Key_Space):
            self._open()
        else:
            super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme.draw_box(painter, self.rect(), 12)
        painter.setFont(self._font)
        painter.setPen(theme.TEXT)
        area = self.rect().adjusted(15, 0, -38, 0)
        shown = painter.fontMetrics().elidedText(self._label(), Qt.TextElideMode.ElideRight, area.width())
        painter.drawText(area, LEFT, shown)
        pen = QPen(theme.TEXT, 2)
        pen.setCapStyle(Qt.PenCapStyle.SquareCap)
        painter.setPen(pen)
        painter.setOpacity(0.7)
        cx = self.width() - 24
        cy = self.height() / 2 - 2
        painter.drawPolyline([QPoint(cx - 5, int(cy)), QPoint(cx, int(cy) + 5), QPoint(cx + 5, int(cy))])


class CopyButton(QWidget):
    SIZE = 34
    RESET_MS = 1500

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._text = text
        self._hover = False
        self._copied = False
        self._reset = QTimer(self)
        self._reset.setSingleShot(True)
        self._reset.setInterval(self.RESET_MS)
        self._reset.timeout.connect(self._clear)
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Copy")

    def _clear(self):
        self._copied = False
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            QGuiApplication.clipboard().setText(self._text)
            self._copied = True
            self._reset.start()
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._hover:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(theme.rgba(255, 255, 255, 0.12))
            painter.drawRoundedRect(QRectF(self.rect()), 8, 8)
        icon, color = ("check.svg", theme.DOWN.name()) if self._copied else ("copy.svg", theme.TEXT.name())
        painter.setOpacity(1.0 if self._copied or self._hover else 0.75)
        center = QRectF(self.rect()).center()
        draw_icon(painter, icon, color, QRectF(center.x() - 7.5, center.y() - 7.5, 16, 16))


class LinkRow(QWidget):
    ICON = 28
    HEIGHT = 44
    PAD = 0
    GAP = 14
    MAX_TEXT = 860

    def __init__(self, icon, text, url, parent=None):
        super().__init__(parent)
        self._icon = icon
        self._text = text
        self._url = url
        self._hover = False
        self._font = theme.make_font(15, weight=QFont.Weight.DemiBold)
        advance = math.ceil(QFontMetricsF(self._font).horizontalAdvance(text))
        self._text_width = min(advance, self.MAX_TEXT)
        self.setFixedSize(self.PAD * 2 + self.ICON + self.GAP + self._text_width, self.HEIGHT)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _target(self):
        link = QUrl(self._url)
        scheme = link.scheme()
        if scheme in ("http", "https") and link.host():
            return link
        if scheme == "mailto" and link.path() and not link.hasQuery():
            return link
        return None

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        target = self._target()
        if event.button() == Qt.MouseButton.LeftButton and target is not None:
            QDesktopServices.openUrl(target)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        top = (self.height() - self.ICON) / 2
        draw_icon(painter, self._icon, theme.TEXT.name(), QRectF(self.PAD, top, self.ICON, self.ICON))
        font = QFont(self._font)
        font.setUnderline(self._hover)
        painter.setFont(font)
        painter.setPen(theme.ACCENT.lighter(160 if self._hover else 135))
        area = QRect(self.PAD + self.ICON + self.GAP, 0, self._text_width, self.height())
        painter.drawText(
            area, LEFT, painter.fontMetrics().elidedText(self._text, Qt.TextElideMode.ElideRight, area.width())
        )


class ConfirmDialog(QDialog):
    def __init__(self, message, detail="", parent=None):
        super().__init__(parent, Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setFixedWidth(460)
        body = QLabel(message)
        body.setObjectName("dialogtext")
        body.setTextFormat(Qt.TextFormat.PlainText)
        body.setWordWrap(True)
        no = QPushButton("No")
        no.setObjectName("choice")
        yes = QPushButton("Yes")
        yes.setObjectName("danger")
        for button in (no, yes):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAutoDefault(False)
        no.setDefault(True)
        no.clicked.connect(self.reject)
        yes.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch(1)
        buttons.addWidget(no)
        buttons.addWidget(yes)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(0)
        layout.addWidget(body)
        if detail:
            note = QLabel(detail)
            note.setObjectName("note")
            note.setTextFormat(Qt.TextFormat.PlainText)
            note.setWordWrap(True)
            layout.addSpacing(8)
            layout.addWidget(note)
        layout.addSpacing(22)
        layout.addLayout(buttons)
        no.setFocus()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme.draw_panel(painter, self.rect(), theme.RADIUS, QColor("#1a2632"), theme.LINE)

    def showEvent(self, event):
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is not None:
            center = parent.frameGeometry().center()
            self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)


class Panel(QWidget):
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme.draw_box(painter, self.rect())


class CopyField(QWidget):
    TOP = 24
    BOX = 46
    BUTTON = 34
    GAP = 2
    REVEAL_MS = 30000
    BLUR_RADIUS = 7
    BLUR_PAD = 3
    ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz0123456789"
    MAX_DECOY = 64

    def __init__(self, label, secret=False, parent=None):
        super().__init__(parent)
        self._label = label.upper()
        self._secret = secret
        self._value = ""
        self._hint = ""
        self._hover = ""
        self._copied = False
        self._revealed = False
        self._decoy = ""
        self._veil = None
        self._veil_key = None
        self._label_font = theme.make_font(12, spacing=0.6)
        self._value_font = theme.make_font(14, weight=QFont.Weight.Medium, mono=True)
        self._reset = QTimer(self)
        self._reset.setSingleShot(True)
        self._reset.setInterval(1500)
        self._reset.timeout.connect(self._clear_copied)
        self._relock = QTimer(self)
        self._relock.setSingleShot(True)
        self._relock.setInterval(self.REVEAL_MS)
        self._relock.timeout.connect(self.conceal)
        self.setFixedHeight(self.TOP + self.BOX)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_value(self, value, hint):
        if value != self._value or hint != self._hint:
            self._value = value
            self._hint = hint
            self._revealed = False
            self._relock.stop()
            self._decoy = self._make_decoy()
            self._veil_key = None
            self._sync_cursor()
            self.update()

    def masked(self):
        return self._secret and bool(self._value) and not self._revealed

    def reveal(self):
        if self._secret and self._value:
            self._revealed = True
            self._relock.start()
            self.update()

    def conceal(self):
        self._relock.stop()
        if self._revealed:
            self._revealed = False
            self.update()

    def _make_decoy(self):
        size = min(len(self._value), self.MAX_DECOY)
        return "".join(secrets.choice(self.ALPHABET) for _ in range(size))

    def _buttons(self):
        top = self.TOP + (self.BOX - self.BUTTON) // 2
        copy = QRect(self.width() - self.BUTTON - 6, top, self.BUTTON, self.BUTTON)
        found = {"copy": copy}
        if self._secret:
            found["eye"] = QRect(copy.left() - self.GAP - self.BUTTON, top, self.BUTTON, self.BUTTON)
        return found

    def _target(self, point):
        if not self._value:
            return ""
        for name, rect in self._buttons().items():
            if rect.contains(point):
                return name
        return ""

    def _sync_cursor(self):
        self.setCursor(Qt.CursorShape.PointingHandCursor if self._hover else Qt.CursorShape.ArrowCursor)

    def _clear_copied(self):
        self._copied = False
        self.update()

    def _tip(self, target):
        if target == "copy":
            return "Copy"
        if target == "eye":
            return "Hide" if self._revealed else "Show"
        return ""

    def event(self, event):
        if event.type() == QEvent.Type.ToolTip:
            tip = self._tip(self._target(event.pos()))
            if tip:
                QToolTip.showText(event.globalPos(), tip, self)
            else:
                QToolTip.hideText()
            return True
        return super().event(event)

    def hideEvent(self, event):
        self.conceal()
        super().hideEvent(event)

    def mouseMoveEvent(self, event):
        hover = self._target(event.position().toPoint())
        if hover != self._hover:
            self._hover = hover
            self._sync_cursor()
            self.update()

    def leaveEvent(self, event):
        if self._hover:
            self._hover = ""
            self._sync_cursor()
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        target = self._target(event.position().toPoint())
        if target == "eye":
            if self._revealed:
                self.conceal()
            else:
                self.reveal()
        elif target == "copy":
            self._copy()

    def _copy(self):
        if self._secret:
            copy_secret(self._value)
            self.conceal()
        else:
            QGuiApplication.clipboard().setText(self._value)
        self._copied = True
        self._reset.start()
        self.update()

    def _veil_pixmap(self, size, ratio):
        key = (size.width(), size.height(), ratio, self._decoy)
        if key != self._veil_key:
            pad = self.BLUR_RADIUS * self.BLUR_PAD
            image = QImage(
                round((size.width() + 2 * pad) * ratio), round((size.height() + 2 * pad) * ratio),
                QImage.Format.Format_ARGB32_Premultiplied,
            )
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
            painter.scale(ratio, ratio)
            painter.setFont(self._value_font)
            painter.setPen(theme.TEXT)
            painter.drawText(QRect(pad, pad, size.width(), size.height()), LEFT, self._decoy)
            painter.end()
            blurred = theme.blur(image, self.BLUR_RADIUS * ratio)
            blurred.setDevicePixelRatio(ratio)
            self._veil = QPixmap.fromImage(blurred)
            self._veil_key = key
        return self._veil

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(self._label_font)
        label = QColor(theme.TEXT)
        label.setAlphaF(0.65)
        painter.setPen(label)
        painter.drawText(QRect(2, 0, self.width() - 4, 18), LEFT, self._label)
        box = QRect(0, self.TOP, self.width(), self.BOX)
        theme.draw_box(painter, box, 12)
        buttons = self._buttons()
        right = min(rect.left() for rect in buttons.values())
        area = QRect(15, self.TOP, right - 15 - 8, self.BOX)
        if self.masked():
            veil = self._veil_pixmap(area.size(), self.devicePixelRatioF())
            pad = self.BLUR_RADIUS * self.BLUR_PAD
            painter.save()
            painter.setClipRect(QRect(4, self.TOP + 3, right - 8, self.BOX - 6))
            painter.drawPixmap(area.topLeft() - QPoint(pad, pad), veil)
            painter.restore()
        else:
            painter.setFont(self._value_font)
            tint = QColor(theme.TEXT)
            tint.setAlphaF(1.0 if self._value else 0.45)
            painter.setPen(tint)
            shown = self._value or self._hint
            painter.drawText(
                area, LEFT, painter.fontMetrics().elidedText(shown, Qt.TextElideMode.ElideRight, area.width())
            )
        for name, rect in buttons.items():
            hot = self._hover == name
            if hot:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(theme.rgba(255, 255, 255, 0.12))
                painter.drawRoundedRect(QRectF(rect), 8, 8)
            if name == "copy":
                icon, color = ("check.svg", theme.DOWN.name()) if self._copied else ("copy.svg", theme.TEXT.name())
                strong = self._copied or hot
            else:
                icon, color = ("eye-off.svg" if self._revealed else "eye.svg"), theme.TEXT.name()
                strong = hot or self._revealed
            painter.setOpacity(1.0 if strong else 0.75 if self._value else 0.25)
            draw_icon(painter, icon, color, QRectF(rect.center().x() - 7.5, rect.center().y() - 7.5, 16, 16))
            painter.setOpacity(1.0)
