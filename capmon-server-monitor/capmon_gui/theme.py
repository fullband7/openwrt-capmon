import math
import random
import sys
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QGradient, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsBlurEffect, QGraphicsPixmapItem, QGraphicsScene


NOISE_SIZE = 256
NOISE_SEED = 20240607


def rgba(red, green, blue, alpha):
    return QColor(red, green, blue, round(alpha * 255))


def snap(value):
    return math.floor(value + 0.5)


def align(rect, ratio):
    box = QRectF(rect)
    return QRectF(
        QPointF(snap(box.left() * ratio) / ratio, snap(box.top() * ratio) / ratio),
        QPointF(snap(box.right() * ratio) / ratio, snap(box.bottom() * ratio) / ratio),
    )


def crisp(painter, rect):
    transform = painter.deviceTransform()
    sx, sy = transform.m11(), transform.m22()
    dx, dy = transform.dx(), transform.dy()
    thick = max(1, snap(min(sx, sy)))
    half = thick / 2
    box = QRectF(rect)
    left = snap(box.left() * sx + dx)
    top = snap(box.top() * sy + dy)
    right = snap(box.right() * sx + dx)
    bottom = snap(box.bottom() * sy + dy)
    path = QRectF(
        QPointF((left + half - dx) / sx, (top + half - dy) / sy),
        QPointF((right - half - dx) / sx, (bottom - half - dy) / sy),
    )
    return path, thick / sx


def hline(painter, left, right, y, color):
    transform = painter.deviceTransform()
    sy, dy = transform.m22(), transform.dy()
    thick = max(1, snap(sy))
    device = snap(y * sy + dy)
    painter.fillRect(QRectF(left, (device - dy) / sy, right - left, thick / sy), color)


def logical(gradient):
    gradient.setCoordinateMode(QGradient.CoordinateMode.LogicalMode)
    return gradient


@lru_cache(maxsize=1)
def _noise_tile():
    count = NOISE_SIZE * NOISE_SIZE
    samples = random.Random(NOISE_SEED).randbytes(count)
    buffer = bytearray(count * 8)
    low = 0 if sys.byteorder == "little" else 1
    for channel in (0, 2, 4):
        buffer[low + channel::8] = samples
    image = QImage(
        bytes(buffer), NOISE_SIZE, NOISE_SIZE, NOISE_SIZE * 8,
        QImage.Format.Format_RGBA64_Premultiplied,
    )
    return image.copy()


def _dither(image, clip, ratio):
    painter = QPainter(image)
    if clip is not None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(ratio, ratio)
        painter.setClipPath(clip)
        painter.resetTransform()
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
    tile = _noise_tile()
    for top in range(0, image.height(), NOISE_SIZE):
        for left in range(0, image.width(), NOISE_SIZE):
            painter.drawImage(left, top, tile)
    painter.end()


def blur(image, radius):
    scene = QGraphicsScene()
    item = QGraphicsPixmapItem(QPixmap.fromImage(image))
    effect = QGraphicsBlurEffect()
    effect.setBlurRadius(radius)
    effect.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
    item.setGraphicsEffect(effect)
    scene.addItem(item)
    result = QImage(image.size(), QImage.Format.Format_ARGB32_Premultiplied)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    bounds = QRectF(result.rect())
    scene.render(painter, bounds, bounds)
    painter.end()
    return result


def bake(width, height, ratio, paint, clip=None):
    size = QSize(max(1, round(width * ratio)), max(1, round(height * ratio)))
    image = QImage(size, QImage.Format.Format_RGBA64_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(ratio, ratio)
    paint(painter)
    painter.end()
    _dither(image, clip, ratio)
    result = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    result.setDevicePixelRatio(ratio)
    return QPixmap.fromImage(result)


WINDOW = QColor("#16202a")
TEXT = QColor("#cccccc")
TITLE = QColor("#bfbfbf")
LINE = rgba(127, 127, 127, 0.28)
SOFT = rgba(127, 127, 127, 0.09)
DOWN = QColor("#1fa971")
UP = QColor("#f0a020")
BAD = QColor("#e5484d")
ACCENT = QColor("#4f7cff")
ACCENT2 = QColor("#8a5cff")
ROUTER = QColor("#4da1c0")
OFFLINE = QColor("#8b8b8b")

WIDTH = 1120
HEIGHT = 780
MARGIN = 14
RADIUS = 16
TITLEBAR = 36

FAMILIES = ["Helvetica Neue", "Helvetica", "Arial", "Segoe UI"]
MONO = ["Consolas", "Menlo", "DejaVu Sans Mono", "Courier New"]

STYLE = """
QToolTip{background:#2b3642;color:#cccccc;border:1px solid #26313c;padding:4px 8px}
QScrollArea{background:transparent;border:0}
QScrollBar:vertical{background:transparent;width:12px;margin:0}
QScrollBar::handle:vertical{background:rgba(255,255,255,46);border-radius:4px;min-height:32px;margin:2px}
QScrollBar::handle:vertical:hover{background:rgba(255,255,255,80)}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0}
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical{background:transparent}
QFrame#tabbar{background:rgba(255,255,255,8);border-radius:18px}
QPushButton#tab{background:rgba(129,139,152,31);color:#cccccc;border:0;border-radius:12px;
padding:0 13px;min-height:35px;font-size:16px;font-weight:600}
QPushButton#tab:hover{background:rgba(129,139,152,56)}
QPushButton#tab:checked{background:#b35900;color:#ffffff}
QPushButton#primary{background:#00664c;color:#ffffff;border:0;border-radius:14px;
min-height:50px;padding:0 24px;font-size:15px;font-weight:600}
QPushButton#primary:hover{background:#0a7a5c}
QPushButton#primary:disabled{background:rgba(0,102,76,128)}
QLabel#message{color:rgba(204,204,204,166);font-size:18px;font-weight:600}
QLabel#dialogtext{color:#cccccc;font-size:16px;font-weight:600}
QPushButton#choice{background:rgba(129,139,152,40);color:#cccccc;border:0;border-radius:12px;
padding:0 24px;min-height:38px;font-size:15px;font-weight:600}
QPushButton#choice:hover{background:rgba(129,139,152,70)}
QPushButton#choice:focus{border:1px solid rgba(204,204,204,120)}
QPushButton#danger{background:#c23b40;color:#ffffff;border:0;border-radius:12px;
padding:0 24px;min-height:38px;font-size:15px;font-weight:600}
QPushButton#danger:hover{background:#d4474c}
QPushButton#danger:focus{border:1px solid rgba(255,255,255,140)}
QPushButton#reset{background:rgba(229,72,77,26);color:#ff8f93;border:1px solid rgba(229,72,77,115);
border-radius:12px;padding:0 20px;min-height:38px;font-size:14px;font-weight:600}
QPushButton#reset:hover{background:rgba(229,72,77,56)}
QPushButton#reset:disabled{color:rgba(255,143,147,110);border-color:rgba(229,72,77,60)}
QLabel#note{color:rgba(204,204,204,166);font-size:13px;font-weight:600}
QLabel#warning{color:#e5484d;font-size:13px;font-weight:600}
QLabel#paragraph{color:rgba(204,204,204,230);font-size:17px;font-weight:600}
"""


def make_font(pixels, weight=QFont.Weight.DemiBold, spacing=0.0, mono=False):
    font = QFont()
    font.setFamilies(MONO if mono else FAMILIES)
    font.setPixelSize(pixels)
    font.setWeight(weight)
    if spacing:
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    return font


def draw_box(painter, rect, radius=14, fill=SOFT, border=LINE, dashed=False):
    path, width = crisp(painter, rect)
    pen = QPen(border, width)
    if dashed:
        pen.setStyle(Qt.PenStyle.DashLine)
    painter.setPen(pen)
    painter.setBrush(fill)
    painter.drawRoundedRect(path, radius, radius)


def draw_panel(painter, rect, radius, fill, border):
    path, width = crisp(painter, rect)
    half = width / 2
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(fill)
    painter.drawRoundedRect(path.adjusted(half, half, -half, -half), radius - width, radius - width)
    painter.setPen(QPen(border, width))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(path, radius - half, radius - half)
