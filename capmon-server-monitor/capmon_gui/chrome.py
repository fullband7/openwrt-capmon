import math

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QConicalGradient,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from . import theme
from .widgets import CENTER, LEFT, Logo, Text


NAME = "CapMon Server Monitor"


def start_move(widget, event):
    if event.button() == Qt.MouseButton.LeftButton:
        handle = widget.window().windowHandle()
        if handle is not None:
            handle.startSystemMove()


class Frame(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._backdrop = None
        self._backdrop_key = None

    def _paint_backdrop(self, painter, ratio):
        margin = theme.MARGIN
        painter.setPen(Qt.PenStyle.NoPen)
        base = QRectF(margin, margin + 4, self.width() - 2 * margin, self.height() - 2 * margin)
        steps = max(1, round(margin * ratio))
        layer = QColor.fromRgbF(0.0, 0.0, 0.0, 5 / 255 / ratio)
        painter.setBrush(layer)
        for step in range(steps, 0, -1):
            grow = step / ratio
            painter.drawRoundedRect(
                base.adjusted(-grow, -grow, grow, grow),
                theme.RADIUS + grow,
                theme.RADIUS + grow,
            )
        area = theme.align(
            QRectF(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin), ratio
        )
        painter.setBrush(theme.WINDOW)
        painter.drawRoundedRect(area, theme.RADIUS, theme.RADIUS)
        center = QPointF(area.left() + area.width() * 0.9, area.top() + area.height() * 0.7)
        reach = math.hypot(area.width() * 0.9, area.height() * 0.7)
        glow = theme.logical(QRadialGradient(center, reach))
        glow.setColorAt(0, QColor(40, 125, 205, 51))
        glow.setColorAt(0.7, QColor(40, 125, 205, 0))
        glow.setColorAt(1, QColor(40, 125, 205, 0))
        painter.setBrush(glow)
        painter.drawRoundedRect(area, theme.RADIUS, theme.RADIUS)

    def _backdrop_pixmap(self):
        ratio = self.devicePixelRatioF()
        key = (self.width(), self.height(), ratio)
        if key != self._backdrop_key:
            margin = theme.MARGIN
            clip = QPainterPath()
            clip.addRoundedRect(
                QRectF(margin + 1, margin + 1, self.width() - 2 * margin - 2, self.height() - 2 * margin - 2),
                theme.RADIUS - 1,
                theme.RADIUS - 1,
            )
            self._backdrop = theme.bake(
                self.width(), self.height(), ratio, lambda painter: self._paint_backdrop(painter, ratio), clip
            )
            self._backdrop_key = key
        return self._backdrop

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._backdrop_pixmap())


class Outline(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path, width = theme.crisp(painter, QRectF(self.rect()))
        painter.setPen(QPen(theme.rgba(255, 255, 255, 0.1), width))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(path, theme.RADIUS, theme.RADIUS)


class CaptionButton(QWidget):
    clicked = Signal()

    def __init__(self, kind, parent=None):
        super().__init__(parent)
        self._kind = kind
        self._hover = False
        self._down = False
        self.setFixedSize(40, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._down = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._down = True
            self.update()

    def mouseReleaseEvent(self, event):
        was_down = self._down
        self._down = False
        self.update()
        if was_down and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        closing = self._kind == "close"
        if self._hover:
            if closing:
                fill = theme.rgba(229, 72, 77, 0.7 if self._down else 0.95)
            else:
                fill = theme.rgba(255, 255, 255, 0.2 if self._down else 0.14)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill)
            painter.drawRoundedRect(QRectF(self.rect()), 9, 9)
        pen = QPen(theme.rgba(255, 255, 255, 1.0 if self._hover else 0.8), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        cx = self.width() / 2
        cy = self.height() / 2
        if closing:
            painter.drawLine(QPointF(cx - 4.5, cy - 4.5), QPointF(cx + 4.5, cy + 4.5))
            painter.drawLine(QPointF(cx - 4.5, cy + 4.5), QPointF(cx + 4.5, cy - 4.5))
        else:
            painter.drawLine(QPointF(cx - 5, cy + 1.5), QPointF(cx + 5, cy + 1.5))


class TitleBar(QWidget):
    minimize_requested = Signal()
    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(theme.TITLEBAR)
        minimize = CaptionButton("minimize")
        close = CaptionButton("close")
        minimize.clicked.connect(self.minimize_requested)
        close.clicked.connect(self.close_requested)
        row = QHBoxLayout(self)
        row.setContentsMargins(18, 0, 10, 0)
        row.setSpacing(10)
        row.addStretch(1)
        row.addWidget(minimize)
        row.addSpacing(2)
        row.addWidget(close)

    def mousePressEvent(self, event):
        start_move(self, event)


class StatusBadge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._synced = False
        self._phase = 0.0
        self._font = theme.make_font(14)
        self.setFixedSize(150, 40)
        self._pulse = QVariantAnimation(self)
        self._pulse.setStartValue(0.0)
        self._pulse.setEndValue(1.0)
        self._pulse.setDuration(1800)
        self._pulse.setLoopCount(-1)
        self._pulse.valueChanged.connect(self._tick)

    def synced(self):
        return self._synced

    def set_synced(self, synced):
        if synced == self._synced:
            return
        self._synced = synced
        if synced:
            self._pulse.start()
        else:
            self._pulse.stop()
        self.update()

    def _tick(self, value):
        self._phase = float(value)
        self.update()

    def _flat(self, painter):
        if self._synced:
            fill = theme.rgba(255, 255, 255, 0.08)
            border = theme.rgba(255, 255, 255, 0.16)
        else:
            fill = theme.rgba(229, 72, 77, 0.3)
            border = theme.rgba(229, 72, 77, 0.65)
        theme.draw_panel(painter, self.rect(), 12, fill, border)

    def _dot(self, painter, center):
        pulse = 0.5 + 0.5 * math.sin(self._phase * 2 * math.pi)
        radius = 5 + 6 * pulse
        halo = theme.logical(QRadialGradient(center, radius))
        halo.setColorAt(0, theme.rgba(31, 169, 113, 0.55))
        halo.setColorAt(1, theme.rgba(31, 169, 113, 0.0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(center, radius, radius)
        painter.setBrush(theme.DOWN)
        painter.drawEllipse(center, 4.5, 4.5)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._flat(painter)
        text = "Synced" if self._synced else "Not Synced"
        painter.setFont(self._font)
        metrics = painter.fontMetrics()
        width = metrics.horizontalAdvance(text)
        tint = QColor("#f2f5f8") if self._synced else QColor("#ffe6e7")
        painter.setPen(tint)
        if not self._synced:
            painter.drawText(self.rect(), CENTER, text)
            return
        total = 10 + 12 + width
        left = (self.width() - total) / 2
        self._dot(painter, QPointF(left + 5, self.height() / 2))
        painter.setPen(tint)
        painter.setFont(self._font)
        painter.drawText(
            QRectF(left + 22, 0, width + 2, self.height()), LEFT, text
        )


class Header(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(theme.TITLEBAR + 96)
        self._backdrop = None
        self._backdrop_key = None
        self._logo = Logo(64, self)
        title = Text(theme.make_font(28), theme.TITLE, line=34)
        title.set_text(NAME)
        tagline = QLabel("Monitor the internet data usage of every client on your network")
        tagline.setIndent(0)
        tagline.setMargin(0)
        tagline.setStyleSheet(
            "color:#bfbfbf;font-size:14px;font-weight:600;padding-top:6px;"
            "border-top:1px solid #cccccc;background:transparent"
        )
        column = QVBoxLayout()
        column.setSpacing(4)
        column.addStretch(1)
        column.addWidget(title)
        column.addWidget(tagline, 0, Qt.AlignmentFlag.AlignLeft)
        column.addStretch(1)
        self.badge = StatusBadge()
        row = QHBoxLayout(self)
        row.setContentsMargins(36, theme.TITLEBAR, 32, 5)
        row.setSpacing(18)
        row.addWidget(self._logo)
        row.addLayout(column)
        row.addStretch(1)
        row.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignVCenter)

    def mousePressEvent(self, event):
        start_move(self, event)

    def _paint_backdrop(self, painter):
        gradient = theme.logical(QLinearGradient(0, 0, self.width(), 0))
        gradient.setColorAt(0, QColor("#1a2839"))
        gradient.setColorAt(1, QColor("#253850"))
        shape = QPainterPath()
        shape.addRoundedRect(
            QRectF(0, 0, self.width(), self.height() + theme.RADIUS), theme.RADIUS, theme.RADIUS
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawPath(shape)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillRect(0, self.height() - 5, self.width(), 5, QColor("#182636"))

    def _backdrop_pixmap(self):
        ratio = self.devicePixelRatioF()
        key = (self.width(), self.height(), ratio)
        if key != self._backdrop_key:
            inset = QPainterPath()
            inset.addRoundedRect(
                QRectF(1, 1, self.width() - 2, self.height() + theme.RADIUS),
                theme.RADIUS - 1,
                theme.RADIUS - 1,
            )
            band = QPainterPath()
            band.addRect(QRectF(0, 0, self.width(), self.height() - 5))
            self._backdrop = theme.bake(
                self.width(), self.height(), ratio, self._paint_backdrop, inset.intersected(band)
            )
            self._backdrop_key = key
        return self._backdrop

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._backdrop_pixmap())


class LoadingOverlay(QWidget):
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0.0
        self._dots = 1
        self._leaving = False
        self._backdrop = None
        self._backdrop_key = None
        self._label_font = theme.make_font(15)
        self._spin = QVariantAnimation(self)
        self._spin.setStartValue(0.0)
        self._spin.setEndValue(360.0)
        self._spin.setDuration(1100)
        self._spin.setLoopCount(-1)
        self._spin.valueChanged.connect(self._turn)
        self._spin.start()
        self._ticker = QTimer(self)
        self._ticker.setInterval(420)
        self._ticker.timeout.connect(self._advance)
        self._ticker.start()

    def _turn(self, value):
        self._angle = float(value)
        self.update()

    def _advance(self):
        self._dots = self._dots % 3 + 1
        self.update()

    def mousePressEvent(self, event):
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def finish(self):
        if self._leaving:
            return
        self._leaving = True
        effect = QGraphicsOpacityEffect(self)
        effect.setOpacity(1.0)
        self.setGraphicsEffect(effect)
        fade = QPropertyAnimation(effect, b"opacity", self)
        fade.setDuration(320)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.Type.InOutQuad)
        fade.finished.connect(self._done)
        fade.start()

    def _done(self):
        self._spin.stop()
        self._ticker.stop()
        self.hide()
        self.finished.emit()
        self.deleteLater()

    def _card(self, painter, card):
        gradient = theme.logical(QLinearGradient(0, card.top(), 0, card.bottom()))
        gradient.setColorAt(0, theme.rgba(255, 255, 255, 0.1))
        gradient.setColorAt(1, theme.rgba(255, 255, 255, 0.05))
        theme.draw_panel(painter, card, 24, gradient, theme.rgba(255, 255, 255, 0.16))

    def _spinner(self, painter, center):
        radius = 30
        area = QRectF(center.x() - radius, center.y() - radius, 2 * radius, 2 * radius)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(theme.rgba(255, 255, 255, 0.09), 5))
        painter.drawEllipse(area)
        head = -self._angle
        for width, strength in ((13, 0.16), (5, 1.0)):
            gradient = theme.logical(QConicalGradient(center, head))
            gradient.setColorAt(0, QColor(110, 168, 255, round(255 * strength)))
            gradient.setColorAt(0.45, QColor(79, 124, 255, round(120 * strength)))
            gradient.setColorAt(0.83, QColor(138, 92, 255, 0))
            pen = QPen(gradient, width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(area, round(head * 16), 300 * 16)

    def _paint_backdrop(self, painter):
        bounds = QRectF(0, 0, self.width(), self.height())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(15, 22, 30, 238))
        painter.drawRoundedRect(bounds, theme.RADIUS, theme.RADIUS)
        glow = theme.logical(
            QRadialGradient(bounds.center(), min(bounds.width(), bounds.height()) * 0.55)
        )
        glow.setColorAt(0, theme.rgba(79, 124, 255, 0.16))
        glow.setColorAt(1, theme.rgba(79, 124, 255, 0.0))
        painter.setBrush(glow)
        painter.drawRoundedRect(bounds, theme.RADIUS, theme.RADIUS)
        self._card(painter, self._card_rect())

    def _card_rect(self):
        card = QRectF(0, 0, 260, 214)
        card.moveCenter(QRectF(self.rect()).center())
        return card

    def _backdrop_pixmap(self):
        ratio = self.devicePixelRatioF()
        key = (self.width(), self.height(), ratio)
        if key != self._backdrop_key:
            clip = QPainterPath()
            clip.addRoundedRect(
                QRectF(1, 1, self.width() - 2, self.height() - 2), theme.RADIUS - 1, theme.RADIUS - 1
            )
            self._backdrop = theme.bake(self.width(), self.height(), ratio, self._paint_backdrop, clip)
            self._backdrop_key = key
        return self._backdrop

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPixmap(0, 0, self._backdrop_pixmap())
        card = self._card_rect()
        self._spinner(painter, QPointF(card.center().x(), card.top() + 84))
        painter.setFont(self._label_font)
        painter.setPen(theme.rgba(255, 255, 255, 0.85))
        metrics = painter.fontMetrics()
        base = "Fetching data"
        full = metrics.horizontalAdvance(base + "...")
        left = card.center().x() - full / 2
        baseline = card.bottom() - 40
        painter.drawText(QPointF(left, baseline), base + "." * self._dots)
