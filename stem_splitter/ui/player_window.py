from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPainter, QColor, QPen


_DRAG_NONE = 0
_DRAG_PLAYHEAD = 1
_DRAG_LOOP_A = 2
_DRAG_LOOP_B = 3
_HIT_RADIUS = 8


class ScrubberWidget(QWidget):
    seek_requested = pyqtSignal(float)
    loop_start_changed = pyqtSignal(float)
    loop_end_changed = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(32)
        self._position: float = 0.0
        self._loop_start: float = 0.0
        self._loop_end: float = 1.0
        self._loop_enabled: bool = False
        self._drag: int = _DRAG_NONE

    def set_position(self, fraction: float) -> None:
        self._position = fraction
        self.update()

    def set_loop_start(self, fraction: float) -> None:
        self._loop_start = fraction
        self.update()

    def set_loop_end(self, fraction: float) -> None:
        self._loop_end = fraction
        self.update()

    def set_loop_enabled(self, enabled: bool) -> None:
        self._loop_enabled = enabled
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mid_y = h // 2
        track_h = 4

        # Grey track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#333333'))
        painter.drawRoundedRect(0, mid_y - track_h // 2, w, track_h, 2, 2)

        # Blue played region
        played_x = int(self._position * w)
        painter.setBrush(QColor('#7c83f5'))
        painter.drawRoundedRect(0, mid_y - track_h // 2, played_x, track_h, 2, 2)

        if self._loop_enabled:
            # Orange loop region
            lx = int(self._loop_start * w)
            lw = int((self._loop_end - self._loop_start) * w)
            loop_color = QColor('#f39c12')
            loop_color.setAlpha(80)
            painter.setBrush(loop_color)
            painter.drawRect(lx, mid_y - track_h // 2, lw, track_h)

            # A marker
            painter.setPen(QPen(QColor('#f39c12'), 2))
            painter.setBrush(QColor('#f39c12'))
            painter.drawLine(lx, mid_y - 10, lx, mid_y + 10)
            painter.setPen(QColor('#f39c12'))
            painter.drawText(lx + 3, mid_y - 8, 'A')

            # B marker
            bx = int(self._loop_end * w)
            painter.setPen(QPen(QColor('#f39c12'), 2))
            painter.drawLine(bx, mid_y - 10, bx, mid_y + 10)
            painter.setPen(QColor('#f39c12'))
            painter.drawText(bx + 3, mid_y - 8, 'B')

        # White playhead
        px = int(self._position * w)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#ffffff'))
        painter.drawEllipse(px - 6, mid_y - 6, 12, 12)

    def mousePressEvent(self, event):
        x = event.position().x()
        w = self.width()
        fraction = max(0.0, min(1.0, x / w))

        px = int(self._position * w)
        ax = int(self._loop_start * w)
        bx = int(self._loop_end * w)

        if self._loop_enabled and abs(x - ax) < _HIT_RADIUS:
            self._drag = _DRAG_LOOP_A
        elif self._loop_enabled and abs(x - bx) < _HIT_RADIUS:
            self._drag = _DRAG_LOOP_B
        elif abs(x - px) < _HIT_RADIUS:
            self._drag = _DRAG_PLAYHEAD
            self.seek_requested.emit(fraction)
        else:
            self._drag = _DRAG_NONE
            self.seek_requested.emit(fraction)

    def mouseMoveEvent(self, event):
        x = event.position().x()
        fraction = max(0.0, min(1.0, x / self.width()))
        if self._drag == _DRAG_PLAYHEAD:
            self.seek_requested.emit(fraction)
        elif self._drag == _DRAG_LOOP_A:
            self.loop_start_changed.emit(fraction)
        elif self._drag == _DRAG_LOOP_B:
            self.loop_end_changed.emit(fraction)

    def mouseReleaseEvent(self, event):
        self._drag = _DRAG_NONE
