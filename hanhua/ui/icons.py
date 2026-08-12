"""不依赖平台字体的线性矢量图标。"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from hanhua.ui.design_system import TOKENS

# 各图标的默认色（未指定 color 时使用）
NAME_COLORS = {
    "home": TOKENS.primary,
    "review": "#69A7FF",
    "translate": TOKENS.accent2,
    "settings": "#F2B84B",
    "folder": TOKENS.primary,
    "scan": TOKENS.primary,
    "tool": TOKENS.primary,
    "shield": TOKENS.primary,
    "check": TOKENS.success,
    "gear": TOKENS.text_secondary,
    "pen": TOKENS.text_secondary,
    "rocket": TOKENS.text_secondary,
    "search": TOKENS.text_secondary,
    "play": TOKENS.text_secondary,
    "alert": TOKENS.warning,
    "database": TOKENS.text_secondary,
}


class LineIcon(QWidget):
    def __init__(self, name: str, size: int = 32, color: str | None = None,
                 parent=None):
        super().__init__(parent)
        self.name = name
        self.color = color or NAME_COLORS.get(name, TOKENS.primary)
        self.setFixedSize(size, size)
        self.setAccessibleName(f"{name} 图标")

    def setColor(self, color: str):
        """运行期改色并重绘（首页任务推荐图标随状态变色）。"""
        self.color = color
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._paint(painter)
        painter.end()

    def _paint(self, painter: QPainter):
        scale = min(self.width(), self.height()) / 32.0
        painter.scale(scale, scale)
        pen = QPen(QColor(self.color), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        getattr(self, f"_paint_{self.name}", self._paint_shield)(painter)

    @classmethod
    def pixmap(cls, name: str, size: int = 18, color: str | None = None) -> QPixmap:
        """把图标渲染为透明底 QPixmap（用于 QIcon / 导航项）。"""
        icon = cls(name, size, color)
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        icon._paint(painter)
        painter.end()
        return pixmap

    # ── 各图标路径（32×32 坐标空间） ──────────────────────

    @staticmethod
    def _paint_home(p: QPainter):
        path = QPainterPath()
        path.moveTo(16, 5)
        path.lineTo(28, 16)
        path.lineTo(24, 16)
        path.lineTo(24, 27)
        path.lineTo(8, 27)
        path.lineTo(8, 16)
        path.lineTo(4, 16)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(13, 27), QPointF(13, 19))
        p.drawLine(QPointF(19, 27), QPointF(19, 19))

    @staticmethod
    def _paint_pen(p: QPainter):
        path = QPainterPath(QPointF(6, 26))
        path.lineTo(9, 18)
        path.lineTo(23, 5)
        path.lineTo(28, 10)
        path.lineTo(14, 23)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(20, 7), QPointF(25, 12))

    @staticmethod
    def _paint_rocket(p: QPainter):
        path = QPainterPath()
        path.moveTo(16, 4)
        path.lineTo(25, 11)
        path.lineTo(25, 17)
        path.lineTo(16, 28)
        path.lineTo(7, 17)
        path.lineTo(7, 11)
        path.closeSubpath()
        p.drawPath(path)
        p.drawEllipse(QRectF(12, 10, 8, 8))
        p.drawLine(16, 22, 16, 28)

    @staticmethod
    def _paint_gear(p: QPainter):
        for angle in (0, 45, 90, 135, 180, 225, 270, 315):
            import math
            rad = math.radians(angle)
            cx = 16 + 10 * math.cos(rad)
            cy = 16 + 10 * math.sin(rad)
            p.drawLine(QPointF(16 + 5 * math.cos(rad), 16 + 5 * math.sin(rad)),
                       QPointF(cx, cy))
        p.drawEllipse(QRectF(9, 9, 14, 14))
        p.drawEllipse(QRectF(13, 13, 6, 6))

    @staticmethod
    def _paint_search(p: QPainter):
        p.drawEllipse(QRectF(6, 6, 15, 15))
        p.drawLine(QPointF(19, 19), QPointF(27, 27))

    @staticmethod
    def _paint_play(p: QPainter):
        path = QPainterPath(QPointF(10, 7))
        path.lineTo(10, 25)
        path.lineTo(26, 16)
        path.closeSubpath()
        p.drawPath(path)

    @staticmethod
    def _paint_alert(p: QPainter):
        path = QPainterPath()
        path.moveTo(16, 5)
        path.lineTo(28, 27)
        path.lineTo(4, 27)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(16, 12), QPointF(16, 19))
        p.drawLine(QPointF(16, 23), QPointF(16, 24))

    @staticmethod
    def _paint_database(p: QPainter):
        p.drawEllipse(QRectF(6, 6, 20, 7))
        p.drawEllipse(QRectF(6, 19, 20, 7))
        p.drawLine(QPointF(6, 9), QPointF(6, 23))
        p.drawLine(QPointF(26, 9), QPointF(26, 23))
        p.drawLine(QPointF(6, 15), QPointF(26, 15))

    @staticmethod
    def _paint_folder(p: QPainter):
        path = QPainterPath()
        path.moveTo(4, 10)
        path.lineTo(12, 10)
        path.lineTo(15, 13)
        path.lineTo(28, 13)
        path.lineTo(26, 25)
        path.lineTo(5, 25)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(5, 10), QPointF(5, 24))

    @staticmethod
    def _paint_scan(p: QPainter):
        p.drawLine(5, 10, 5, 5); p.drawLine(5, 5, 10, 5)
        p.drawLine(22, 5, 27, 5); p.drawLine(27, 5, 27, 10)
        p.drawLine(5, 22, 5, 27); p.drawLine(5, 27, 10, 27)
        p.drawLine(22, 27, 27, 27); p.drawLine(27, 27, 27, 22)
        p.drawLine(8, 16, 24, 16)

    @staticmethod
    def _paint_tool(p: QPainter):
        p.drawEllipse(QRectF(9, 9, 14, 14))
        p.drawEllipse(QRectF(14, 14, 4, 4))
        for start, end in (((16, 4), (16, 9)), ((16, 23), (16, 28)),
                           ((4, 16), (9, 16)), ((23, 16), (28, 16))):
            p.drawLine(*start, *end)

    @staticmethod
    def _paint_translate(p: QPainter):
        p.drawRoundedRect(QRectF(4, 6, 16, 14), 3, 3)
        p.drawLine(8, 11, 16, 11); p.drawLine(12, 9, 12, 17)
        p.drawRoundedRect(QRectF(12, 13, 16, 13), 3, 3)
        p.drawLine(17, 22, 20, 16); p.drawLine(20, 16, 23, 22)

    @staticmethod
    def _paint_shield(p: QPainter):
        path = QPainterPath()
        path.moveTo(16, 4); path.lineTo(26, 8); path.lineTo(25, 17)
        path.cubicTo(24, 23, 20, 26, 16, 28)
        path.cubicTo(12, 26, 8, 23, 7, 17)
        path.lineTo(6, 8); path.closeSubpath()
        p.drawPath(path)

    @staticmethod
    def _paint_check(p: QPainter):
        p.drawEllipse(QRectF(5, 5, 22, 22))
        path = QPainterPath(QPointF(10, 16))
        path.lineTo(14, 20); path.lineTo(23, 11)
        p.drawPath(path)

    @staticmethod
    def _paint_brand(p: QPainter):
        """品牌图形：两个错位方括号围住一个发光节点（提取→翻译→回写）。"""
        p.drawLine(4, 8, 4, 24)
        p.drawLine(4, 24, 13, 24)
        p.drawLine(28, 8, 28, 24)
        p.drawLine(28, 24, 19, 24)
        p.drawLine(4, 8, 13, 8)
        p.drawLine(28, 8, 19, 8)
        p.drawEllipse(QRectF(13, 13, 6, 6))
        for start, end in (((16, 8), (16, 13)), ((16, 19), (16, 24)),
                           ((8, 16), (13, 16)), ((19, 16), (24, 16))):
            p.drawLine(*start, *end)
